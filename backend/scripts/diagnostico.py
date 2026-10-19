"""Diagnostico de recuperacion y evaluacion.

Para cada pregunta muestra que fragmentos se recuperaron, con que score, y que
contesto exactamente el nodo evaluador. Sirve para distinguir un fallo de
recuperacion (no encuentra) de un fallo de evaluacion (encuentra pero lo
descarta).

    uv run python -u -m scripts.diagnostico
"""

from __future__ import annotations

import logging
import sys
import uuid

logging.basicConfig(level=logging.WARNING)

from sqlalchemy import select  # noqa: E402

from app.agents import nodes  # noqa: E402
from app.agents.llm import TOKENS_VEREDICTO, get_llm  # noqa: E402
from app.agents.prompts import PROMPT_EVALUACION  # noqa: E402
from app.db.models import Document  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.vectorstore.store import buscar_fragmentos  # noqa: E402

PREGUNTAS = [
    "¿Qué pasó en el Maracanazo?",
    "¿Qué es el fuera de juego?",
    "¿Quién ganó el Mundial de 2022?",
]


def dueno_del_acta() -> uuid.UUID | None:
    """Usuario que subió el acta de demostración, si está cargada."""
    with SessionLocal() as db:
        doc = db.scalar(
            select(Document)
            .where(Document.nombre_archivo.like("acta-club%"))
            .order_by(Document.creado_en.desc())
        )
        if doc is None:
            return None
        print(
            f"Acta encontrada: {doc.nombre_archivo} | estado={doc.estado} | "
            f"fragmentos={doc.num_fragmentos} | publico={doc.es_publico} | "
            f"owner={doc.owner_id}"
        )
        return doc.owner_id


def revisar(pregunta: str, user_id: uuid.UUID | None) -> None:
    print(f"\n{'=' * 74}\n{pregunta}\n{'=' * 74}")

    fragmentos, mejor = buscar_fragmentos(pregunta, user_id=user_id)
    print(f"mejor score: {mejor:.3f} | aceptados: {len(fragmentos)}")
    for f in fragmentos:
        print(f"  [{f.score:.3f}] {f.documento}: {f.contenido[:110].replace(chr(10), ' ')}…")

    if not fragmentos:
        print("  -> sin fragmentos: el rechazo viene del umbral")
        return

    contexto = nodes._formatear_contexto(
        [
            {
                "contenido": f.contenido,
                "documento": f.documento,
                "document_id": f.document_id,
                "pagina": f.pagina,
                "score": f.score,
            }
            for f in fragmentos
        ],
        max_caracteres=420,
    )
    salida = get_llm(TOKENS_VEREDICTO).invoke(
        PROMPT_EVALUACION.format(pregunta=pregunta, contexto=contexto)
    )
    print(f"  evaluador dice: {nodes._limpiar(str(salida.content))!r}")


def main() -> int:
    owner = dueno_del_acta()

    for pregunta in PREGUNTAS:
        revisar(pregunta, user_id=None)

    if owner is not None:
        print(f"\n\n### Con el usuario dueño del acta ({owner}) ###")
        revisar("¿Quién es el máximo goleador del Club La Quebrada?", user_id=owner)
        revisar("¿Cuánto se multa por llegar tarde al entrenamiento?", user_id=owner)

    return 0


if __name__ == "__main__":
    sys.exit(main())
