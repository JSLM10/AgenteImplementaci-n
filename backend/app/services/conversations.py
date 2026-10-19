"""Conversaciones e historial.

Separado de los routers a proposito: el nodo `historial` del grafo tambien
necesita guardar, y un nodo del agente no debe depender de la sesion de base
de datos que abrio una peticion HTTP.
"""

from __future__ import annotations

import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Conversation, Message, RolMensaje, User
from app.db.session import SessionLocal

TITULO_MAXIMO = 60


def _titulo_desde(pregunta: str) -> str:
    limpio = " ".join(pregunta.split())
    if len(limpio) <= TITULO_MAXIMO:
        return limpio
    return limpio[:TITULO_MAXIMO].rsplit(" ", 1)[0] + "…"


def obtener_o_crear_conversacion(
    db: Session,
    usuario: User,
    conversation_id: uuid.UUID | None,
    pregunta: str,
) -> Conversation:
    """Devuelve la conversacion indicada, o crea una nueva si no se indica.

    Si se indica una que no existe o es de otro usuario, se trata como "no
    existe": nunca se revela que la conversacion pertenece a alguien mas.
    """
    if conversation_id is not None:
        conversacion = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == usuario.id,
            )
        )
        if conversacion is not None:
            return conversacion

    conversacion = Conversation(user_id=usuario.id, titulo=_titulo_desde(pregunta))
    db.add(conversacion)
    db.commit()
    db.refresh(conversacion)
    return conversacion


def cargar_historial(db: Session, conversation_id: uuid.UUID) -> list[BaseMessage]:
    """Historial reciente como mensajes de LangChain, en orden cronologico."""
    mensajes = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.creado_en.desc())
        .limit(settings.MAX_HISTORY_MESSAGES)
    ).all()

    historial: list[BaseMessage] = []
    for mensaje in reversed(mensajes):
        if mensaje.rol == RolMensaje.USUARIO:
            historial.append(HumanMessage(content=mensaje.contenido))
        else:
            historial.append(AIMessage(content=mensaje.contenido))
    return historial


def guardar_interaccion(
    conversation_id: uuid.UUID,
    pregunta: str,
    respuesta: str,
    rechazada: bool,
    fuentes: list[dict] | None,
) -> None:
    """Persiste el par pregunta/respuesta. Abre y cierra su propia sesion.

    La llama el nodo `historial` del grafo, que no tiene acceso a la sesion de
    la peticion HTTP.
    """
    with SessionLocal() as db:
        db.add(
            Message(
                conversation_id=conversation_id,
                rol=RolMensaje.USUARIO,
                contenido=pregunta,
                rechazada=False,
            )
        )
        db.add(
            Message(
                conversation_id=conversation_id,
                rol=RolMensaje.AGENTE,
                contenido=respuesta,
                rechazada=rechazada,
                fuentes=fuentes or None,
            )
        )
        conversacion = db.get(Conversation, conversation_id)
        if conversacion is not None:
            # Fuerza la actualizacion de `actualizado_en` para que la barra
            # lateral ordene por actividad reciente.
            conversacion.titulo = conversacion.titulo
        db.commit()


def listar_conversaciones(db: Session, usuario: User) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == usuario.id)
            .order_by(Conversation.actualizado_en.desc())
        ).all()
    )


def obtener_conversacion(
    db: Session, usuario: User, conversation_id: uuid.UUID
) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.mensajes))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == usuario.id,
        )
    )


def eliminar_conversacion(db: Session, usuario: User, conversation_id: uuid.UUID) -> bool:
    conversacion = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == usuario.id,
        )
    )
    if conversacion is None:
        return False
    db.delete(conversacion)
    db.commit()
    return True
