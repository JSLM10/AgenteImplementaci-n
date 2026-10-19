"""Los nodos del grafo.

Cada nodo es una funcion pura sobre el estado: recibe el estado completo y
devuelve solo las claves que cambia. Mantenerlos asi es lo que hace que el
grafo sea facil de leer, de probar por separado y de explicar en voz alta.

Los nodos implementan los siete pasos del flujo de referencia del enunciado y,
entre ellos, cinco de las seis estrategias anti-alucinacion. La sexta (el
umbral de similitud) vive en la capa vectorial, antes de que el contexto
llegue siquiera al modelo.
"""

from __future__ import annotations

import logging
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import (
    TOKENS_CLASIFICACION,
    TOKENS_RESPUESTA,
    TOKENS_VEREDICTO,
    get_llm,
)
from app.agents.prompts import (
    MENSAJE_RECHAZO,
    PROMPT_CLASIFICACION,
    PROMPT_EVALUACION,
    PROMPT_REFORMULACION,
    PROMPT_RESPUESTA,
    PROMPT_VERIFICACION,
    RESPUESTA_SALUDO,
    SUGERENCIA_CARGA,
)
from app.agents.state import EstadoAgente
from app.core.config import settings
from app.vectorstore.store import buscar_fragmentos

logger = logging.getLogger(__name__)

# Los modelos con razonamiento explicito (la familia Qwen3, entre otros)
# emiten su cadena de pensamiento envuelta en <think>...</think>. Si no se
# quita, acaba en la respuesta que ve el usuario.
_RE_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _limpiar(texto: str) -> str:
    return _RE_THINK.sub("", texto or "").strip()


def _invocar(prompt: str, max_tokens: int, sistema: str | None = None) -> str:
    mensajes = []
    if sistema:
        mensajes.append(SystemMessage(content=sistema))
    mensajes.append(HumanMessage(content=prompt))
    respuesta = get_llm(max_tokens).invoke(mensajes)
    return _limpiar(str(respuesta.content))


def _formatear_contexto(fragmentos: list[dict], max_caracteres: int | None = None) -> str:
    """Numera los fragmentos para que el modelo pueda citarlos como [1], [2].

    `max_caracteres` recorta cada fragmento. Se usa en el nodo evaluador: en
    CPU, leer el prompt cuesta casi tanto como generar la respuesta, y para
    decidir si un fragmento viene al caso basta con su principio.
    """
    if not fragmentos:
        return "(no se recuperó ningún fragmento)"
    partes = []
    for i, f in enumerate(fragmentos, 1):
        origen = f.get("documento", "documento desconocido")
        pagina = f.get("pagina")
        cabecera = f"[{i}] Fuente: {origen}"
        if pagina is not None:
            cabecera += f", página {pagina}"
        contenido = f.get("contenido", "")
        if max_caracteres is not None and len(contenido) > max_caracteres:
            contenido = contenido[:max_caracteres].rsplit(" ", 1)[0] + "…"
        partes.append(f"{cabecera}\n{contenido}")
    return "\n\n".join(partes)


def _formatear_historial(historial: list, maximo: int) -> str:
    recientes = historial[-maximo:] if maximo > 0 else []
    if not recientes:
        return "(sin historial)"
    lineas = []
    for mensaje in recientes:
        quien = "Usuario" if mensaje.type == "human" else "Asistente"
        lineas.append(f"{quien}: {mensaje.content}")
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 1 — recibir la pregunta y validar su intencion
# ─────────────────────────────────────────────────────────────────────────────
def clasificar(state: EstadoAgente) -> dict:
    pregunta = state["pregunta"]

    # Un mensaje muy corto casi nunca es una pregunta real; resolverlo sin
    # llamar al modelo ahorra un segundo largo en el caso mas comun.
    if len(pregunta.strip()) < 3:
        return {"intencion": "OTRO", "traza": ["clasificar"]}

    try:
        salida = _invocar(
            PROMPT_CLASIFICACION.format(pregunta=pregunta),
            max_tokens=TOKENS_CLASIFICACION,
        ).upper()
    except Exception:
        # Si el modelo no responde, se asume que es una pregunta: es mejor
        # intentar buscar que rechazar por un fallo de infraestructura.
        logger.exception("Fallo la clasificación; se asume PREGUNTA")
        return {"intencion": "PREGUNTA", "traza": ["clasificar"]}

    if "SALUDO" in salida:
        intencion = "SALUDO"
    elif "OTRO" in salida:
        intencion = "OTRO"
    else:
        intencion = "PREGUNTA"

    return {"intencion": intencion, "traza": ["clasificar"]}


def responder_saludo(state: EstadoAgente) -> dict:
    return {
        "respuesta": RESPUESTA_SALUDO,
        "rechazada": False,
        "fuentes": [],
        "traza": ["saludo"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 2 — reformular la pregunta con el historial
# ─────────────────────────────────────────────────────────────────────────────
def reformular(state: EstadoAgente) -> dict:
    pregunta = state["pregunta"]
    historial = state.get("historial") or []

    # Sin historial no hay nada que resolver, y es el caso de la primera
    # pregunta de toda conversacion. Saltarselo ahorra una llamada entera.
    if not historial:
        return {"pregunta_reformulada": pregunta, "traza": ["reformular(omitido)"]}

    try:
        reformulada = _invocar(
            PROMPT_REFORMULACION.format(
                historial=_formatear_historial(historial, settings.MAX_HISTORY_MESSAGES),
                pregunta=pregunta,
            ),
            max_tokens=TOKENS_VEREDICTO,
        )
    except Exception:
        logger.exception("Fallo la reformulación; se usa la pregunta original")
        return {"pregunta_reformulada": pregunta, "traza": ["reformular(error)"]}

    # Un modelo pequeno a veces devuelve una parrafada en vez de una pregunta.
    # Si lo que vuelve no parece una pregunta corta, se descarta.
    reformulada = reformulada.split("\n")[0].strip().strip('"')
    if not reformulada or len(reformulada) > 300:
        reformulada = pregunta

    return {"pregunta_reformulada": reformulada, "traza": ["reformular"]}


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 3 — buscar contexto en la base vectorial
# ─────────────────────────────────────────────────────────────────────────────
def recuperar(state: EstadoAgente) -> dict:
    consulta = state.get("pregunta_reformulada") or state["pregunta"]
    user_id = state.get("user_id")

    fragmentos, mejor_score = buscar_fragmentos(
        consulta,
        user_id=uuid.UUID(user_id) if user_id else None,
    )

    como_dicts = [
        {
            "contenido": f.contenido,
            "documento": f.documento,
            "document_id": f.document_id,
            "pagina": f.pagina,
            "score": f.score,
        }
        for f in fragmentos
    ]

    return {
        "fragmentos": como_dicts,
        "contexto": _formatear_contexto(como_dicts),
        "score_maximo": mejor_score,
        "traza": ["recuperar"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 4 — evaluar si el contexto recuperado alcanza
# ─────────────────────────────────────────────────────────────────────────────
def evaluar(state: EstadoAgente) -> dict:
    fragmentos = state.get("fragmentos") or []

    # Si el umbral de similitud ya descarto todo, no hace falta preguntarle al
    # modelo: no hay nada que evaluar.
    if not fragmentos:
        return {
            "contexto_suficiente": False,
            "motivo_rechazo": (
                f"Ningún fragmento superó el umbral de similitud "
                f"({settings.RETRIEVAL_MIN_SCORE}); mejor coincidencia: "
                f"{state.get('score_maximo', 0.0):.3f}."
            ),
            "traza": ["evaluar(sin fragmentos)"],
        }

    try:
        salida = _invocar(
            PROMPT_EVALUACION.format(
                pregunta=state.get("pregunta_reformulada") or state["pregunta"],
                contexto=_formatear_contexto(fragmentos, max_caracteres=420),
            ),
            max_tokens=TOKENS_VEREDICTO,
        )
    except Exception:
        # Ante un fallo del evaluador se deja pasar: ya hay fragmentos que
        # superaron el umbral, y el prompt de generacion sigue siendo estricto.
        logger.exception("Fallo la evaluación de contexto; se continúa")
        return {"contexto_suficiente": True, "traza": ["evaluar(error)"]}

    normalizada = salida.upper()
    # El orden importa: "INSUFICIENTE" contiene "SUFICIENTE" como subcadena.
    suficiente = "INSUFICIENTE" not in normalizada

    motivo = ""
    for linea in salida.splitlines():
        if linea.upper().startswith("MOTIVO:"):
            motivo = linea.split(":", 1)[1].strip()
            break

    return {
        "contexto_suficiente": suficiente,
        "motivo_rechazo": motivo or "El evaluador consideró el contexto insuficiente.",
        "traza": ["evaluar"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 5 — generar la respuesta a partir del contexto
# ─────────────────────────────────────────────────────────────────────────────
def generar(state: EstadoAgente) -> dict:
    fragmentos = state.get("fragmentos") or []

    try:
        respuesta = _invocar(
            PROMPT_RESPUESTA.format(
                contexto=state.get("contexto", ""),
                pregunta=state.get("pregunta_reformulada") or state["pregunta"],
                mensaje_rechazo=MENSAJE_RECHAZO,
            ),
            max_tokens=TOKENS_RESPUESTA,
        )
    except Exception:
        logger.exception("Fallo la generación de la respuesta")
        return {
            "respuesta": (
                "Hubo un problema al generar la respuesta con el modelo local. "
                "Comprueba que el servicio del modelo esté disponible e inténtalo de nuevo."
            ),
            "rechazada": True,
            "fuentes": [],
            "traza": ["generar(error)"],
        }

    # El propio modelo puede concluir que no le alcanza y devolver la frase de
    # rechazo. Si lo hace, se respeta y se marca como rechazo de verdad, para
    # que el historial y la interfaz lo muestren como tal.
    if MENSAJE_RECHAZO.lower() in respuesta.lower():
        return {
            "respuesta": MENSAJE_RECHAZO + SUGERENCIA_CARGA,
            "rechazada": True,
            "fuentes": [],
            "traza": ["generar(autorrechazo)"],
        }

    fuentes = [
        {
            "documento": f["documento"],
            "document_id": f["document_id"],
            "pagina": f["pagina"],
            "score": round(f["score"], 4),
            "extracto": _extracto(f["contenido"]),
        }
        for f in fragmentos
    ]

    return {
        "respuesta": respuesta,
        "rechazada": False,
        "fuentes": fuentes,
        "traza": ["generar"],
    }


def _extracto(contenido: str, maximo: int = 320) -> str:
    texto = (contenido or "").strip().replace("\n", " ")
    if len(texto) <= maximo:
        return texto
    return texto[:maximo].rsplit(" ", 1)[0] + "…"


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 6 — verificar que la respuesta se sostiene en el contexto
# ─────────────────────────────────────────────────────────────────────────────
def verificar(state: EstadoAgente) -> dict:
    if not settings.ENABLE_GROUNDEDNESS_CHECK:
        return {"traza": ["verificar(desactivado)"]}

    try:
        salida = _invocar(
            PROMPT_VERIFICACION.format(
                contexto=state.get("contexto", ""),
                respuesta=state.get("respuesta", ""),
            ),
            max_tokens=TOKENS_CLASIFICACION,
        ).upper()
    except Exception:
        logger.exception("Fallo la verificación; se mantiene la respuesta")
        return {"traza": ["verificar(error)"]}

    # Solo se degrada ante un NO explicito: un verificador que falla no debe
    # tumbar una respuesta que ya paso el umbral y al evaluador.
    if salida.startswith("NO") or " NO" in f" {salida}":
        logger.warning("La verificación rechazó la respuesta generada")
        return {
            "respuesta": MENSAJE_RECHAZO + SUGERENCIA_CARGA,
            "rechazada": True,
            "fuentes": [],
            "traza": ["verificar(rechazada)"],
        }

    return {"traza": ["verificar"]}


# ─────────────────────────────────────────────────────────────────────────────
# Nodo 7 — rechazar explicitamente
# ─────────────────────────────────────────────────────────────────────────────
def rechazar(state: EstadoAgente) -> dict:
    motivo = state.get("motivo_rechazo", "")
    if motivo:
        logger.info("Pregunta rechazada: %s", motivo)

    if state.get("intencion") == "OTRO":
        mensaje = (
            "No he entendido la pregunta. Formúlala de otra manera y buscaré en "
            "los documentos de mi base de conocimiento."
        )
    else:
        mensaje = MENSAJE_RECHAZO + SUGERENCIA_CARGA

    return {
        "respuesta": mensaje,
        "rechazada": True,
        "fuentes": [],
        "traza": ["rechazar"],
    }
