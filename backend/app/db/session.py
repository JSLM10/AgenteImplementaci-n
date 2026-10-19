"""Motor y sesiones de SQLAlchemy."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # reconecta si Neon durmio la conexion
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Crea la extension pgvector y las tablas de la aplicacion.

    langchain-postgres crea por su cuenta sus tablas de embeddings la primera
    vez que se usa el vector store, pero necesita que la extension exista.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesion por peticion, siempre cerrada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
