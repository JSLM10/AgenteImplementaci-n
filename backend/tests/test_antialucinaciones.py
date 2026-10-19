"""Las dos barreras que impiden que el agente invente.

1. El umbral de similitud, que descarta fragmentos antes de que el modelo los
   vea.
2. El nodo evaluador, que decide si lo recuperado alcanza para responder.

Si cualquiera de las dos se rompe en silencio, el agente empieza a contestar
preguntas que no puede respaldar y el trabajo pierde su criterio principal.
"""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

from app.agents import nodes
from app.core.config import settings
from app.vectorstore import store


def _doc(texto: str, nombre: str = "futbol.md") -> LCDocument:
    return LCDocument(
        page_content=texto,
        metadata={"nombre_archivo": nombre, "document_id": "abc", "es_publico": True},
    )


class _VectorStoreFalso:
    def __init__(self, resultados):
        self._resultados = resultados

    def similarity_search_with_relevance_scores(self, *_args, **_kwargs):
        return self._resultados


# ─── Umbral de similitud ─────────────────────────────────────────────────────


def test_descarta_los_fragmentos_por_debajo_del_umbral(monkeypatch):
    monkeypatch.setattr(
        store,
        "get_vector_store",
        lambda: _VectorStoreFalso(
            [
                (_doc("Argentina ganó el Mundial de 2022."), 0.81),
                (_doc("El fuera de juego se sanciona…"), 0.42),
                (_doc("Receta de sushi"), 0.09),
            ]
        ),
    )

    fragmentos, mejor = store.buscar_fragmentos("¿Quién ganó el Mundial?", user_id=None)

    assert len(fragmentos) == 2
    assert all(f.score >= settings.RETRIEVAL_MIN_SCORE for f in fragmentos)
    assert mejor == 0.81


def test_si_nada_supera_el_umbral_no_devuelve_contexto(monkeypatch):
    monkeypatch.setattr(
        store,
        "get_vector_store",
        lambda: _VectorStoreFalso([(_doc("Receta de sushi"), 0.11)]),
    )

    fragmentos, mejor = store.buscar_fragmentos("¿Cómo preparo sushi?", user_id=None)

    assert fragmentos == []
    # El mejor score se conserva aunque se descarte: explica el rechazo.
    assert mejor == 0.11


def test_un_fallo_de_la_base_vectorial_no_revienta_la_peticion(monkeypatch):
    class _Roto:
        def similarity_search_with_relevance_scores(self, *_a, **_k):
            raise RuntimeError("la colección no existe")

    monkeypatch.setattr(store, "get_vector_store", lambda: _Roto())

    fragmentos, mejor = store.buscar_fragmentos("lo que sea", user_id=None)

    # Sin contexto, el agente rechaza. Es el comportamiento seguro.
    assert fragmentos == []
    assert mejor == 0.0


# ─── Nodo evaluador ──────────────────────────────────────────────────────────


def test_sin_fragmentos_no_llama_al_modelo(monkeypatch):
    def _explota(*_a, **_k):
        raise AssertionError("no debería invocarse el modelo si no hay fragmentos")

    monkeypatch.setattr(nodes, "_invocar", _explota)

    salida = nodes.evaluar({"pregunta": "¿Quién ganó?", "fragmentos": [], "score_maximo": 0.1})

    assert salida["contexto_suficiente"] is False
    assert "umbral" in salida["motivo_rechazo"]


def test_el_evaluador_distingue_insuficiente_de_suficiente(monkeypatch):
    """'INSUFICIENTE' contiene 'SUFICIENTE': comprobarlo mal invierte el fallo."""
    monkeypatch.setattr(
        nodes,
        "_invocar",
        lambda *_a, **_k: "VEREDICTO: INSUFICIENTE\nMOTIVO: no se menciona el dato",
    )

    salida = nodes.evaluar(
        {
            "pregunta": "¿Cuánto mide el campo?",
            "fragmentos": [{"contenido": "Historia del Mundial", "documento": "a.md"}],
            "contexto": "…",
        }
    )

    assert salida["contexto_suficiente"] is False
    assert salida["motivo_rechazo"] == "no se menciona el dato"


def test_el_evaluador_acepta_un_contexto_suficiente(monkeypatch):
    monkeypatch.setattr(
        nodes,
        "_invocar",
        lambda *_a, **_k: "VEREDICTO: SUFICIENTE\nMOTIVO: el fragmento lo dice",
    )

    salida = nodes.evaluar(
        {
            "pregunta": "¿Quién ganó el Mundial de 2022?",
            "fragmentos": [{"contenido": "Argentina ganó en 2022.", "documento": "a.md"}],
            "contexto": "…",
        }
    )

    assert salida["contexto_suficiente"] is True


def test_si_el_evaluador_falla_se_continua_en_vez_de_rechazar(monkeypatch):
    """Un fallo de infraestructura no debe parecer falta de información."""

    def _falla(*_a, **_k):
        raise RuntimeError("el modelo no responde")

    monkeypatch.setattr(nodes, "_invocar", _falla)

    salida = nodes.evaluar(
        {
            "pregunta": "¿Quién ganó?",
            "fragmentos": [{"contenido": "Argentina ganó en 2022.", "documento": "a.md"}],
            "contexto": "…",
        }
    )

    assert salida["contexto_suficiente"] is True


# ─── Limpieza de la salida del modelo ────────────────────────────────────────


def test_se_elimina_el_bloque_de_razonamiento():
    """Los modelos con razonamiento envuelven su cadena en <think>…</think>."""
    sucio = "<think>El usuario pregunta por el Mundial…</think>Argentina ganó en 2022."
    assert nodes._limpiar(sucio) == "Argentina ganó en 2022."
