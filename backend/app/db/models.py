"""Modelos SQLAlchemy.

Un solo PostgreSQL guarda todo: usuarios, conversaciones, mensajes, documentos
y -- en las tablas que crea langchain-postgres -- los embeddings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(UTC)


class EstadoDocumento(StrEnum):
    PROCESANDO = "PROCESANDO"
    LISTO = "LISTO"
    ERROR = "ERROR"


class RolMensaje(StrEnum):
    USUARIO = "usuario"
    AGENTE = "agente"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)

    # Nulo cuando el usuario viene de Keycloak: alli la contrasena no es nuestra.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "sub" del token de Keycloak, para reconocer al mismo usuario entre sesiones.
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    conversaciones: Mapped[list[Conversation]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    documentos: Mapped[list[Document]] = relationship(
        back_populates="propietario", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Refresh tokens emitidos. Permite cerrar sesion de verdad.

    Sin esta tabla, "cerrar sesion" solo borraria el token del navegador y el
    token seguiria siendo valido durante dias para quien lo hubiera copiado.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revocado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    usuario: Mapped[User] = relationship(back_populates="refresh_tokens")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    titulo: Mapped[str] = mapped_column(String(200), default="Nueva conversacion", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now(), nullable=False
    )

    usuario: Mapped[User] = relationship(back_populates="conversaciones")
    mensajes: Mapped[list[Message]] = relationship(
        back_populates="conversacion",
        cascade="all, delete-orphan",
        order_by="Message.creado_en",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rol: Mapped[str] = mapped_column(String(16), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    # True cuando el agente se nego a responder por falta de contexto. Permite
    # distinguir en el historial una respuesta de un rechazo.
    rechazada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Fragmentos que sustentan la respuesta: nombre de documento, pagina y score.
    fuentes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    conversacion: Mapped[Conversation] = relationship(back_populates="mensajes")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()

    # Nulo = documento semilla, visible para todos los usuarios. Con valor =
    # documento privado de quien lo subio. Es lo que permite que un jurado que
    # se registre vea la base de futbol sin ver los archivos de nadie mas.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    es_publico: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(120), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    estado: Mapped[str] = mapped_column(
        String(16), default=EstadoDocumento.PROCESANDO, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    num_fragmentos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    propietario: Mapped[User | None] = relationship(back_populates="documentos")
