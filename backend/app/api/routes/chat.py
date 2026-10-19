"""Controlador del chat y del historial de conversaciones."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.chat import (
    ConversacionDetalleOut,
    ConversacionOut,
    MensajeOut,
    PreguntaRequest,
    RespuestaOut,
)
from app.services import agent_service, conversations

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=RespuestaOut,
    summary="Enviar una pregunta al agente",
)
def preguntar(peticion: PreguntaRequest, usuario: CurrentUser, db: DbSession) -> RespuestaOut:
    """Ejecuta el grafo del agente y devuelve la respuesta con sus fuentes.

    Si el contexto recuperado no alcanza, `rechazada` viene en true y la
    respuesta es el mensaje explicito de rechazo.
    """
    return agent_service.responder(db, usuario, peticion)


@router.get(
    "/conversations",
    response_model=list[ConversacionOut],
    summary="Listar las conversaciones del usuario",
)
def listar(usuario: CurrentUser, db: DbSession) -> list[ConversacionOut]:
    return [
        ConversacionOut.model_validate(c)
        for c in conversations.listar_conversaciones(db, usuario)
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversacionDetalleOut,
    summary="Ver el historial de una conversación",
)
def detalle(
    conversation_id: uuid.UUID, usuario: CurrentUser, db: DbSession
) -> ConversacionDetalleOut:
    conversacion = conversations.obtener_conversacion(db, usuario, conversation_id)
    if conversacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La conversación no existe.",
        )

    return ConversacionDetalleOut(
        id=conversacion.id,
        titulo=conversacion.titulo,
        creado_en=conversacion.creado_en,
        actualizado_en=conversacion.actualizado_en,
        mensajes=[MensajeOut.model_validate(m) for m in conversacion.mensajes],
    )


@router.delete(
    "/conversations/{conversation_id}",
    summary="Eliminar una conversación",
)
def eliminar(conversation_id: uuid.UUID, usuario: CurrentUser, db: DbSession) -> dict:
    if not conversations.eliminar_conversacion(db, usuario, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La conversación no existe.",
        )
    return {"mensaje": "Conversación eliminada."}
