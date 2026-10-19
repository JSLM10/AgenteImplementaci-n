"""Prompts del agente.

El prompt de generacion es la tercera estrategia anti-alucinacion: prohibe
explicitamente el conocimiento externo y obliga a citar el fragmento del que
sale cada afirmacion. Las instrucciones estan en espanol porque el corpus y
las preguntas lo estan, y mezclar idiomas empeora el seguimiento de
instrucciones en modelos pequenos.
"""

from __future__ import annotations

# El enunciado del trabajo exige este texto literal cuando no hay informacion
# suficiente. No cambiarlo sin cambiar tambien el documento tecnico.
MENSAJE_RECHAZO = (
    "No tengo suficiente información en mi base de conocimiento para responder esa pregunta."
)

SUGERENCIA_CARGA = (
    " Si quieres que pueda responderla, sube un documento relacionado con el tema "
    "desde la sección de Documentos y vuelve a preguntarme."
)

RESPUESTA_SALUDO = (
    "¡Hola! Soy VAR, un asistente que responde únicamente con información tomada de los "
    "documentos de su base de conocimiento. De base sé de fútbol: mundiales, competiciones, "
    "reglas y jugadores. Si subes tus propios documentos, también podré responder sobre ellos. "
    "¿Qué quieres saber?"
)

# ─────────────────────────────────────────────────────────────────────────────
# Nodo 1 — clasificar la intencion
# ─────────────────────────────────────────────────────────────────────────────
# Deliberadamente NO se le pide al modelo que decida si la pregunta esta
# "dentro del tema": eso lo decide la busqueda vectorial, no la opinion previa
# del modelo. Aqui solo se separa la conversacion social de las preguntas.
PROMPT_CLASIFICACION = """\
Clasifica el mensaje del usuario en UNA de estas tres categorías y responde \
solo con la palabra, sin explicar nada:

SALUDO    — saludos, despedidas, agradecimientos o cortesía.
PREGUNTA  — cualquier petición de información, dato, explicación o resumen.
OTRO      — insultos, texto sin sentido o mensajes vacíos de contenido.

Mensaje: {pregunta}

Categoría:"""

# ─────────────────────────────────────────────────────────────────────────────
# Nodo 2 — reformular con el historial
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_REFORMULACION = """\
Reescribe la última pregunta del usuario para que se entienda por sí sola, \
sin necesidad del historial de la conversación. Resuelve los pronombres y las \
referencias implícitas ("ese equipo", "él", "ahí") usando el historial.

NO respondas la pregunta. Devuelve solo la pregunta reescrita, en una línea. \
Si ya se entiende por sí sola, devuélvela sin cambios.

Historial:
{historial}

Última pregunta: {pregunta}

Pregunta reescrita:"""

# ─────────────────────────────────────────────────────────────────────────────
# Nodo 4 — evaluar si el contexto alcanza
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_EVALUACION = """\
Decide si los fragmentos recuperados permiten responder la pregunta.

Responde EXACTAMENTE en este formato, en dos líneas:
VEREDICTO: SUFICIENTE o INSUFICIENTE
MOTIVO: una frase corta

Criterios:
- SUFICIENTE si los fragmentos contienen el dato que se pide, aunque sea de \
forma parcial, indirecta o con otras palabras. No exijas que la pregunta \
aparezca formulada igual.
- INSUFICIENTE solo si los fragmentos tratan de otro asunto, o si hablan del \
tema general sin contener en ningún momento el dato concreto.

Ante la duda, marca SUFICIENTE: quien redacta la respuesta tiene prohibido \
salirse de estos fragmentos, así que un contexto flojo produce una respuesta \
corta, no una inventada.

Pregunta: {pregunta}

Fragmentos:
{contexto}

Tu evaluación:"""

# ─────────────────────────────────────────────────────────────────────────────
# Nodo 5 — generar la respuesta
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_RESPUESTA = """\
Eres VAR, un asistente de consulta documental.

REGLAS, en orden de prioridad:
1. Responde ÚNICAMENTE con información contenida en los fragmentos de abajo.
2. Está prohibido usar conocimiento propio, suposiciones o datos que no estén \
en los fragmentos, aunque creas saber la respuesta.
3. Cita el número del fragmento del que sale cada afirmación, así: [1], [2].
4. Si los fragmentos no contienen la respuesta, responde exactamente esta \
frase y nada más: {mensaje_rechazo}
5. Responde en español, de forma directa y sin rodeos. No repitas la pregunta \
ni anuncies lo que vas a hacer.

Fragmentos recuperados:
{contexto}

Pregunta: {pregunta}

Respuesta:"""

# ─────────────────────────────────────────────────────────────────────────────
# Nodo 6 — verificar que la respuesta se sostiene en el contexto
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_VERIFICACION = """\
Comprueba si la respuesta se apoya por completo en los fragmentos.

Responde solo con una palabra:
SI   — todo lo que afirma la respuesta aparece en los fragmentos.
NO   — la respuesta afirma algo que no aparece en los fragmentos.

Fragmentos:
{contexto}

Respuesta a comprobar: {respuesta}

Veredicto:"""
