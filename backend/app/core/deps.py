"""Dependencias de FastAPI, sobre todo la identificacion del usuario.

El punto importante de este archivo es `get_current_user`: es la unica puerta
de entrada autenticada del sistema. Los dos proveedores (JWT propio y Keycloak)
devuelven el mismo objeto `User`, asi que ningun router sabe cual esta activo.
"""

from __future__ import annotations

import time
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import TokenError, decode_token
from app.db.models import User
from app.db.session import get_db

# auto_error=False para poder devolver un 401 con cuerpo JSON propio en vez
# del texto plano que genera FastAPI.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Keycloak: cliente JWKS con cache
# ─────────────────────────────────────────────────────────────────────────────
_jwks_client: PyJWKClient | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


def _get_jwks_client() -> PyJWKClient:
    """Cliente JWKS reutilizado durante una hora.

    Sin cache, cada peticion autenticada dispararia una llamada HTTP a Keycloak
    para descargar las claves publicas.
    """
    global _jwks_client, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_client is None or (now - _jwks_fetched_at) > _JWKS_TTL_SECONDS:
        _jwks_client = PyJWKClient(settings.keycloak_jwks_url)
        _jwks_fetched_at = now
    return _jwks_client


def _decode_keycloak_token(token: str) -> dict[str, Any]:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            # Keycloak suele emitir el access token con aud="account"; lo que
            # de verdad identifica al cliente es azp, que se comprueba abajo.
            options={"verify_aud": False},
        )
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise _unauthorized(f"Token de Keycloak invalido: {exc}") from exc


def _user_from_keycloak(payload: dict[str, Any], db: Session) -> User:
    """Busca o crea el usuario local que corresponde al token de Keycloak.

    Keycloak es la autoridad de identidad, pero las conversaciones y los
    documentos son filas nuestras: hace falta una fila en `users` a la que
    apuntar.
    """
    sub = payload.get("sub")
    if not sub:
        raise _unauthorized("El token no identifica a ningun usuario.")

    email = payload.get("email") or f"{sub}@keycloak.local"
    nombre = payload.get("name") or payload.get("preferred_username") or email

    user = db.query(User).filter(User.external_id == sub).one_or_none()
    if user is None:
        # Puede existir ya con ese correo si antes se registro en modo local.
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(email=email, nombre=nombre, external_id=sub, password_hash=None)
            db.add(user)
        else:
            user.external_id = sub
        db.commit()
        db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Dependencia principal
# ─────────────────────────────────────────────────────────────────────────────
def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Falta el encabezado Authorization.")

    token = credentials.credentials

    if settings.AUTH_PROVIDER == "keycloak":
        payload = _decode_keycloak_token(token)
        azp = payload.get("azp") or payload.get("client_id")
        if azp and azp != settings.KEYCLOAK_CLIENT_ID:
            raise _unauthorized("El token fue emitido para otro cliente.")
        return _user_from_keycloak(payload, db)

    # AUTH_PROVIDER=local
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    user = db.query(User).filter(User.id == payload["sub"]).one_or_none()
    if user is None:
        raise _unauthorized("El usuario del token ya no existe.")
    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta desactivada.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
