"""Proveedor de modelo de lenguaje local.

Dos implementaciones de la misma interfaz, elegidas con LLM_PROVIDER:

  ollama        Ollama corriendo en la maquina. Es el camino por defecto y el
                de la demo en vivo: mejores respuestas y mas rapido, porque el
                modelo ya esta cargado en el servidor de Ollama.
  huggingface   Transformers dentro del propio proceso del backend. Pensado
                para el despliegue en la nube, donde no hay un Ollama al lado.

Los dos son modelos locales: en ningun caso se llama a una API comercial.

El numero maximo de tokens se fija al construir el modelo, no por llamada, asi
que se cachea una instancia por tamano. Son tres: respuestas de una palabra
para clasificar, veredictos cortos para evaluar, y la respuesta final.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Presupuestos de tokens por tipo de tarea (ver §11.2 del documento de diseno).
#
# Medido en el portatil de destino (i7-1255U, sin GPU) con qwen3.5:4b:
# 11,7 tokens por segundo. De ahi salen estos numeros: la respuesta no puede
# pasar de ~320 tokens si se quiere quedar por debajo de los 30 segundos.
TOKENS_CLASIFICACION = 8
TOKENS_VEREDICTO = 64
TOKENS_RESPUESTA = 320


@lru_cache
def get_llm(max_tokens: int = TOKENS_RESPUESTA) -> BaseChatModel:
    proveedor = settings.LLM_PROVIDER.lower()

    if proveedor == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            num_predict=max_tokens,
            # Ventana de contexto suficiente para los fragmentos recuperados
            # mas el prompt y el historial.
            num_ctx=4096,
            # Los modelos de razonamiento (la familia Qwen3, entre otros)
            # gastan el presupuesto de tokens pensando antes de escribir: con
            # num_predict=8 devuelven la respuesta vacia. Desactivarlo baja de
            # 6,6 a 11,7 tokens por segundo en la maquina de destino y hace
            # que las llamadas cortas funcionen. En un modelo sin razonamiento
            # el parametro se ignora.
            reasoning=settings.OLLAMA_REASONING,
        )

    if proveedor == "huggingface":
        # Import perezoso: transformers solo se instala con el extra "cloud".
        from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

        pipeline = HuggingFacePipeline.from_model_id(
            model_id=settings.HF_MODEL,
            task="text-generation",
            pipeline_kwargs={
                "max_new_tokens": max_tokens,
                "temperature": settings.LLM_TEMPERATURE,
                "do_sample": settings.LLM_TEMPERATURE > 0,
                "return_full_text": False,
            },
        )
        return ChatHuggingFace(llm=pipeline)

    raise ValueError(
        f"LLM_PROVIDER='{settings.LLM_PROVIDER}' no es valido. Use 'ollama' o 'huggingface'."
    )


def describir_modelo() -> dict[str, str]:
    """Datos del modelo activo, para el endpoint de salud y la sustentacion."""
    if settings.LLM_PROVIDER.lower() == "huggingface":
        return {"proveedor": "huggingface", "modelo": settings.HF_MODEL}
    return {
        "proveedor": "ollama",
        "modelo": settings.OLLAMA_MODEL,
        "base_url": settings.OLLAMA_BASE_URL,
    }
