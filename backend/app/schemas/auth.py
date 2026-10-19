"""Modelos de entrada y salida de autenticacion."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegistroRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_suficientemente_fuerte(cls, v: str) -> str:
        # Minimo razonable para un trabajo academico: evita "12345678" sin
        # exigir simbolos raros que el jurado tendria que teclear en la demo.
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contrasena debe incluir al menos una letra y un numero.")
        return v

    @field_validator("nombre")
    @classmethod
    def nombre_sin_espacios_sobrantes(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("El nombre no puede estar vacio.")
        return limpio


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    creado_en: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    usuario: UsuarioOut
