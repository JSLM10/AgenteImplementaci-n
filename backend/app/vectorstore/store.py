"""Acceso a la base vectorial (PostgreSQL + pgvector via langchain-postgres).

Aqui vive la primera de las seis estrategias anti-alucinacion: el umbral
minimo de similitud. Los fragmentos que no lo alcanzan se descartan antes de
llegar al modelo, de modo que el LLM nunca llega a ver contexto irrelevante
que pudiera tentarle a improvisar.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.documents import Document as LCDocument
from langchain_postgres import PGVector

from app.core.config import settings
from app.vectorstore.embeddings import get_embeddings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Fragmento:
    """Un trozo de documento recuperado, con su procedencia y su score."""

    contenido: str
    documento: str
    document_id: str | None
    pagina: int | None
    score: float

    def como_fuente(self, max_caracteres: int = 320) -> dict[str, Any]:
        extracto = self.contenido.strip().replace("\n", " ")
        if len(extracto) > max_caracteres:
            extracto = extracto[:max_caracteres].rsplit(" ", 1)[0] + "…"
        return {
            "documento": self.documento,
            "document_id": self.document_id,
            "pagina": self.pagina,
            "score": round(self.score, 4),
            "extracto": extracto,
        }


@lru_cache
def get_vector_store() -> PGVector:
    """Instancia unica del vector store.

    `use_jsonb=True` guarda los metadatos como JSONB, que es lo que permite
    filtrar por propietario directamente en la consulta SQL.
    """
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.COLLECTION_NAME,
        connection=settings.DATABASE_URL,
        use_jsonb=True,
    )


def _filtro_visibilidad(user_id: uuid.UUID | None) -> dict[str, Any]:
    """Un usuario ve el corpus publico mas lo que el mismo subio.

    Esta regla es lo que hace que un jurado que se registre en la URL publica
    encuentre la base de futbol, y a la vez que los documentos privados de un
    usuario no aparezcan nunca en las respuestas de otro.
    """
    if user_id is None:
        return {"es_publico": {"$eq": True}}
    return {
        "$or": [
            {"es_publico": {"$eq": True}},
            {"owner_id": {"$eq": str(user_id)}},
        ]
    }


def buscar_fragmentos(
    pregunta: str,
    user_id: uuid.UUID | None,
    k: int | None = None,
    min_score: float | None = None,
) -> tuple[list[Fragmento], float]:
    """Busca fragmentos relevantes y descarta los que no llegan al umbral.

    Devuelve (fragmentos aceptados, mejor score visto). El mejor score se
    devuelve aunque todo se haya descartado, porque es util para explicar por
    que el agente rechazo la pregunta.
    """
    k = k or settings.RETRIEVAL_K
    umbral = settings.RETRIEVAL_MIN_SCORE if min_score is None else min_score

    try:
        resultados = get_vector_store().similarity_search_with_relevance_scores(
            pregunta,
            k=k,
            filter=_filtro_visibilidad(user_id),
        )
    except Exception:
        # Si la coleccion todavia no existe (base recien creada, sin ingesta),
        # no hay contexto: el agente rechazara, que es el comportamiento
        # correcto y seguro.
        logger.exception("Fallo la busqueda vectorial")
        return [], 0.0

    if not resultados:
        return [], 0.0

    mejor_score = max(score for _, score in resultados)

    aceptados: list[Fragmento] = []
    for doc, score in resultados:
        if score < umbral:
            continue
        meta = doc.metadata or {}
        aceptados.append(
            Fragmento(
                contenido=doc.page_content,
                documento=meta.get("nombre_archivo", "documento desconocido"),
                document_id=meta.get("document_id"),
                pagina=meta.get("pagina"),
                score=float(score),
            )
        )

    logger.info(
        "Recuperacion: %d candidatos, %d sobre el umbral %.2f (mejor %.3f)",
        len(resultados),
        len(aceptados),
        umbral,
        mejor_score,
    )
    return aceptados, float(mejor_score)


def chunk_id(document_id: uuid.UUID, indice: int) -> str:
    """Identificador determinista de cada fragmento.

    Que sea determinista permite borrar todos los fragmentos de un documento
    sin tener que consultar antes cuales son, y hace la reingesta idempotente.
    """
    return f"{document_id}:{indice}"


def agregar_fragmentos(documentos: list[LCDocument], document_id: uuid.UUID) -> int:
    """Vectoriza y guarda los fragmentos de un documento."""
    if not documentos:
        return 0
    ids = [chunk_id(document_id, i) for i in range(len(documentos))]
    get_vector_store().add_documents(documents=documentos, ids=ids)
    return len(documentos)


def eliminar_fragmentos(document_id: uuid.UUID, num_fragmentos: int) -> None:
    """Borra de la base vectorial todos los fragmentos de un documento."""
    if num_fragmentos <= 0:
        return
    ids = [chunk_id(document_id, i) for i in range(num_fragmentos)]
    try:
        get_vector_store().delete(ids=ids)
    except Exception:
        logger.exception("No se pudieron borrar los fragmentos de %s", document_id)
