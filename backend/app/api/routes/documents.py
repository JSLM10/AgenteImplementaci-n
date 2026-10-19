"""Controlador de carga y gestion de documentos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.schemas.documents import DocumentoOut, SubidaOut
from app.services import documents
from app.services.ingestion import EXTENSIONES_SOPORTADAS

router = APIRouter(prefix="/documents", tags=["Documentos"])


@router.post(
    "",
    response_model=SubidaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un documento a la base de conocimiento",
)
async def subir(
    usuario: CurrentUser,
    db: DbSession,
    tareas: BackgroundTasks,
    archivo: UploadFile = File(..., description="PDF, TXT, MD, CSV o DOCX"),
) -> SubidaOut:
    """Paso 1 y 6 del flujo de ingesta: recibir el archivo y confirmar.

    Los pasos intermedios (extraer, fragmentar, vectorizar, almacenar) corren
    en segundo plano: un PDF grande tardaria mas que el tiempo de espera de la
    petición, y la subida parecería haber fallado.
    """
    if not archivo.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo no tiene nombre.",
        )

    if not documents.extension_valida(archivo.filename):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Formato no soportado. Formatos aceptados: "
                f"{', '.join(sorted(EXTENSIONES_SOPORTADAS))}."
            ),
        )

    contenido = await archivo.read()

    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo está vacío.",
        )

    if len(contenido) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_MB} MB.",
        )

    documento = documents.crear_documento(
        db=db,
        usuario=usuario,
        nombre_archivo=archivo.filename,
        tipo_mime=archivo.content_type or "application/octet-stream",
        contenido=contenido,
    )

    tareas.add_task(documents.procesar_en_segundo_plano, documento.id)

    return SubidaOut(documento=DocumentoOut.model_validate(documento))


@router.get(
    "",
    response_model=list[DocumentoOut],
    summary="Listar los documentos disponibles",
)
def listar(usuario: CurrentUser, db: DbSession) -> list[DocumentoOut]:
    """Los documentos propios mas los de la base común de fútbol."""
    return [
        DocumentoOut.model_validate(d) for d in documents.listar_documentos(db, usuario)
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentoOut,
    summary="Consultar el estado de un documento",
)
def detalle(document_id: uuid.UUID, usuario: CurrentUser, db: DbSession) -> DocumentoOut:
    documento = documents.obtener_documento(db, usuario, document_id)
    if documento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El documento no existe.",
        )
    return DocumentoOut.model_validate(documento)


@router.delete(
    "/{document_id}",
    summary="Eliminar un documento",
)
def eliminar(document_id: uuid.UUID, usuario: CurrentUser, db: DbSession) -> dict:
    ok, mensaje = documents.eliminar_documento(db, usuario, document_id)
    if not ok:
        codigo = (
            status.HTTP_403_FORBIDDEN
            if "común" in mensaje
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=codigo, detail=mensaje)
    return {"mensaje": mensaje}
