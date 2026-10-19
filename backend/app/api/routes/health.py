"""Estado del servicio y diagrama del grafo."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.agents.llm import describir_modelo
from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["Sistema"])


@router.get("/health", summary="Estado del servicio")
def salud() -> dict:
    """Comprueba que la base de datos responde y describe la configuración activa.

    Es público a propósito: los servicios de despliegue lo usan para saber si
    el contenedor está vivo. No revela datos de ningún usuario.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        base_datos = "ok"
    except Exception as exc:
        base_datos = f"error: {type(exc).__name__}"

    return {
        "estado": "ok" if base_datos == "ok" else "degradado",
        "version": settings.APP_VERSION,
        "base_datos": base_datos,
        "modelo": describir_modelo(),
        "embeddings": {
            "modelo": settings.EMBEDDING_MODEL,
            "dimensiones": settings.EMBEDDING_DIMENSIONS,
        },
        "autenticacion": settings.AUTH_PROVIDER,
        "rag": {
            "k": settings.RETRIEVAL_K,
            "umbral_similitud": settings.RETRIEVAL_MIN_SCORE,
            "verificacion_posterior": settings.ENABLE_GROUNDEDNESS_CHECK,
        },
    }


@router.get("/health/grafo", summary="Diagrama del grafo del agente")
def grafo() -> dict:
    """Devuelve el grafo en sintaxis Mermaid.

    Lo genera LangGraph a partir de la topología real compilada, así que no
    puede quedar desactualizado respecto al código. Sirve de evidencia del uso
    de LangGraph y alimenta el diagrama del documento técnico.
    """
    # Import local: compilar el grafo carga el modelo de embeddings, y este
    # módulo lo importa el arranque de la aplicación.
    from app.agents.graph import diagrama_mermaid

    return {"mermaid": diagrama_mermaid()}
