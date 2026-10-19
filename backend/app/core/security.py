"""Hashing de contrasenas y emision/verificacion de JWT propios.

Este modulo solo cubre AUTH_PROVIDER=local. La validacion de tokens de
Keycloak vive en core/deps.py porque necesita red (descargar el JWKS).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

# bcrypt ignora en silencio todo lo que pase de 72 bytes. En vez de truncar
# sin avisar -- lo que haria que dos contrasenas distintas con el mismo prefijo
# fueran equivalentes -- se rechaza explicitamente al registrar.
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """La contrasena excede lo que bcrypt puede procesar."""


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"La contrasena no puede superar {MAX_PASSWORD_BYTES} bytes."
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        # Hash corrupto o con formato desconocido: se trata como fallo de login,
        # no como error del servidor.
        return False


def _create_token(
    subject: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Devuelve (token, jti, fecha de expiracion).

    El jti permite revocar un refresh token concreto al cerrar sesion.
    """
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def create_access_token(user_id: str, email: str) -> tuple[str, datetime]:
    token, _, expires_at = _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"email": email},
    )
    return token, expires_at


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


class TokenError(Exception):
    """El token no es valido, expiro o no es del tipo esperado."""


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("El token expiro.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("El token no es valido.") from exc

    # Sin esta comprobacion, un refresh token serviria como access token y
    # duraria dias en vez de minutos.
    if payload.get("type") != expected_type:
        raise TokenError(f"Se esperaba un token de tipo '{expected_type}'.")

    if not payload.get("sub"):
        raise TokenError("El token no identifica a ningun usuario.")

    return payload
