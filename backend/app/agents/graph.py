"""Construccion del grafo de LangGraph.

Este archivo es el que hay que mostrar en la sustentacion: es la topologia
completa del agente, y se corresponde uno a uno con los siete pasos del flujo
de referencia del enunciado.

    START
      │
      ▼
  clasificar ──SALUDO──────────────────────────────┐
      │ OTRO ─────────────────────────┐            │
      │ PREGUNTA                      │            │
      ▼                               │            │
  reformular                          │            │
      │                               │            │
      ▼                               │            │
  recuperar                           │            │
      │                               │            │
      ▼                               ▼            ▼
   evaluar ──insuficiente──────►  rechazar      saludo
      │ suficiente                   │            │
      ▼                              │            │
   generar                           │            │
      │                              │            │
      ▼                              │            │
  verificar                          │            │
      │                              │            │
      └──────────────┬───────────────┴────────────┘
                     ▼
                 historial
                     │
                     ▼
                    END
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    clasificar,
    evaluar,
    generar,
    recuperar,
    rechazar,
    reformular,
    responder_saludo,
    verificar,
)
from app.agents.state import EstadoAgente
from app.services.conversations import guardar_interaccion

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Nodo final — guardar la interaccion en el historial
# ─────────────────────────────────────────────────────────────────────────────
def guardar_historial(state: EstadoAgente) -> dict:
    conversation_id = state.get("conversation_id")
    if not conversation_id:
        return {"traza": ["historial(omitido)"]}

    try:
        guardar_interaccion(
            conversation_id=uuid.UUID(conversation_id),
            pregunta=state["pregunta"],
            respuesta=state.get("respuesta", ""),
            rechazada=bool(state.get("rechazada", False)),
            fuentes=state.get("fuentes") or None,
        )
    except Exception:
        # Perder el historial es molesto, pero no justifica tumbar una
        # respuesta que el usuario ya tiene delante.
        logger.exception("No se pudo guardar la interacción en el historial")
        return {"traza": ["historial(error)"]}

    return {"traza": ["historial"]}


# ─────────────────────────────────────────────────────────────────────────────
# Aristas condicionales
# ─────────────────────────────────────────────────────────────────────────────
def _ruta_tras_clasificar(state: EstadoAgente) -> str:
    intencion = state.get("intencion", "PREGUNTA")
    if intencion == "SALUDO":
        return "saludo"
    if intencion == "OTRO":
        return "rechazar"
    return "reformular"


def _ruta_tras_evaluar(state: EstadoAgente) -> str:
    """La bifurcacion central del trabajo.

    Es el punto donde el agente decide no inventar: si el contexto no alcanza,
    no hay generacion, se va directo al rechazo explicito.
    """
    return "generar" if state.get("contexto_suficiente") else "rechazar"


# ─────────────────────────────────────────────────────────────────────────────
# Construccion
# ─────────────────────────────────────────────────────────────────────────────
def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("clasificar", clasificar)
    grafo.add_node("saludo", responder_saludo)
    grafo.add_node("reformular", reformular)
    grafo.add_node("recuperar", recuperar)
    grafo.add_node("evaluar", evaluar)
    grafo.add_node("generar", generar)
    grafo.add_node("verificar", verificar)
    grafo.add_node("rechazar", rechazar)
    grafo.add_node("historial", guardar_historial)

    grafo.add_edge(START, "clasificar")

    grafo.add_conditional_edges(
        "clasificar",
        _ruta_tras_clasificar,
        {"saludo": "saludo", "reformular": "reformular", "rechazar": "rechazar"},
    )

    grafo.add_edge("reformular", "recuperar")
    grafo.add_edge("recuperar", "evaluar")

    grafo.add_conditional_edges(
        "evaluar",
        _ruta_tras_evaluar,
        {"generar": "generar", "rechazar": "rechazar"},
    )

    grafo.add_edge("generar", "verificar")

    # Los tres finales posibles convergen en el historial: toda interaccion se
    # guarda, responda o rechace.
    grafo.add_edge("verificar", "historial")
    grafo.add_edge("rechazar", "historial")
    grafo.add_edge("saludo", "historial")

    grafo.add_edge("historial", END)

    return grafo


@lru_cache
def get_agente():
    """Grafo compilado, una sola vez por proceso."""
    compilado = construir_grafo().compile()
    logger.info("Grafo del agente compilado")
    return compilado


def diagrama_mermaid() -> str:
    """Diagrama del grafo en sintaxis Mermaid.

    Lo genera LangGraph a partir de la topologia real, asi que no puede
    quedarse desactualizado respecto al codigo. Se expone en /api/health/grafo
    y se usa en el documento tecnico.
    """
    return get_agente().get_graph().draw_mermaid()
