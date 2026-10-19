"""Embeddings locales con Sentence Transformers.

Se ejecutan dentro del proceso del backend, sin llamar a ningun servicio
externo. Son los mismos en local y en la nube a proposito: la base vectorial
se comparte, y vectores generados por modelos distintos no son comparables.

Los modelos de la familia E5 esperan que el texto venga marcado con un prefijo
que indica su papel ("query:" para la pregunta, "passage:" para el fragmento
indexado). Omitirlos degrada la recuperacion de forma notable, y
HuggingFaceEmbeddings no los pone por su cuenta, asi que se anaden aqui.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings


class E5Embeddings(HuggingFaceEmbeddings):
    """HuggingFaceEmbeddings con los prefijos que exige E5."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return super().embed_documents([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(f"query: {text}")


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Instancia unica del modelo de embeddings.

    Cargar el modelo cuesta varios segundos y unos cientos de MB de RAM, asi
    que se hace una sola vez por proceso.
    """
    nombre = settings.EMBEDDING_MODEL
    kwargs = {
        "model_name": nombre,
        "model_kwargs": {"device": "cpu"},
        # Vectores normalizados: con similitud coseno, el score cae en [0, 1]
        # y el umbral de RETRIEVAL_MIN_SCORE es interpretable.
        "encode_kwargs": {"normalize_embeddings": True},
    }
    # Solo los modelos E5 necesitan el prefijo; otros lo tomarian como texto.
    if "e5" in nombre.lower():
        return E5Embeddings(**kwargs)
    return HuggingFaceEmbeddings(**kwargs)
