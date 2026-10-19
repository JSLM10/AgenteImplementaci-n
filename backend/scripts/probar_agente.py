"""Prueba de humo del agente, sin pasar por la API.

Ejecuta el grafo contra un conjunto de preguntas que cubren los tres
comportamientos que exige el enunciado: responder con fundamento, rechazar por
falta de información y atender la conversación social. Mide además el tiempo
de cada respuesta, que es el dato que decide si la demo en vivo es viable.

    uv run python -m scripts.probar_agente
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")

from app.agents.graph import get_agente  # noqa: E402
from app.core.config import settings  # noqa: E402

# (pregunta, se espera rechazo)
CASOS: list[tuple[str, bool]] = [
    ("Hola, buenas tardes", False),
    ("¿Quién ganó el Mundial de 2022?", False),
    ("¿Cuántos Balones de Oro tiene Messi?", False),
    ("¿Qué pasó en el Maracanazo?", False),
    ("¿Cuándo ganó Colombia la Copa América?", False),
    ("¿Qué es el fuera de juego?", False),
    ("¿Cuál es la mejor receta para preparar sushi?", True),
    ("¿Quién ganó el Mundial de 2026?", True),
    ("¿Cuánto cuesta un Tesla Model 3?", True),
]

VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[93m"
GRIS = "\033[90m"
FIN = "\033[0m"


def main() -> int:
    print("=" * 78)
    print(f"  Modelo: {settings.OLLAMA_MODEL}   Proveedor: {settings.LLM_PROVIDER}")
    print(f"  Umbral de similitud: {settings.RETRIEVAL_MIN_SCORE}   k={settings.RETRIEVAL_K}")
    print(f"  Verificación posterior: {settings.ENABLE_GROUNDEDNESS_CHECK}")
    print("=" * 78)

    agente = get_agente()
    tiempos: list[float] = []
    aciertos = 0

    for pregunta, espera_rechazo in CASOS:
        inicio = time.perf_counter()
        estado = agente.invoke(
            {
                "user_id": "",
                "conversation_id": "",
                "pregunta": pregunta,
                "historial": [],
                "traza": [],
            }
        )
        duracion = time.perf_counter() - inicio
        tiempos.append(duracion)

        rechazada = bool(estado.get("rechazada"))
        # Un saludo no es ni respuesta fundamentada ni rechazo; se da por bueno.
        es_saludo = "saludo" in (estado.get("traza") or [])
        correcto = es_saludo or rechazada == espera_rechazo
        aciertos += int(correcto)

        marca = f"{VERDE}[OK]{FIN}" if correcto else f"{ROJO}[XX]{FIN}"
        etiqueta = (
            f"{AMARILLO}RECHAZO{FIN}"
            if rechazada
            else (f"{GRIS}SALUDO{FIN}" if es_saludo else f"{VERDE}RESPUESTA{FIN}")
        )

        print(f"\n{marca} [{duracion:5.1f}s] {etiqueta}  {pregunta}")
        print(f"   {GRIS}{' -> '.join(estado.get('traza') or [])}{FIN}")

        respuesta = (estado.get("respuesta") or "").replace("\n", " ")
        print(f"   {respuesta[:240]}{'...' if len(respuesta) > 240 else ''}")

        fuentes = estado.get("fuentes") or []
        if fuentes:
            resumen = ", ".join(f"{f['documento']} ({f['score']:.2f})" for f in fuentes[:3])
            print(f"   {GRIS}Fuentes: {resumen}{FIN}")

    print("\n" + "=" * 78)
    print(f"  Aciertos: {aciertos}/{len(CASOS)}")
    print(
        f"  Tiempo — media {sum(tiempos) / len(tiempos):.1f}s, "
        f"máximo {max(tiempos):.1f}s, mínimo {min(tiempos):.1f}s"
    )
    print("=" * 78)

    return 0 if aciertos == len(CASOS) else 1


if __name__ == "__main__":
    sys.exit(main())
