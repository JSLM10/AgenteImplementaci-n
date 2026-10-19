# VAR — Verificador Aumentado de Respuestas

### Documento técnico

**Asignatura:** Implementación e Integración de Software
**Equipo:** Juan Pablo Muñoz · Gabriel Giraldo · Luis Brito
**Repositorio:** *(enlace público de GitHub)*
**Fecha:** octubre de 2026

---

## 1. Nombre del proyecto e integrantes

**VAR — Verificador Aumentado de Respuestas.**

El nombre no es un acrónimo forzado: describe lo que hace el sistema. El videoarbitraje
del fútbol revisa la evidencia disponible antes de confirmar o corregir una decisión y,
cuando las imágenes no son concluyentes, no cambia nada. El agente de este trabajo opera
igual: recupera evidencia de su base de conocimiento, la evalúa y solo responde si
alcanza. Si no, lo dice.

| Integrante |
|---|
| Juan Pablo Muñoz |
| Gabriel Giraldo |
| Luis Brito |

---

## 2. Tema seleccionado y descripción del problema

### El tema

**Fútbol**, con una base de conocimiento ampliable a cualquier dominio.

La base inicial cubre historia de los Mundiales, Copa Libertadores, Liga de Campeones,
Copa América, Balón de Oro, Selección Colombia, reglas del juego, táctica y clásicos.
Son ocho documentos curados que llegan hasta el Mundial de 2022.

### El problema

Un modelo de lenguaje, preguntado sobre cualquier cosa, contesta. Casi siempre con
aplomo, a veces con datos inventados, y sin que el usuario pueda distinguir una respuesta
fundamentada de una fabricada. En un dominio con tantos datos verificables como el
fútbol — marcadores, fechas, palmarés — ese fallo es inmediato y evidente.

El sistema resuelve dos cosas a la vez:

1. **Responder con trazabilidad.** Cada afirmación procede de un fragmento concreto de un
   documento concreto, y el usuario puede verlo.
2. **Aprender de documentos nuevos.** Cualquier archivo que se suba pasa a formar parte
   de lo que el agente puede consultar. Si un documento afirma algo, el agente lo
   responde citándolo; si ningún documento lo respalda, se niega.

Lo segundo es lo que convierte el trabajo en una herramienta y no en una demostración:
la base de fútbol es el punto de partida, no el límite.

### Caso límite elegido a propósito

La base llega hasta 2022. Preguntar por el Mundial de 2026 produce un rechazo legítimo,
no un fallo. Ese mismo rechazo se convierte después en la demostración de aprendizaje:
se sube un documento, se repite la pregunta y el agente ya responde.

---

## 3. Arquitectura general

```
                        Usuario
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Frontend — React + Vite + Tailwind  │
        │  Login · Chat · Documentos           │
        └───────────────┬──────────────────────┘
                        │  HTTPS + JWT en cada petición
                        ▼
        ┌──────────────────────────────────────┐
        │  API FastAPI protegida               │
        │  ──────────────────────────────────  │
        │  Autenticación   (JWT / Keycloak)    │
        │  Gestión de usuarios                 │
        │  Carga de archivos                   │
        │  Procesamiento de documentos         │
        │  Agente LangGraph                    │
        └───────┬──────────────────────┬───────┘
                │                      │
                ▼                      ▼
   ┌────────────────────┐   ┌──────────────────────────┐
   │  Modelo local      │   │  PostgreSQL 16           │
   │  Ollama            │   │  ├── usuarios            │
   │  o Transformers    │   │  ├── conversaciones      │
   │                    │   │  ├── mensajes            │
   │                    │   │  ├── documentos          │
   │                    │   │  └── pgvector embeddings │
   └────────────────────┘   └──────────────────────────┘
```

Una sola base de datos guarda tanto los datos relacionales como los vectores. Reduce
piezas móviles y permite borrar un documento y sus fragmentos en la misma operación
lógica.

### Flujo de una pregunta

1. El frontend envía la pregunta con el token en la cabecera `Authorization`.
2. La dependencia de autenticación resuelve el usuario o devuelve 401.
3. El servicio del agente recupera o crea la conversación y carga el historial reciente.
4. Se invoca el grafo compilado de LangGraph.
5. El grafo devuelve la respuesta, las fuentes y la traza de nodos recorridos.
6. La interacción se guarda en el historial dentro del propio grafo.

---

## 4. Tecnologías utilizadas

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend | FastAPI | Validación con Pydantic, documentación automática, inyección de dependencias que encaja con el modelo de seguridad |
| Lenguaje | Python 3.12 | Fijado con `uv`. El equipo tenía Python 3.14, demasiado nuevo para PyTorch |
| Gestor | uv | Resuelve e instala en segundos y gestiona la versión de Python |
| Agente | LangChain + LangGraph | Exigidos por el enunciado |
| Modelo local | Ollama · `qwen3.5:4b` | Servidor ya instalado, modelo cargado y residente entre peticiones |
| Alternativa | HuggingFace Transformers | Para la nube, donde no hay un Ollama al lado |
| Embeddings | `intfloat/multilingual-e5-small` | Multilingüe, 384 dimensiones, 118 MB, rápido en CPU |
| Base vectorial | PostgreSQL 16 + pgvector | Una sola base para todo; `langchain-postgres` lo integra |
| ORM | SQLAlchemy 2 | Tipado moderno con `Mapped[...]` |
| Autenticación | bcrypt + PyJWT | Sin servicios externos en el camino crítico |
| Alternativa | Keycloak 26 | Validación OIDC RS256, conmutable por variable de entorno |
| Frontend | React 19 + Vite + TypeScript | — |
| Estilos | Tailwind v4 | Tokens en `@theme`, sin archivo de configuración |
| Animación | Motion | Transiciones de la interfaz; el orbe usa su propio motor sobre canvas |
| Contenedores | Docker Compose | Un comando levanta base de datos, backend, frontend y los perfiles opcionales |

---

## 5. Descripción del backend

### Organización

```
app/
├── main.py          montaje de routers y auditoría de seguridad
├── core/            configuración, seguridad, dependencias
├── api/routes/      controladores: auth, chat, documents, health
├── services/        lógica de negocio
├── agents/          grafo, nodos, prompts, estado, proveedor de modelo
├── vectorstore/     embeddings y búsqueda con umbral
├── db/              modelos SQLAlchemy y sesión
└── schemas/         modelos Pydantic de entrada y salida
```

La separación se sostiene en una regla: **un controlador no construye prompts ni abre
conexiones a la base vectorial, y un nodo del agente no sabe que existe HTTP.** Por eso
el nodo que guarda el historial abre su propia sesión de base de datos en vez de recibir
la de la petición.

### Endpoints

| Método | Ruta | Token | Qué hace |
|---|---|:---:|---|
| `GET` | `/api/health` | — | Estado del servicio y configuración activa |
| `GET` | `/api/health/grafo` | — | Diagrama Mermaid del grafo compilado |
| `POST` | `/api/auth/register` | — | Alta de usuario |
| `POST` | `/api/auth/login` | — | Inicio de sesión |
| `POST` | `/api/auth/refresh` | — | Renovación con rotación del refresh |
| `GET` | `/api/auth/me` | ✔ | Datos del usuario |
| `POST` | `/api/auth/logout` | ✔ | Revoca los refresh tokens |
| `POST` | `/api/chat` | ✔ | Pregunta al agente |
| `GET` | `/api/conversations` | ✔ | Lista de conversaciones |
| `GET` | `/api/conversations/{id}` | ✔ | Historial completo |
| `DELETE` | `/api/conversations/{id}` | ✔ | Elimina una conversación |
| `POST` | `/api/documents` | ✔ | Sube un documento |
| `GET` | `/api/documents` | ✔ | Documentos propios y comunes |
| `GET` | `/api/documents/{id}` | ✔ | Estado de procesamiento |
| `DELETE` | `/api/documents/{id}` | ✔ | Borra documento y fragmentos |

### Modelo de datos

| Tabla | Contenido |
|---|---|
| `users` | Cuenta, hash bcrypt, `external_id` para Keycloak |
| `refresh_tokens` | Tokens emitidos con su `jti` y marca de revocación |
| `conversations` | Hilos por usuario |
| `messages` | Mensajes, con `rechazada` y `fuentes` en JSONB |
| `documents` | Archivos, estado, número de fragmentos, visibilidad |
| `langchain_pg_*` | Colección y embeddings, creadas por `langchain-postgres` |

### Manejo de errores

Tres capas. Pydantic valida la entrada y devuelve 422 con los campos concretos. Los
servicios lanzan `HTTPException` con códigos adecuados. Un manejador global registra la
traza de cualquier excepción no prevista y devuelve un mensaje neutro, sin filtrar rutas
del sistema ni fragmentos de configuración.

---

## 6. Descripción del frontend

React 19 con Vite, TypeScript, Tailwind v4 y Motion.

### Pantallas

| Ruta | Contenido |
|---|---|
| `/entrar` | Registro e inicio de sesión, con validación en cliente |
| `/` | Chat. Con la conversación vacía, el orbe ocupa el centro |
| `/conversacion/:id` | Hilo con su historial |
| `/documentos` | Subida con arrastrar y soltar, lista con estado, borrado |

### Dirección visual

El vocabulario viene del fútbol, no del género «aplicación de IA»: fondo de césped
nocturno, estructura trazada con líneas de tiza en lugar de tarjetas con sombra,
tipografía condensada de dorsal y marcador (Barlow Condensed) sobre un cuerpo de texto
técnico (IBM Plex Sans). El color está reservado para los estados — ámbar mientras se
procesa, esmeralda cuando hay respuesta fundamentada, rojo cuando se rechaza — en vez de
usarse como decoración.

### El orbe

El componente `MorphOrb` anima una píldora de entrada que vuela al centro de la pantalla,
se convierte en una esfera de partículas dibujada sobre canvas, y al terminar se despliega
en una tarjeta de respuesta. Está construido para **una** pregunta y **una** respuesta.

Por eso se usa como pantalla de bienvenida del chat y no como el chat entero: forzarlo a
representar un hilo lo rompería. Su animación de espera corre mientras el agente trabaja
de verdad, y sus etiquetas — *Pensando, Buscando, Evaluando, Redactando* — siguen los
nodos reales del grafo. Cuando llega la respuesta, el usuario pasa al hilo, que ya
contiene el intercambio.

El componente llegó sin su hoja de estilos: solo traía los `@keyframes`, sin ninguna de
las clases `.mo-*` que usa. Hubo que escribir la hoja completa — unas 400 líneas — a
partir de las variables CSS que el componente escribe fotograma a fotograma.

### Elementos propios del dominio

- **Fuentes desplegables** bajo cada respuesta, con documento, página y porcentaje de
  similitud de cada fragmento.
- **Traza del grafo** bajo cada respuesta: los nodos recorridos y el tiempo total. En la
  sustentación permite enseñar que una pregunta rechazada nunca pasó por `generar`.

---

## 7. Descripción del agente y del flujo de LangGraph

### El grafo

```
START
  │
  ▼
clasificar ──── SALUDO ──────────────────────► saludo ─────────┐
  │                                                            │
  ├──────────── OTRO ───────────────────────► rechazar ────────┤
  │                                                │           │
  └──────────── PREGUNTA                           │           │
                 │                                 │           │
                 ▼                                 │           │
            reformular                             │           │
                 │                                 │           │
                 ▼                                 │           │
            recuperar                              │           │
                 │                                 │           │
                 ▼                                 │           │
             evaluar ──── insuficiente ────────────┘           │
                 │                                             │
            suficiente                                         │
                 │                                             │
                 ▼                                             │
              generar                                          │
                 │                                             │
                 ▼                                             │
             verificar ────────────────────────────────────────┤
                                                               │
                                                               ▼
                                                          historial
                                                               │
                                                               ▼
                                                              END
```

Siete nodos y dos aristas condicionales. El diagrama real, generado por LangGraph a
partir del grafo compilado, se obtiene en `GET /api/health/grafo`.

### Estado compartido

```python
class EstadoAgente(TypedDict, total=False):
    user_id: str
    conversation_id: str
    pregunta: str
    historial: list[BaseMessage]
    intencion: Literal["SALUDO", "PREGUNTA", "OTRO"]
    pregunta_reformulada: str
    fragmentos: list[dict]
    contexto: str
    score_maximo: float
    contexto_suficiente: bool
    motivo_rechazo: str
    respuesta: str
    fuentes: list[dict]
    rechazada: bool
    traza: Annotated[list[str], operator.add]
```

`traza` lleva un reductor (`operator.add`) para que cada nodo **añada** su nombre en vez
de sobrescribir la lista. Es lo que permite mostrar el camino recorrido.

### Los nodos

**1. `clasificar`.** Separa saludo, pregunta y mensaje sin contenido. Deliberadamente
**no** se le pide al modelo que juzgue si la pregunta «es del tema»: eso lo decide la
búsqueda vectorial con evidencia, no la opinión previa del modelo. Presupuesto: 8 tokens.

**2. `reformular`.** Resuelve pronombres y referencias implícitas usando el historial. Se
omite cuando no hay historial, que es el caso de toda primera pregunta: ahorra una
llamada completa al modelo.

**3. `recuperar`.** Búsqueda por similitud coseno sobre pgvector, filtrada por
visibilidad y recortada por umbral.

**4. `evaluar`.** Pide al modelo un veredicto estructurado sobre si los fragmentos bastan.
Si el umbral ya descartó todo, ni siquiera llama al modelo.

**5. `generar`.** Redacta usando solo el contexto, citando `[1]`, `[2]`. Si el propio
modelo concluye que no le alcanza y devuelve la frase de rechazo, se respeta y se marca
como rechazo real.

**6. `verificar`.** Comprueba que la respuesta no afirme nada que no esté en el contexto.
Opcional: duplica el coste de inferencia.

**7. `historial`.** Persiste la interacción. Los tres finales posibles convergen aquí:
toda interacción se guarda, responda o rechace.

### Decisión de diseño: por qué no `create_react_agent`

LangGraph ofrece un agente ReAct prefabricado en una línea. Se descartó por dos razones.
La primera es que delega en el modelo la decisión de si buscar o no, y un modelo pequeño
a menudo decide responder de memoria — justo el fallo que el trabajo quiere evitar. En
este grafo la búsqueda **no es opcional**: toda pregunta pasa por `recuperar`. La segunda
es que un agente prefabricado no evidencia dominio de la herramienta.

---

## 8. Modelo local utilizado y base de datos vectorial

### El modelo de chat

**Ollama con `qwen3.5:4b`**, ejecutado en la máquina del equipo.

El proveedor es conmutable mediante `LLM_PROVIDER`:

| Valor | Implementación | Dónde se usa |
|---|---|---|
| `ollama` | `ChatOllama` contra el servidor local | Desarrollo y demostración |
| `huggingface` | `transformers` dentro del proceso | Despliegue en la nube |

Ambos son modelos locales. En ningún caso se llama a una API comercial.

#### Por qué este modelo

Se midieron los dos modelos disponibles en el equipo, con el mismo prompt corto:

| Modelo | Tamaño | Velocidad | Resultado |
|---|---|---|---|
| `llama3:latest` | 8B, 4,7 GB | 4,8 tok/s | Correcto |
| `qwen3.5:4b` | 4B, 3,4 GB | 6,6 tok/s | **Respuesta vacía** |
| `qwen3.5:4b` con razonamiento desactivado | 4B, 3,4 GB | **11,7 tok/s** | Correcto |

`qwen3.5:4b` es un modelo de razonamiento: envuelve su cadena de pensamiento en bloques
`<think>…</think>` antes de escribir la respuesta visible. Con un presupuesto de 8 tokens
para clasificar, lo consumía entero pensando y devolvía texto vacío. Desactivar el
razonamiento (`reasoning=False` en `ChatOllama`, que se traduce a `"think": false` en la
API de Ollama) resolvió el problema y **casi duplicó la velocidad**.

Es el hallazgo técnico más útil del trabajo y no era evidente de antemano: el modelo
parecía roto cuando en realidad estaba razonando correctamente dentro de un presupuesto
de tokens pensado para un modelo que no razona.

#### Limitaciones encontradas

- **Sin GPU.** El equipo es un i7-1255U con gráficos integrados. Todo corre en CPU.
- **El prompt cuesta tanto como la respuesta.** En CPU, leer el contexto es comparable a
  generarlo. De ahí que `RETRIEVAL_K` bajara de 5 a 4 y que el nodo evaluador reciba los
  fragmentos recortados a 420 caracteres.
- **Longitud acotada.** La respuesta se limita a 320 tokens. Más sería más completo y
  bastante más lento.
- **Calidad desigual en la nube.** El modelo de 1,5B del despliegue redacta peor que el
  de 4B local. Se declara abiertamente: la demostración va por el entorno local.

### Los embeddings

**`intfloat/multilingual-e5-small`** vía Sentence Transformers, en proceso, 384
dimensiones.

Decisión importante: **los embeddings no siguen a `LLM_PROVIDER`.** Son los mismos en
local y en la nube. La base vectorial se comparte entre los dos entornos, y vectores
generados por modelos distintos tienen otra dimensión y otro espacio semántico: la
búsqueda devolvería resultados sin sentido.

Los modelos E5 esperan prefijos que marcan el papel del texto (`query:` para la pregunta,
`passage:` para el fragmento indexado). `HuggingFaceEmbeddings` no los añade, así que se
implementó una subclase que lo hace. Omitirlos degrada la recuperación de forma notable.

Esto se aparta de lo que usó la clase (`nomic-embed-text` de Ollama) y es consciente: con
los embeddings en Ollama, el despliegue en la nube habría necesitado un Ollama también
allí.

### La base vectorial

**PostgreSQL 16 con pgvector**, mediante `langchain-postgres`.

Cada fragmento guarda en sus metadatos:

| Campo | Para qué |
|---|---|
| `document_id` | Asociar el fragmento con su documento original |
| `nombre_archivo` | Citar la fuente en la respuesta |
| `pagina` | Localizar la cita dentro de un PDF |
| `owner_id` | Filtrar por propietario |
| `es_publico` | Distinguir el corpus común del privado |

Los identificadores de fragmento son deterministas (`{document_id}:{índice}`). Así se
pueden borrar todos los fragmentos de un documento sin consultarlos antes, y la
reingesta es idempotente.

#### Regla de visibilidad

```python
{"$or": [
    {"es_publico": {"$eq": True}},
    {"owner_id": {"$eq": str(user_id)}},
]}
```

El corpus de fútbol es público: pertenece al sistema, no a una cuenta. Lo que sube cada
usuario es privado. Sin esta regla, un jurado que se registrase en la URL pública
obtendría un agente que no sabe nada de fútbol y lo rechaza todo — que parece un sistema
roto, no control de alucinaciones.

---

## 9. Proceso de carga de documentos

Formatos aceptados: **PDF, TXT, MD, CSV, DOCX.** Límite de 25 MB.

```
   Frontend                Backend                    Almacenamiento
      │                       │                              │
      │  POST /api/documents  │                              │
      ├──────────────────────►│                              │
      │                       │ valida formato y tamaño      │
      │                       │ guarda el archivo ───────────►│
      │                       │ crea la fila PROCESANDO ─────►│ PostgreSQL
      │  201 { PROCESANDO }   │                              │
      │◄──────────────────────┤                              │
      │                       │                              │
      │                       │ ── tarea en segundo plano ── │
      │                       │  2. extraer contenido        │
      │                       │  3. dividir en fragmentos    │
      │                       │  4. generar embeddings       │
      │                       │  5. almacenar en pgvector ──►│
      │                       │     estado → LISTO ─────────►│
      │                       │                              │
      │  GET /documents/{id}  │                              │
      ├──────────────────────►│                              │
      │  { LISTO, 12 frag. }  │                              │
      │◄──────────────────────┤  6. confirmación al usuario  │
```

### Por qué es asíncrono

Un PDF grande tarda más que el tiempo de espera de una petición HTTP: la subida parecería
haber fallado justo durante la demostración. El `POST` responde al instante con el
documento en `PROCESANDO`, el trabajo pesado corre en una tarea de fondo, y el frontend
consulta el estado cada dos segundos hasta `LISTO` o `ERROR`.

### Extracción por formato

| Formato | Cómo | Detalle |
|---|---|---|
| PDF | `pypdf` | Una entrada por página, conservando el número para citarlo |
| DOCX | `python-docx` | Párrafos **y tablas**: las tablas suelen llevar los datos más consultados |
| CSV | `csv.DictReader` | Cada fila se convierte a `columna: valor`; un CSV crudo se fragmenta mal porque los encabezados acaban en un trozo y los datos en otro |
| TXT / MD | Lectura directa | — |

### Fragmentación

`RecursiveCharacterTextSplitter` con **500 caracteres y 120 de solape**, cortando primero
por párrafo y luego por frase para que un fragmento no parta una idea por la mitad.

Cada fragmento se guarda precedido de una línea con el documento y la sección a la que
pertenece:

```
mundiales historia — Episodios célebres
**El Maracanazo (1950).** Uruguay venció 2-1 a Brasil en el Estadio Maracaná…
```

Esa línea **entra en el embedding**, no es decorativa. Un trozo suelto de una tabla de
sanciones sigue sabiendo que habla de sanciones.

#### Por qué se cambió (y qué se midió)

La primera versión usaba 1000 caracteres y cuatro fragmentos. El agente rechazaba
preguntas cuya respuesta estaba claramente en el corpus:

| Pregunta | Antes | Después |
|---|---|---|
| ¿Qué pasó en el Maracanazo? | Rechazo | Responde, fragmento correcto en 1.ª posición (0,857) |
| ¿Qué es el fuera de juego? | Rechazo | Responde, Regla 11 en 1.ª posición (0,873) |

El diagnóstico mostró que no fallaba el evaluador sino la recuperación: para
«Maracanazo» devolvía el palmarés por selección, el Milagro de Berna y la final de 2021,
pero **no** el párrafo del Maracanazo, que estaba diluido dentro de un fragmento de 1000
caracteres junto a otros cinco episodios. El evaluador rechazaba con razón un contexto
que no contenía la respuesta.

Es un caso instructivo: el síntoma apuntaba al control de alucinaciones, y la causa
estaba dos capas más abajo, en cómo se parte el texto.

### Seguridad en la subida

El archivo se guarda en disco con el **identificador del documento** como nombre, nunca
con el que envía el usuario: un nombre como `../../etc/passwd` escribiría fuera del
directorio previsto.

---

## 10. Estrategias implementadas para evitar alucinaciones

El enunciado pide al menos dos. Están implementadas las seis.

### 1. Umbral mínimo de similitud

`app/vectorstore/store.py`. La recuperación usa
`similarity_search_with_relevance_scores` y descarta todo fragmento por debajo de
`RETRIEVAL_MIN_SCORE` (0,35). **El modelo nunca llega a ver contexto irrelevante**, así
que no puede verse tentado a usarlo. El mejor score se conserva aunque se descarte todo,
porque explica el rechazo.

### 2. Nodo evaluador dedicado

`app/agents/nodes.py` → `evaluar`. Un nodo propio del grafo pide un veredicto
estructurado: `SUFICIENTE` o `INSUFICIENTE`, más un motivo. El criterio del prompt es
estricto: si los fragmentos hablan del tema general pero no contienen el dato concreto,
el veredicto es `INSUFICIENTE`.

> **Detalle que importa:** `"INSUFICIENTE"` contiene `"SUFICIENTE"` como subcadena.
> Comprobarlo en el orden equivocado invierte el resultado y el agente empieza a
> responder justo cuando no debería. Hay una prueba automatizada para esto.

### 3. Prompt que obliga a usar solo el contexto

`app/agents/prompts.py`. Cinco reglas en orden de prioridad. La segunda prohíbe
explícitamente el conocimiento propio *«aunque creas saber la respuesta»*. La tercera
obliga a citar el número de fragmento.

### 4. Rechazo explícito

El texto exacto que pide el enunciado:

> No tengo suficiente información en mi base de conocimiento para responder esa pregunta.

Acompañado de una sugerencia de subir documentos sobre el tema. En la interfaz se marca
con color de precaución y la etiqueta **«Sin respaldo suficiente»**, distinguible de una
respuesta normal de un vistazo.

### 5. Fuentes a la vista

La respuesta de la API incluye cada fragmento usado con su documento, su página y su
score. El frontend los muestra en un desplegable bajo cada respuesta. El usuario puede
comprobar por sí mismo de dónde sale cada afirmación en vez de fiarse del modelo.

### 6. Verificación posterior

`verificar` comprueba que lo generado no exceda el contexto. Si lo excede, la respuesta
se degrada a rechazo. Solo actúa ante un `NO` explícito: un verificador que falla no debe
tumbar una respuesta que ya superó el umbral y al evaluador.

Está detrás de `ENABLE_GROUNDEDNESS_CHECK` y desactivado por defecto porque duplica el
tiempo de respuesta en CPU.

### Comprobación automatizada

`backend/tests/test_antialucinaciones.py` cubre las dos barreras principales: que el
umbral descarta lo que debe, que el evaluador distingue los dos veredictos, que un fallo
de infraestructura no se confunde con falta de información, y que se limpian los bloques
de razonamiento del modelo.

---

## 11. Seguridad y autenticación

### Modelo de protección

Dos routers con el mismo prefijo `/api`. El privado lleva la dependencia de autenticación
aplicada a **todo** lo que cuelgue de él. Un endpoint nuevo nace protegido salvo que
alguien lo registre a propósito en el público.

```python
api_publico = APIRouter(prefix="/api")
api_privado = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])
```

### Auditoría al arrancar

Al importar `app.main` se recorre la tabla de rutas y se comprueba que toda ruta bajo
`/api` o exige token o está en una lista blanca de cinco rutas. Si alguna no cumple, **la
aplicación no arranca**:

```python
_desprotegidas = auditar_rutas(app)
if _desprotegidas:
    raise RuntimeError("Hay endpoints bajo /api sin autenticación…")
```

Un endpoint expuesto por descuido es el tipo de fallo que no se nota: la aplicación
funciona igual de bien. Por eso se comprueba al arrancar y también en las pruebas.

Las cinco rutas públicas son `/api/health`, `/api/health/grafo`, `/api/auth/register`,
`/api/auth/login` y `/api/auth/refresh`. Ninguna revela datos de usuario.

### Tokens

| Token | Duración | Contenido |
|---|---|---|
| Acceso | 60 min | `sub`, `email`, `type: access`, `jti` |
| Refresco | 7 días | `sub`, `type: refresh`, `jti` |

El campo `type` se verifica al decodificar. Sin esa comprobación, un refresh token
serviría como token de acceso y duraría días en vez de minutos.

Los refresh se guardan en base de datos con su `jti`. Al renovar, el usado **se revoca**
(rotación): si alguien roba un refresh y lo usa, el legítimo deja de funcionar y el robo
se nota. Al cerrar sesión se revocan todos los del usuario, de modo que cerrar sesión
cierra la sesión de verdad y no solo borra el token del navegador.

### Contraseñas

bcrypt con sal por contraseña. bcrypt ignora en silencio todo lo que pase de 72 bytes, lo
que haría equivalentes dos contraseñas largas con el mismo prefijo; en vez de truncar sin
avisar, se rechaza explícitamente al registrar.

El mensaje de error de login es el mismo para usuario inexistente y para contraseña
incorrecta: distinguirlos permitiría averiguar qué correos están registrados.

### Keycloak

Con `AUTH_PROVIDER=keycloak`, los tokens se validan en RS256 contra el JWKS del realm,
con el cliente JWKS cacheado una hora para no pedir las claves públicas en cada petición.
Un usuario de Keycloak se refleja en la tabla local por su `sub`, porque las
conversaciones y los documentos necesitan una fila a la que apuntar.

Ambos proveedores devuelven el mismo objeto `User`, así que **ningún router sabe cuál
está activo**. El realm viene preconfigurado en `infra/keycloak/realm-var.json` y se
importa solo al levantar el perfil correspondiente.

### Otras medidas

- CORS restringido a los orígenes de `CORS_ORIGINS`.
- Los manejadores de error nunca devuelven el texto de la excepción al cliente.
- Los archivos subidos se guardan con el identificador del documento como nombre.
- Un usuario no puede leer ni borrar conversaciones ni documentos de otro; se responde
  «no existe» en vez de «no autorizado», para no confirmar que existe.
- Los documentos del corpus común no los puede borrar ningún usuario.

---

## 12. Despliegue

| Pieza | Servicio | URL |
|---|---|---|
| Frontend | Vercel | *(pendiente)* |
| Backend | Hugging Face Spaces (Docker) | *(pendiente)* |
| Base de datos | Neon — PostgreSQL con pgvector | — |

### Por qué no Render para el backend

El enunciado sugiere Render. Su plan gratuito ofrece **512 MB de RAM**, donde PyTorch ni
siquiera llega a cargar, y mucho menos un modelo de lenguaje. **Hugging Face Spaces**
ofrece 16 GB de RAM y 2 vCPU sin coste, con despliegue por Docker. Además es coherente:
un modelo local de HuggingFace corriendo sobre infraestructura de HuggingFace.

La base de datos va a **Neon** y no al PostgreSQL gratuito de Render porque el de Render
caduca a los 30 días, lo que borraría los documentos cargados.

### Variables de entorno del despliegue

| Variable | Valor en la nube |
|---|---|
| `DATABASE_URL` | Cadena de Neon, con `?sslmode=require` |
| `LLM_PROVIDER` | `huggingface` |
| `HF_MODEL` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `EMBEDDING_MODEL` | El mismo que en local, **obligatoriamente** |
| `AUTH_PROVIDER` | `local` |
| `JWT_SECRET` | Generado aparte, nunca el del repositorio |
| `CORS_ORIGINS` | Dominio de Vercel |
| `ENABLE_GROUNDEDNESS_CHECK` | `false` |

En Vercel, `VITE_API_URL` apunta a la URL del Space. Vite incrusta las variables `VITE_*`
en tiempo de compilación, así que cambiarla exige reconstruir, no solo reiniciar.

### Problemas encontrados durante el despliegue

1. **Memoria en los planes gratuitos.** Obligó a cambiar Render por Hugging Face Spaces.
2. **Persistencia del disco.** En planes gratuitos el disco es efímero y cada
   redespliegue borraría los documentos cargados. Los embeddings viven en Neon, que es
   persistente; solo el archivo original se pierde, y ya no hace falta tras la ingesta.
3. **Coherencia de los embeddings.** Local y nube comparten base vectorial. Si cada
   entorno vectorizara con un modelo distinto, los vectores serían incomparables. Se
   resolvió fijando el modelo de embeddings y documentando que no se puede cambiar
   después de ingestar.
4. **Arranque en frío.** Hugging Face Spaces duerme tras 48 h sin tráfico y la primera
   petición tarda. Se despierta sola; conviene hacerle una petición antes de la
   sustentación.
5. **Modelo de embeddings en la imagen.** Se descarga durante la construcción en vez del
   primer arranque, para que el contenedor quede listo desde el principio.

---

## 13. Evidencias de funcionamiento

### Pruebas automatizadas

```
19 passed
```

`backend/tests/` cubre:

- Que ninguna ruta bajo `/api` queda sin autenticación.
- Que las rutas sin token responden 401.
- Que un refresh token no sirve como token de acceso.
- Que el umbral de similitud descarta lo que debe.
- Que el evaluador distingue `SUFICIENTE` de `INSUFICIENTE`.
- Que un fallo de la base vectorial no se confunde con falta de información.
- Que se limpian los bloques de razonamiento del modelo.

### Pruebas de la API

`19 comprobaciones, 0 fallos` sobre el servidor en marcha:

- Los endpoints protegidos devuelven 401 sin token.
- Registro, login, `me`, y rechazo de correo duplicado y de contraseña incorrecta.
- **Rotación de refresh:** reutilizar un refresh ya consumido devuelve 401.
- El corpus de fútbol es visible para una cuenta recién creada (8 documentos).
- Un usuario no puede borrar documentos de la base común (403).
- Subida de un documento: responde `PROCESANDO` y pasa solo a `LISTO`.

### Latencia medida, nodo por nodo

Medido en el equipo de destino (i7-1255U, sin GPU), con la pregunta
*¿Quién ganó el Mundial de 2022?*:

| Nodo | En frío | En caliente |
|---|---:|---:|
| `clasificar` | 7,7 s | 1,5 s |
| `reformular` | 0,0 s | 0,0 s |
| `recuperar` | 16,2 s | 0,1 s |
| `evaluar` | 6,8 s | 7,0 s |
| `generar` | 3,9 s | 3,3 s |
| **Total** | **34,6 s** | **11,8 s** |

Tres lecturas de esta tabla:

- `reformular` marca 0,0 s porque **se omite** cuando no hay historial, que es el caso de
  toda primera pregunta.
- Los 16,2 segundos de `recuperar` en frío son la carga única del modelo de embeddings, no
  la búsqueda: en caliente son 0,1 s. Por eso el modelo **se precarga al arrancar el
  servidor**, y la primera pregunta de un usuario cuesta ya 11,8 segundos y no 34.
- `evaluar` cuesta más que `generar` (7,0 s frente a 3,3 s) porque lee los seis fragmentos
  mientras que la respuesta es corta. En CPU, leer el prompt pesa más que escribir.

> **Sobre medir con el equipo ocupado.** Una tanda anterior dio 110 s de media. No era el
> agente: corría a la vez que Vite empaquetaba el frontend y que el backend cargaba sus
> modelos, y Ollama necesita todos los núcleos. Las cifras de arriba se tomaron con la
> máquina en reposo. Es la condición de la demostración, y conviene tenerlo presente: no
> compilar nada mientras se sustenta.

### Prueba de humo del agente

`uv run python -m scripts.probar_agente` ejecuta el grafo contra nueve preguntas que
cubren los tres comportamientos exigidos y muestra, para cada una, el camino recorrido
por el grafo y el tiempo empleado.

Resultado: **9 de 9 correctas.** Respuestas obtenidas, con sus fuentes:

| Pregunta | Resultado |
|---|---|
| Hola, buenas tardes | Saludo. El grafo va `clasificar → saludo`, sin tocar la base vectorial |
| ¿Quién ganó el Mundial de 2022? | «Argentina ganó el Mundial de 2022 [1]» · `mundiales-historia.md` (0,87) |
| ¿Cuántos Balones de Oro tiene Messi? | «Messi tiene 7 Balones de Oro [2]» · `clasicos-y-leyendas.md` (0,87) |
| ¿Cuándo ganó Colombia la Copa América? | «Colombia ganó la Copa América en 2001 [1], [2]» · `seleccion-colombia.md` (0,88) |
| ¿Qué pasó en el Maracanazo? | Responde desde `mundiales-historia.md` (0,857) |
| ¿Qué es el fuera de juego? | Responde desde `reglas-del-futbol.md` (0,873) |
| ¿Cuál es la mejor receta para preparar sushi? | **Rechazo.** El grafo va `evaluar → rechazar`, sin pasar por `generar` |
| ¿Quién ganó el Mundial de 2026? | **Rechazo.** La base llega hasta 2022 |
| ¿Cuánto cuesta un Tesla Model 3? | **Rechazo** |

La traza confirma el comportamiento. En el rechazo del sushi y en el del Tesla el camino es
`clasificar → reformular → recuperar → evaluar → rechazar → historial`: **el nodo `generar`
no llega a ejecutarse.** No es que se pida al modelo que no invente, es que no se le da la
oportunidad.

El caso del Mundial de 2026 es más interesante y muestra las barreras encadenadas. Ahí la
traza fue:

```
clasificar → reformular(omitido) → recuperar → evaluar → generar(autorrechazo) → historial
```

El evaluador dejó pasar el contexto, porque los fragmentos recuperados **sí hablaban de
mundiales**, solo que de otras ediciones. Fue el modelo generador el que, atado por el
prompt a no salirse del contexto, concluyó que no podía responder y devolvió la frase de
rechazo. El código la detecta y la marca como rechazo real en el historial y en la
interfaz.

Es la cuarta barrera actuando como red de seguridad de la segunda, y es la prueba de por
qué conviene tener varias: ninguna es infalible por separado.

### Capturas

*(Ver `docs/img/`.)*

---

## 14. Problemas encontrados y conclusiones

### Problemas

**El modelo de razonamiento que parecía roto.** `qwen3.5:4b` devolvía respuestas vacías.
No era un error de integración: es un modelo de razonamiento y consumía todo el
presupuesto de tokens dentro del bloque `<think>`. Desactivar el razonamiento lo arregló
y casi duplicó la velocidad. Fue el hallazgo más útil del trabajo, y solo apareció al
medir en vez de suponer.

**La latencia en CPU.** Un grafo de siete nodos puede implicar cinco llamadas secuenciales
al modelo. Se acotó con un presupuesto de tokens por tipo de tarea, omitiendo la
reformulación cuando no hay historial, recortando los fragmentos que ve el evaluador y
dejando la verificación posterior desactivada por defecto.

**Rechazos que parecían del control de alucinaciones y eran del troceado.** El agente se
negaba a explicar el Maracanazo y el fuera de juego, dos cosas que están escritas en el
corpus. Lo fácil era culpar al evaluador por estricto y relajarlo. El diagnóstico mostró
que el evaluador tenía razón: la recuperación no le estaba entregando el párrafo correcto,
porque estaba diluido dentro de un fragmento de 1000 caracteres junto a otros cinco
episodios. La causa estaba dos capas por debajo del síntoma. Se arregló troceando más
fino e incrustando la sección en cada fragmento, no tocando el umbral.

**La incompatibilidad de los embeddings.** Casi se diseña con embeddings de Ollama en
local y de HuggingFace en la nube. Habría producido una base vectorial con vectores de
distinta dimensión e imposible de consultar. Se detectó antes de escribir código, al
pensar en el despliegue.

**OneDrive y los enlaces duros.** El proyecto vive en una carpeta sincronizada y `uv`
falla al instalar con su modo por defecto (`os error 396`). Se resolvió con
`link-mode = "copy"`.

**Python 3.14.** Demasiado nuevo para PyTorch. `uv` fija 3.12 en el proyecto sin tocar la
instalación global del equipo.

**El componente sin estilos.** `MorphOrb` llegó con solo sus `@keyframes`. Hubo que
escribir unas 400 líneas de CSS deduciendo cada clase a partir de las variables que el
componente escribe en tiempo de ejecución.

**Una dependencia que faltaba.** `EmailStr` de Pydantic necesita `email-validator` en
tiempo de ejecución. Lo detectó una prueba antes de que tumbara el arranque del servidor.

### Conclusiones

**Un grafo explícito vale más que un agente prefabricado.** `create_react_agent` resuelve
el caso general en una línea, pero deja al modelo decidir si busca. Con un modelo pequeño,
a menudo decide responder de memoria — justo lo que el trabajo quiere evitar. Un grafo
escrito a mano, donde la búsqueda no es opcional y hay un nodo dedicado a evaluar la
evidencia, da control sobre el comportamiento que se está evaluando.

**El control de alucinaciones es arquitectura, no prompt.** El prompt es la tercera de
seis barreras y la más fácil de saltarse. Las que de verdad funcionan son estructurales:
si el umbral descarta un fragmento, el modelo nunca lo ve; si el evaluador dice que no
alcanza, el nodo de generación no llega a ejecutarse.

**Enseñar las fuentes cambia la relación con el usuario.** Mostrar los fragmentos y los
scores convierte una respuesta en algo comprobable. Y obliga a ser honesto: cuando la
recuperación es mala, se nota.

**Medir antes de decidir.** Las dos decisiones más importantes del proyecto — el modelo y
los parámetros de recuperación — salieron de cronometrar, no de leer documentación. El
modelo que parecía peor resultó ser el bueno en cuanto se configuró bien.

**En un RAG, la calidad del troceado manda sobre todo lo demás.** Se puede tener el mejor
grafo, los mejores prompts y seis barreras anti-alucinación, y aun así el agente rechaza
preguntas que debería responder si la recuperación no le entrega el párrafo correcto. Es
la parte menos vistosa del sistema y la que más condiciona el resultado.

**El rechazo es una funcionalidad.** Es contraintuitivo construir un asistente cuyo logro
sea negarse a contestar. Pero un sistema que admite lo que no sabe es más útil que uno
que siempre responde, porque se puede confiar en lo que sí dice.
