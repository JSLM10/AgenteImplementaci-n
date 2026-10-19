"""Registro, login, refresco y cierre de sesion (AUTH_PROVIDER=local)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    PasswordTooLongError,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.schemas.auth import LoginRequest, RegistroRequest, TokenResponse, UsuarioOut

# Mensaje unico para usuario inexistente y contrasena incorrecta: decir cual de
# las dos falla permitiria averiguar que correos estan registrados.
CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."


def _emitir_tokens(db: Session, usuario: User) -> TokenResponse:
    access_token, expira_en = create_access_token(str(usuario.id), usuario.email)
    refresh_token, jti, refresh_expira = create_refresh_token(str(usuario.id))

    db.add(
        RefreshToken(
            jti=jti,
            user_id=usuario.id,
            expira_en=refresh_expira,
        )
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expira_en,
        usuario=UsuarioOut.model_validate(usuario),
    )


def registrar(db: Session, datos: RegistroRequest) -> TokenResponse:
    email = datos.email.lower().strip()

    existente = db.scalar(select(User).where(User.email == email))
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo.",
        )

    try:
        password_hash = hash_password(datos.password)
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    usuario = User(email=email, nombre=datos.nombre, password_hash=password_hash)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return _emitir_tokens(db, usuario)


def iniciar_sesion(db: Session, datos: LoginRequest) -> TokenResponse:
    email = datos.email.lower().strip()
    usuario = db.scalar(select(User).where(User.email == email))

    if usuario is None or not usuario.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=CREDENCIALES_INVALIDAS,
        )

    if not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=CREDENCIALES_INVALIDAS,
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada.",
        )

    return _emitir_tokens(db, usuario)


def refrescar(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    registro = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if registro is None or registro.revocado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de refresco ya no es válido.",
        )
    if registro.expira_en < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de refresco expiró.",
        )

    usuario = db.get(User, uuid.UUID(payload["sub"]))
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario del token ya no existe.",
        )

    # Rotacion: el refresh usado se revoca al emitir el nuevo par. Si alguien
    # roba un refresh token y lo usa, el legitimo deja de funcionar y el robo
    # se nota.
    registro.revocado = True
    db.commit()

    return _emitir_tokens(db, usuario)


def cerrar_sesion(db: Session, usuario: User) -> None:
    """Revoca todos los refresh tokens del usuario.

    Sin esto, "cerrar sesión" solo borraria el token del navegador y seguiria
    siendo valido durante dias para quien lo hubiera copiado.
    """
    tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == usuario.id,
            RefreshToken.revocado.is_(False),
        )
    ).all()
    for token in tokens:
        token.revocado = True
    db.commit()
