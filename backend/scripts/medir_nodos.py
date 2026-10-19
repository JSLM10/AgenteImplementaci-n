"""Cronometra cada nodo del grafo por separado, para saber donde se va el tiempo."""

import logging
import sys
import time

logging.basicConfig(level=logging.WARNING)

from app.agents import nodes  # noqa: E402
from app.core.config import settings  # noqa: E402

PREGUNTA = "¿Quién ganó el Mundial de 2022?"


def cronometrar(etiqueta, fn, *args):
    inicio = time.perf_counter()
    salida = fn(*args)
    segundos = time.perf_counter() - inicio
    print(f"  {etiqueta:<14} {segundos:6.1f}s", flush=True)
    return salida, segundos


def main():
    print(f"Modelo: {settings.OLLAMA_MODEL}  k={settings.RETRIEVAL_K}", flush=True)
    print(f"Pregunta: {PREGUNTA}\n", flush=True)

    # Dos pasadas: la primera carga el modelo de embeddings y el de Ollama en
    # memoria, la segunda es la que representa el coste real por pregunta.
    for pasada in (1, 2):
        print(f"--- pasada {pasada} {'(en frio)' if pasada == 1 else '(en caliente)'} ---", flush=True)
        _una_pasada()
        print(flush=True)
    return 0


def _una_pasada():
    estado = {"user_id": "", "conversation_id": "", "pregunta": PREGUNTA, "historial": []}
    total = 0.0

    salida, s = cronometrar("clasificar", nodes.clasificar, estado)
    estado.update(salida)
    total += s
    print(f"     intencion={estado.get('intencion')}", flush=True)

    salida, s = cronometrar("reformular", nodes.reformular, estado)
    estado.update(salida)
    total += s

    salida, s = cronometrar("recuperar", nodes.recuperar, estado)
    estado.update(salida)
    total += s
    print(
        f"     {len(estado.get('fragmentos') or [])} fragmentos,"
        f" {len(estado.get('contexto') or '')} caracteres de contexto",
        flush=True,
    )

    salida, s = cronometrar("evaluar", nodes.evaluar, estado)
    estado.update(salida)
    total += s
    print(f"     suficiente={estado.get('contexto_suficiente')}", flush=True)

    if estado.get("contexto_suficiente"):
        salida, s = cronometrar("generar", nodes.generar, estado)
        estado.update(salida)
        total += s

    print(f"  {'TOTAL':<14} {total:6.1f}s", flush=True)
    print(f"  Respuesta: {(estado.get('respuesta') or '')[:300]}", flush=True)
    fuentes = estado.get("fuentes") or []
    if fuentes:
        print("  Fuentes:", ", ".join(f["documento"] for f in fuentes), flush=True)


if __name__ == "__main__":
    sys.exit(main())
