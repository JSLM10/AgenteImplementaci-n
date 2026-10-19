"""Estado compartido entre los nodos del grafo.

En LangGraph cada nodo recibe el estado completo y devuelve solo las claves
que modifica; LangGraph las fusiona. `traza` es la excepcion: lleva un
reductor para que cada nodo *anada* su nombre en vez de sobreescribir la lista.
Esa traza es lo que permite mostrar en la sustentacion, y en la propia
interfaz, el camino exacto que siguio cada pregunta por el grafo.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

Intencion = Literal["SALUDO", "PREGUNTA", "OTRO"]


class EstadoAgente(TypedDict, total=False):
    # ─── Entrada ─────────────────────────────────────────────────────────────
    user_id: str
    conversation_id: str
    pregunta: str
    historial: list[BaseMessage]

    # ─── Nodo 1: clasificar ──────────────────────────────────────────────────
    intencion: Intencion

    # ─── Nodo 2: reformular ──────────────────────────────────────────────────
    pregunta_reformulada: str

    # ─── Nodo 3: recuperar ───────────────────────────────────────────────────
    fragmentos: list[dict[str, Any]]
    contexto: str
    score_maximo: float

    # ─── Nodo 4: evaluar ─────────────────────────────────────────────────────
    contexto_suficiente: bool
    motivo_rechazo: str

    # ─── Nodos 5/6: generar, verificar, rechazar ─────────────────────────────
    respuesta: str
    fuentes: list[dict[str, Any]]
    rechazada: bool

    # ─── Diagnostico ─────────────────────────────────────────────────────────
    traza: Annotated[list[str], operator.add]
