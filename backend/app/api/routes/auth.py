"""Controlador de autenticacion."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegistroRequest,
    TokenResponse,
    UsuarioOut,
)
from app.services import auth_service

# Rutas que NO exigen token: registrarse, entrar y renovar. Van en su propio
# router, sin la dependencia de autenticacion.
router_publico = APIRouter(prefix="/auth", tags=["Autenticación"])

# Todo lo demas exige token.
router_privado = APIRouter(prefix="/auth", tags=["Autenticación"])


@router_publico.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un usuario nuevo",
)
def registrar(datos: RegistroRequest, db: DbSession) -> TokenResponse:
    return auth_service.registrar(db, datos)


@router_publico.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
)
def iniciar_sesion(datos: LoginRequest, db: DbSession) -> TokenResponse:
    return auth_service.iniciar_sesion(db, datos)


@router_publico.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar el token de acceso",
)
def refrescar(datos: RefreshRequest, db: DbSession) -> TokenResponse:
    return auth_service.refrescar(db, datos.refresh_token)


@router_privado.get(
    "/me",
    response_model=UsuarioOut,
    summary="Datos del usuario autenticado",
)
def usuario_actual(usuario: CurrentUser) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)


@router_privado.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión",
)
def cerrar_sesion(usuario: CurrentUser, db: DbSession) -> dict:
    auth_service.cerrar_sesion(db, usuario)
    return {"mensaje": "Sesión cerrada. Los tokens de refresco fueron revocados."}
