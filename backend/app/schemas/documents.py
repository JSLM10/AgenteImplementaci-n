"""Modelos de entrada y salida de documentos."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre_archivo: str
    tipo_mime: str
    tamano_bytes: int
    estado: str  # PROCESANDO | LISTO | ERROR
    error: str | None = None
    num_fragmentos: int
    es_publico: bool
    creado_en: datetime


class SubidaOut(BaseModel):
    """Respuesta inmediata de la subida.

    El procesamiento ocurre en segundo plano, asi que esto confirma la
    recepcion, no el fin de la ingesta. El frontend consulta el estado del
    documento hasta que pase a LISTO o ERROR.
    """

    documento: DocumentoOut
    mensaje: str = "Documento recibido. Procesando en segundo plano."
