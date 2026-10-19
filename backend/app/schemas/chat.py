"""Modelos de entrada y salida del chat."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PreguntaRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)
    # Nulo = empezar una conversacion nueva.
    conversation_id: uuid.UUID | None = None

    @field_validator("pregunta")
    @classmethod
    def pregunta_no_vacia(cls, v: str) -> str:
        limpia = v.strip()
        if not limpia:
            raise ValueError("La pregunta no puede estar vacia.")
        return limpia


class FuenteOut(BaseModel):
    """Un fragmento recuperado que sustenta la respuesta.

    Se devuelve al frontend para que el usuario pueda comprobar de donde salio
    cada afirmacion. Es una de las seis estrategias anti-alucinacion.
    """

    documento: str
    document_id: str | None = None
    pagina: int | None = None
    score: float
    extracto: str


class RespuestaOut(BaseModel):
    conversation_id: uuid.UUID
    respuesta: str
    # True cuando el agente se nego por falta de contexto suficiente.
    rechazada: bool
    fuentes: list[FuenteOut] = []
    # Ruta que siguio el grafo, p.ej. ["clasificar", "recuperar", "evaluar", ...].
    # Sirve para explicar el grafo en vivo durante la sustentacion.
    traza: list[str] = []
    duracion_ms: int = 0


class MensajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rol: str
    contenido: str
    rechazada: bool
    fuentes: list[FuenteOut] | None = None
    creado_en: datetime


class ConversacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    creado_en: datetime
    actualizado_en: datetime


class ConversacionDetalleOut(ConversacionOut):
    mensajes: list[MensajeOut] = []
