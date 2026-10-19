"""Orquestacion entre la peticion HTTP y el grafo del agente.

El router no habla con LangGraph directamente: prepara la conversacion y el
historial, invoca el grafo y traduce el estado final a la respuesta de la API.
"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.agents.graph import get_agente
from app.db.models import User
from app.schemas.chat import PreguntaRequest, RespuestaOut
from app.services.conversations import cargar_historial, obtener_o_crear_conversacion

logger = logging.getLogger(__name__)


def responder(db: Session, usuario: User, peticion: PreguntaRequest) -> RespuestaOut:
    inicio = time.perf_counter()

    conversacion = obtener_o_crear_conversacion(
        db=db,
        usuario=usuario,
        conversation_id=peticion.conversation_id,
        pregunta=peticion.pregunta,
    )
    historial = cargar_historial(db, conversacion.id)

    estado_inicial = {
        "user_id": str(usuario.id),
        "conversation_id": str(conversacion.id),
        "pregunta": peticion.pregunta,
        "historial": historial,
        "traza": [],
    }

    estado_final = get_agente().invoke(estado_inicial)

    duracion_ms = int((time.perf_counter() - inicio) * 1000)
    logger.info(
        "Pregunta resuelta en %d ms por la ruta %s",
        duracion_ms,
        " → ".join(estado_final.get("traza", [])),
    )

    return RespuestaOut(
        conversation_id=conversacion.id,
        respuesta=estado_final.get("respuesta", ""),
        rechazada=bool(estado_final.get("rechazada", False)),
        fuentes=estado_final.get("fuentes") or [],
        traza=estado_final.get("traza") or [],
        duracion_ms=duracion_ms,
    )
