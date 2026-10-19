"""Que ningún endpoint quede expuesto sin autenticación.

El enunciado lo exige de forma explícita, y es el tipo de fallo que no se nota
hasta que alguien lo prueba: la aplicación arranca igual de bien con un
endpoint abierto. Por eso se comprueba en una prueba y, además, al arrancar.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import RUTAS_PUBLICAS, app, auditar_rutas
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)

cliente = TestClient(app)


def test_ninguna_ruta_privada_queda_sin_autenticacion():
    desprotegidas = auditar_rutas(app)
    assert desprotegidas == [], (
        "Estos endpoints no exigen token y no están en la lista de rutas "
        f"públicas: {desprotegidas}"
    )


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("post", "/api/chat"),
        ("get", "/api/conversations"),
        ("get", "/api/documents"),
        ("post", "/api/documents"),
        ("get", "/api/auth/me"),
        ("post", "/api/auth/logout"),
    ],
)
def test_sin_token_responde_401(metodo: str, ruta: str):
    respuesta = getattr(cliente, metodo)(ruta)
    assert respuesta.status_code == 401


def test_token_invalido_responde_401():
    respuesta = cliente.get(
        "/api/auth/me", headers={"Authorization": "Bearer esto-no-es-un-token"}
    )
    assert respuesta.status_code == 401


def test_las_rutas_publicas_son_las_esperadas():
    """La lista de rutas públicas es corta y cerrada a propósito.

    Si alguien la amplía, esta prueba falla y obliga a justificarlo.
    """
    assert RUTAS_PUBLICAS == frozenset(
        {
            "/api/health",
            "/api/health/grafo",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/refresh",
        }
    )


def test_un_refresh_token_no_sirve_como_access_token():
    """Sin esta comprobación, un refresh robado valdría durante días."""
    refresh, _, _ = create_refresh_token("11111111-1111-1111-1111-111111111111")

    with pytest.raises(TokenError):
        decode_token(refresh, expected_type="access")


def test_un_access_token_valido_se_decodifica():
    access, _ = create_access_token(
        "11111111-1111-1111-1111-111111111111", "alguien@ejemplo.com"
    )
    datos = decode_token(access, expected_type="access")
    assert datos["sub"] == "11111111-1111-1111-1111-111111111111"
    assert datos["type"] == "access"
