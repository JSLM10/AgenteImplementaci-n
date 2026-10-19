"""Gestion de documentos subidos por los usuarios."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, EstadoDocumento, User
from app.db.session import SessionLocal
from app.services.ingestion import EXTENSIONES_SOPORTADAS, procesar_documento
from app.vectorstore.store import eliminar_fragmentos

logger = logging.getLogger(__name__)


def extension_valida(nombre_archivo: str) -> bool:
    return Path(nombre_archivo).suffix.lower() in EXTENSIONES_SOPORTADAS


def ruta_almacenamiento(document_id: uuid.UUID, nombre_archivo: str) -> Path:
    """Ruta en disco del archivo original.

    Se nombra con el id del documento, no con el nombre que trae el usuario:
    un nombre como "../../etc/passwd" escribiria fuera del directorio.
    """
    directorio = settings.storage_path
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio / f"{document_id}{Path(nombre_archivo).suffix.lower()}"


def crear_documento(
    db: Session,
    usuario: User | None,
    nombre_archivo: str,
    tipo_mime: str,
    contenido: bytes,
    es_publico: bool = False,
) -> Document:
    """Guarda el archivo en disco y crea la fila en estado PROCESANDO."""
    documento = Document(
        owner_id=usuario.id if usuario else None,
        es_publico=es_publico,
        nombre_archivo=Path(nombre_archivo).name,
        tipo_mime=tipo_mime or "application/octet-stream",
        tamano_bytes=len(contenido),
        estado=EstadoDocumento.PROCESANDO,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)

    ruta = ruta_almacenamiento(documento.id, documento.nombre_archivo)
    ruta.write_bytes(contenido)

    return documento


def procesar_en_segundo_plano(document_id: uuid.UUID) -> None:
    """Ejecuta la ingesta y actualiza el estado del documento.

    Corre fuera del ciclo de la peticion HTTP, con su propia sesion. Nunca
    lanza: un fallo se registra en la fila como estado ERROR para que el
    usuario lo vea en la interfaz.
    """
    with SessionLocal() as db:
        documento = db.get(Document, document_id)
        if documento is None:
            logger.warning("El documento %s desapareció antes de procesarse", document_id)
            return

        ruta = ruta_almacenamiento(documento.id, documento.nombre_archivo)
        try:
            total = procesar_documento(
                ruta=ruta,
                document_id=documento.id,
                nombre_archivo=documento.nombre_archivo,
                owner_id=documento.owner_id,
                es_publico=documento.es_publico,
            )
            documento.num_fragmentos = total
            documento.estado = EstadoDocumento.LISTO
            documento.error = None
        except Exception as exc:
            logger.exception("Falló el procesamiento de %s", documento.nombre_archivo)
            documento.estado = EstadoDocumento.ERROR
            documento.error = str(exc)[:500]
        db.commit()


def listar_documentos(db: Session, usuario: User) -> list[Document]:
    """Los documentos del usuario mas los publicos del corpus semilla.

    Es la misma regla de visibilidad que aplica la busqueda vectorial: lo que
    el usuario ve listado es exactamente aquello sobre lo que puede preguntar.
    """
    return list(
        db.scalars(
            select(Document)
            .where(or_(Document.owner_id == usuario.id, Document.es_publico.is_(True)))
            .order_by(Document.es_publico.asc(), Document.creado_en.desc())
        ).all()
    )


def obtener_documento(db: Session, usuario: User, document_id: uuid.UUID) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.id == document_id,
            or_(Document.owner_id == usuario.id, Document.es_publico.is_(True)),
        )
    )


def eliminar_documento(db: Session, usuario: User, document_id: uuid.UUID) -> tuple[bool, str]:
    """Borra el documento, su archivo y sus fragmentos de la base vectorial."""
    documento = db.scalar(select(Document).where(Document.id == document_id))

    if documento is None:
        return False, "El documento no existe."

    # Los documentos del corpus semilla son compartidos: que un usuario pueda
    # borrarlos dejaria al resto sin base de conocimiento.
    if documento.owner_id != usuario.id:
        if documento.es_publico:
            return False, "Los documentos de la base de conocimiento común no se pueden eliminar."
        return False, "El documento no existe."

    eliminar_fragmentos(documento.id, documento.num_fragmentos)

    ruta = ruta_almacenamiento(documento.id, documento.nombre_archivo)
    ruta.unlink(missing_ok=True)

    db.delete(documento)
    db.commit()
    return True, "Documento eliminado."
