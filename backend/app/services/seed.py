"""Siembra del corpus inicial de futbol.

Los documentos de `backend/seed/` se ingestan como publicos: no pertenecen a
ningun usuario y son visibles para todos. Es lo que hace que cualquiera que se
registre -- un jurado durante la sustentacion, por ejemplo -- encuentre una
base de conocimiento ya cargada en vez de un agente que lo rechaza todo.

Es idempotente: al arrancar comprueba que documentos faltan y solo procesa
esos, asi que reiniciar el servidor no duplica nada.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import BACKEND_DIR
from app.db.models import Document, EstadoDocumento
from app.db.session import SessionLocal
from app.services.ingestion import procesar_documento

logger = logging.getLogger(__name__)

SEED_DIR = BACKEND_DIR / "seed"


def sembrar_corpus_inicial() -> int:
    """Ingesta los documentos semilla que falten. Devuelve cuantos proceso."""
    if not SEED_DIR.exists():
        logger.warning("No existe el directorio de corpus inicial: %s", SEED_DIR)
        return 0

    archivos = sorted(
        p for p in SEED_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".md"
    )
    if not archivos:
        logger.warning("El directorio de corpus inicial está vacío")
        return 0

    procesados = 0

    with SessionLocal() as db:
        existentes = {
            nombre
            for (nombre,) in db.execute(
                select(Document.nombre_archivo).where(
                    Document.es_publico.is_(True),
                    Document.estado == EstadoDocumento.LISTO,
                )
            ).all()
        }

        pendientes = [p for p in archivos if p.name not in existentes]
        if not pendientes:
            logger.info("Corpus inicial ya cargado (%d documentos)", len(existentes))
            return 0

        logger.info(
            "Sembrando corpus inicial: %d documentos. "
            "La primera vez tarda, porque hay que descargar el modelo de embeddings.",
            len(pendientes),
        )

        for ruta in pendientes:
            # Se limpia cualquier intento anterior fallido del mismo archivo.
            anterior = db.scalar(
                select(Document).where(
                    Document.nombre_archivo == ruta.name,
                    Document.es_publico.is_(True),
                )
            )
            if anterior is not None:
                db.delete(anterior)
                db.commit()

            documento = Document(
                owner_id=None,
                es_publico=True,
                nombre_archivo=ruta.name,
                tipo_mime="text/markdown",
                tamano_bytes=ruta.stat().st_size,
                estado=EstadoDocumento.PROCESANDO,
            )
            db.add(documento)
            db.commit()
            db.refresh(documento)

            try:
                total = procesar_documento(
                    ruta=ruta,
                    document_id=documento.id,
                    nombre_archivo=ruta.name,
                    owner_id=None,
                    es_publico=True,
                )
                documento.num_fragmentos = total
                documento.estado = EstadoDocumento.LISTO
                procesados += 1
                logger.info("  ✓ %s — %d fragmentos", ruta.name, total)
            except Exception as exc:
                logger.exception("  ✗ %s", ruta.name)
                documento.estado = EstadoDocumento.ERROR
                documento.error = str(exc)[:500]
            db.commit()

    logger.info("Corpus inicial: %d documentos procesados", procesados)
    return procesados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from app.db.session import init_db

    init_db()
    sembrar_corpus_inicial()
