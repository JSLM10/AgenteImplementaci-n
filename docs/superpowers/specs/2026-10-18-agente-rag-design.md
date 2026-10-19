# Diseño — Agente VAR: asistente RAG de fútbol ampliable

Fecha: 2026-10-18
Estado: propuesta, pendiente de aprobación

## 1. Intención y porqué

Trabajo académico de *Implementación e Integración de Software*. Hay que entregar una
aplicación web completa cuyo núcleo sea un agente construido con **LangChain + LangGraph**
sobre arquitectura **RAG**, con modelo de lenguaje local, base vectorial, autenticación,
carga de documentos y despliegue en la nube.

El porqué real, más allá de la rúbrica: el usuario quiere un agente que **sepa de fútbol
de entrada** y que, además, **aprenda de cualquier documento que le suba**. El ejemplo que
dio es literal: si sube un documento que afirma algo sobre una persona concreta y luego
pregunta por eso, el agente debe responderlo; si no hay documento que lo respalde, debe
negarse en vez de inventar.

Eso es exactamente lo que premia la rúbrica (control de alucinaciones, 10% y "criterio más
importante"), así que el objetivo del usuario y el de la nota coinciden.

**Nombre propuesto: `VAR` — Verificador Aumentado de Respuestas.** El VAR del fútbol revisa
la evidencia antes de decidir y, si no hay imágenes concluyentes, no cambia la decisión. Es
la metáfora exacta del grafo que vamos a construir: recuperar evidencia, evaluarla, y
responder solo si alcanza. Si el nombre no gusta, es un find/replace.

## 2. Objetivos

1. Cumplir **los ocho requisitos mínimos de aprobación** (sección 6.1 del enunciado). Sin
   ellos la nota es cero independientemente de lo demás.
2. Que el agente **nunca invente**. Respuesta fundamentada con fuentes citadas, o rechazo
   explícito con el texto que pide el enunciado:
   *"No tengo suficiente información en mi base de conocimiento para responder esa pregunta."*
3. Que la demo en vivo de 7–10 minutos salga sin sobresaltos y cubra los siete puntos de la
   sección 5.3, incluida la carga de un documento nuevo y una pregunta que dependa de él.
4. Que el repositorio se lea como código profesional: separación controladores / servicios /
   agente / acceso a datos, variables de entorno, manejo de errores, README ejecutable.
5. Interfaz que no parezca plantilla. Es solo 5% de la nota, pero es lo primero que ve el
   jurado y condiciona cómo leen el resto.

## 3. No-objetivos

- Multi-tenencia, roles o permisos más allá de "usuario autenticado dueño de sus datos".
- Streaming token a token en el chat. Añade complejidad en el grafo y el modelo local en la
  nube es lento de todos modos; se resuelve con buena animación de carga.
- Soporte de GPU. El portátil es un i7-1255U con gráficos integrados: todo se diseña para CPU.
- Escalabilidad real. Un proceso, un worker.
- Rehacer los repos de clase. Se construye **sobre** su estilo (uv/Poetry, FastAPI,
  PGVector, Ollama, docker-compose), completando lo que allá quedó a medias.

## 4. Anti-objetivos (cosas que harían fracasar el trabajo aunque "funcione")

- **Que el agente conteste de memoria paramétrica.** Si responde "¿quién ganó el Mundial 2022?"
  sin que eso salga de la base vectorial, el trabajo falla en su criterio central aunque la
  respuesta sea correcta. Toda respuesta debe ser trazable a fragmentos recuperados.
- **Que algún endpoint quede sin autenticación.** El enunciado lo dice explícitamente.
  La protección va por defecto (deny by default), no endpoint por endpoint.
- **Que el grafo de LangGraph sea decorativo.** Un `create_react_agent` prebuilt de una línea
  no evidencia dominio. Tiene que haber nodos propios, aristas condicionales y un nodo de
  validación visible y explicable en la sustentación.
- **Que la demo dependa de internet del salón o de un servicio externo frágil.** Todo el
  camino crítico corre local; la nube es evidencia adicional.
- **Que el agente alucine sobre fútbol reciente.** La base de conocimiento llega hasta el
  Mundial 2022. El Mundial 2026 es justamente el caso de demostración de rechazo + carga.

## 5. Restricciones

| Restricción | Origen | Consecuencia de diseño |
|---|---|---|
| LangChain + LangGraph obligatorios, prohibido n8n/Flowise | Enunciado §4 | Grafo escrito a mano con `StateGraph` |
| Modelo de lenguaje ejecutado localmente | Enunciado §3.2 | Ollama en local, Transformers de HF en la nube |
| Backend y frontend con URL pública | Enunciado §3.5 | HF Spaces + Vercel + Neon |
| Ningún endpoint sin autenticación | Enunciado §2.1 | Dependencia global de FastAPI |
| i7-1255U, 32 GB RAM, sin GPU dedicada | Máquina del usuario | Modelos de 7–8B como techo local |
| Python 3.14 instalado (demasiado nuevo para torch) | Máquina del usuario | `uv` fija Python 3.12 en el proyecto |
| Planes gratis de nube: 512 MB en Render | Investigado | El backend va a HF Spaces (16 GB gratis) |
| El CSS del componente MorphOrb que entregó el usuario está incompleto | Revisado | Hay que escribir la hoja de estilos completa |

## 6. Decisiones ya tomadas

Las cuatro primeras las decidió el usuario explícitamente. El resto son llamadas mías y van
marcadas como tales.

### 6.1 Proveedor de LLM dual *(decidido por el usuario)*

Una variable `LLM_PROVIDER` conmuta entre dos implementaciones de la misma interfaz:

- `ollama` — por defecto en local y en la demo en vivo. `llama3.1:8b`, que es el modelo que
  usó la clase. Respuestas buenas, ~6 GB de RAM, cómodo en 32 GB.
- `huggingface` — en la nube. `Qwen/Qwen2.5-1.5B-Instruct` vía `transformers`, cargado en el
  proceso del backend. Lento (CPU) pero es un modelo local de verdad, no una API comercial.

Ambos caminos cumplen "modelo local". El documento técnico justificará los dos, sus
diferencias de calidad y la limitación encontrada (velocidad en CPU sin GPU).

### 6.2 Autenticación doble *(decidido por el usuario)*

`AUTH_PROVIDER` conmuta entre:

- `local` — registro y login propios en FastAPI. Contraseñas con bcrypt, tokens JWT HS256
  (access corto + refresh), rotación de refresh. Es el camino por defecto y el que se
  despliega.
- `keycloak` — validación de tokens OIDC RS256 contra el JWKS del realm. Keycloak se levanta
  en `docker-compose` con un realm preconfigurado que se importa solo.

Ambos producen el mismo objeto `CurrentUser`, así que el resto del backend no sabe cuál está
activo. Eso es lo que impide que la doble implementación duplique código.

### 6.3 Base vectorial: pgvector *(decidido por el usuario)*

Un solo PostgreSQL guarda usuarios, conversaciones, mensajes, documentos y embeddings.
En local, contenedor `pgvector/pgvector:pg16`. En la nube, Neon (gratis, permanente,
pgvector incluido). Acceso vía `langchain-postgres` / `PGVector`, igual que la clase.

### 6.4 Embeddings fijos, no conmutables *(llamada mía — importante)*

Los embeddings **no** siguen a `LLM_PROVIDER`. Son siempre
`intfloat/multilingual-e5-small` vía `sentence-transformers`, en proceso, 384 dimensiones.

Razón: la base vectorial es compartida entre local y nube. Si cada entorno vectorizara con
un modelo distinto, los vectores tendrían dimensiones y espacios semánticos incompatibles y
la búsqueda devolvería basura. Se elige e5-small por ser multilingüe (el corpus y las
preguntas son en español), pequeño (118 MB) y rápido en CPU.

Coste: deja de usarse `nomic-embed-text` de Ollama, que es lo que usó la clase. Es una
desviación consciente y se justifica en el documento técnico.

### 6.5 El grafo de LangGraph *(llamada mía)*

Siete nodos, que son exactamente los siete pasos del flujo de referencia del enunciado (§3.1):

```
                    ┌──────────────────┐
  START ──────────► │   clasificar     │  ¿saludo, pregunta o fuera de alcance?
                    └────────┬─────────┘
                             │ condicional
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          [saludo]      [reformular]    [rechazar]
              │              │              │
              │              ▼              │
              │        ┌───────────┐        │
              │        │ recuperar │  búsqueda vectorial + umbral
              │        └─────┬─────┘        │
              │              ▼              │
              │        ┌───────────┐        │
              │        │  evaluar  │  ¿alcanza este contexto?
              │        └─────┬─────┘        │
              │        condicional          │
              │         ┌────┴────┐         │
              │         ▼         ▼         │
              │     [generar] [rechazar]◄───┘
              │         │         │
              │         ▼         │
              │    [verificar]    │  ¿la respuesta se sostiene en el contexto?
              │         │         │
              └─────────┴────┬────┘
                             ▼
                     ┌───────────────┐
                     │   historial   │  persiste en Postgres
                     └───────┬───────┘
                             ▼
                            END
```

Estado compartido (`TypedDict`): `user_id`, `conversation_id`, `pregunta`,
`historial`, `pregunta_reformulada`, `fragmentos`, `score_maximo`, `contexto_suficiente`,
`motivo_rechazo`, `respuesta`, `fuentes`, `rechazada`.

El nodo `verificar` es opcional vía `ENABLE_GROUNDEDNESS_CHECK` porque duplica el coste de
inferencia; va activo en local (demo) y apagable en la nube.

### 6.6 Control de alucinaciones: las seis estrategias *(llamada mía)*

El enunciado pide dos. Se implementan las seis, porque es el criterio más pesado y el más
fácil de demostrar en vivo:

1. **Umbral de similitud.** `similarity_search_with_relevance_scores`; los fragmentos por
   debajo de `RETRIEVAL_MIN_SCORE` se descartan antes de llegar al modelo.
2. **Nodo evaluador dedicado.** `evaluar_contexto` le pide al LLM un veredicto estructurado
   (suficiente sí/no + motivo) sobre si los fragmentos responden la pregunta.
3. **Prompt restrictivo.** El prompt de generación prohíbe el conocimiento externo y obliga
   a citar el número de fragmento.
4. **Rechazo explícito.** Mensaje literal del enunciado + sugerencia de subir documentos
   sobre el tema.
5. **Fuentes a la vista.** La respuesta de la API incluye los fragmentos usados con su
   documento de origen y su score; el frontend los muestra desplegables bajo cada respuesta.
6. **Verificación posterior.** `verificar_respuesta` comprueba que lo generado no exceda el
   contexto; si lo excede, degrada a rechazo.

### 6.7 Backend *(llamada mía)*

FastAPI. Estructura con separación explícita, como pide §2.2:

```
backend/app/
  main.py            arranque, CORS, routers, manejadores de error
  core/              config (pydantic-settings), seguridad, dependencias
  api/routes/        auth, chat, documents, health   ← controladores
  services/          auth, ingestion, documents, conversations  ← lógica
  agents/            state, prompts, llm, nodes, graph  ← el agente
  vectorstore/       cliente PGVector, búsqueda con umbral
  db/                modelos SQLAlchemy, sesión, migraciones
  schemas/           modelos Pydantic de entrada/salida
```

Endpoints (todos autenticados salvo los cuatro marcados):

| Método | Ruta | Público |
|---|---|---|
| POST | `/api/auth/register` | sí |
| POST | `/api/auth/login` | sí |
| POST | `/api/auth/refresh` | sí |
| GET | `/api/health` | sí |
| POST | `/api/auth/logout` | no |
| GET | `/api/auth/me` | no |
| POST | `/api/chat` | no |
| GET | `/api/conversations` | no |
| GET | `/api/conversations/{id}` | no |
| DELETE | `/api/conversations/{id}` | no |
| POST | `/api/documents` (subida) | no |
| GET | `/api/documents` | no |
| GET | `/api/documents/{id}` | no |
| DELETE | `/api/documents/{id}` | no |

La protección es por dependencia global en el router `/api`, con una lista blanca explícita
de rutas públicas. Así un endpoint nuevo nace protegido, que es el comportamiento seguro.

### 6.8 Carga de documentos *(llamada mía)*

Pipeline en seis pasos, los del enunciado §2.4. Formatos: PDF, TXT, MD, CSV, DOCX siempre;
JPG/JPEG (OCR), MP3/MP4 (transcripción Whisper local) detrás de `ENABLE_MEDIA_INGEST`,
apagado en la nube para no inflar la imagen.

El procesamiento es **asíncrono con estado**: el POST responde al instante con el documento
en `PROCESANDO`, un `BackgroundTask` hace extracción → chunking → embeddings → pgvector, y
el frontend consulta el estado hasta `LISTO` o `ERROR`. Si fuera síncrono, un PDF grande
tumbaría la petición por timeout justo durante la demo.

Cada chunk guarda `document_id`, `user_id`, nombre de archivo y número de página en metadatos,
que es lo que permite citar la fuente y borrar un documento de la base vectorial.

### 6.9 Frontend *(llamada mía)*

React 18 + Vite + TypeScript + Tailwind v4 + shadcn/ui + **motion** (Framer Motion).

El componente `MorphOrb` que entregó el usuario se integra como **la pantalla de bienvenida
del chat**: cuando una conversación está vacía, el orbe ocupa el centro; la primera pregunta
se hace ahí y su animación de "pensando" corre mientras el agente trabaja de verdad. Cuando
llega la respuesta, el orbe se despliega en la tarjeta de respuesta y la vista transiciona al
hilo de chat normal. Los mensajes siguientes van en burbujas, con un indicador pequeño
derivado del mismo orbe.

Esto es deliberado: el componente está diseñado para **una** pregunta y **una** respuesta, no
para un hilo. Forzarlo a ser el chat completo lo rompería; usarlo como entrada al chat lo
aprovecha donde brilla.

Pantallas: Login/Registro · Chat (hilo + barra lateral de conversaciones) · Documentos
(subida con drag & drop, lista con estado, borrado) · barra superior con usuario y logout.

Se invocará la skill `frontend-design` antes de decidir la dirección visual, para que no
quede con pinta de plantilla.

### 6.10 Base de conocimiento inicial *(llamada mía)*

Entre 8 y 12 documentos Markdown curados sobre fútbol: historia de los Mundiales y campeones
hasta 2022, Copa Libertadores, Champions League, Selección Colombia, Balón de Oro, reglas
del juego, glosario táctico, clásicos y rivalidades.

**Decisión clave para la demo:** la base llega hasta 2022 a propósito, así que
"¿Quién ganó el Mundial 2026?" es un rechazo legítimo y demostrable.

El documento que se sube en vivo, en cambio, **no** será sobre el Mundial 2026 (ver §11.5):
nadie en la sala puede verificarlo y afirmar un campeón equivocado destruiría justo la tesis
del trabajo. Será un documento indiscutible, pendiente de que el usuario elija cuál.

### 6.11 Despliegue *(llamada mía — se desvía de lo que sugiere el enunciado)*

| Pieza | Dónde | Por qué |
|---|---|---|
| Backend | **Hugging Face Spaces** (Docker) | Gratis con 16 GB de RAM y 2 vCPU. Render gratis da 512 MB, donde `torch` ni siquiera carga. Además es coherente: un modelo local de HF corriendo en infraestructura de HF |
| Base de datos | **Neon** | Postgres gratis permanente con pgvector. El de Render gratis caduca a los 30 días |
| Frontend | **Vercel** | Build estático de Vite, dominio público, despliegue desde Git |

El enunciado sugiere Render para el backend; la desviación se justifica en el documento
técnico por la restricción de memoria, que es un hallazgo legítimo del proceso de despliegue
y de hecho material para el apartado "problemas encontrados".

## 7. Qué queda a criterio de quien implemente

- Nombres internos de funciones, variables y archivos dentro de la estructura acordada.
- Estrategia de chunking concreta (tamaño y solape); punto de partida 1000/200 como la clase,
  ajustable si la recuperación sale pobre.
- Modelo exacto de Ollama si `llama3.1:8b` resulta lento en este portátil (alternativa
  `qwen2.5:7b`, mejor en español).
- Paleta, tipografía y detalle visual, dentro de lo que diga `frontend-design`.
- Redacción de los documentos de fútbol, mientras los hechos sean verificables y no pasen de 2022.
- Alcance de las pruebas automatizadas. Mínimo: el nodo de evaluación de contexto, el umbral
  de similitud y el guard de autenticación — que son las tres cosas cuya rotura silenciosa
  costaría la nota.

## 8. Entregables

1. **Repositorio** con backend, frontend, configuración del agente, README ejecutable,
   `.env.example`, capturas y diagrama de arquitectura.
2. **Documento técnico** en PDF, con los 14 apartados de §5.2. Este diseño cubre ya buena
   parte de su contenido.
3. **Diapositivas**, 8–12 láminas. *El usuario pidió dejarlas para después.*
4. **Guion de sustentación** de 7–10 minutos con el orden exacto de la demo.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| `llama3.1:8b` lento en CPU y la demo se arrastra | Medir temprano; si no da, bajar a `qwen2.5:7b` o `llama3.2:3b`. `num_predict` acotado |
| El modelo pequeño de la nube responde con peor calidad que el local | Es esperado y se declara en el documento técnico. La demo en vivo va por local |
| HF Spaces duerme tras 48 h sin tráfico | Se despierta solo con la primera petición; avisar al jurado o hacerle un ping antes |
| Python 3.14 rompe `torch` | `uv` fija 3.12 en `.python-version` |
| El CSS del orbe hay que escribirlo entero y puede comerse mucho tiempo | Se hace después de que el camino crítico (auth + grafo + RAG) esté funcionando |
| El alcance es grande | Orden de construcción por riesgo: base de datos y auth → agente y RAG → documentos → frontend → despliegue → documentación |

## 10. Respuestas del usuario y línea de corte definitiva

**Equipo (3 integrantes):** Juan Pablo Muñoz · Gabriel Giraldo · Luis Brito.

**Plazo: un día.** Esto manda sobre todo lo demás y obliga a recortar. El alcance queda así:

| Pieza | Decisión | Motivo |
|---|---|---|
| Auth local (JWT propio) | **Entra completo** | Requisito mínimo de aprobación |
| Keycloak | **Solo backend**: validador RS256/JWKS + servicio en compose. Sin flujo OIDC en el frontend | El validador son ~80 líneas y deja el requisito "recomendado" cubierto; el doble flujo de login en el frontend no cabe |
| Grafo LangGraph de 7 nodos | **Entra completo** | Es el 15% de la rúbrica y el corazón del trabajo |
| Estrategias anti-alucinación | **Las 6**, con `verificar` apagado por defecto | Son baratas de escribir y valen el 10%. El nodo extra se enciende solo si la latencia lo permite |
| Proveedor LLM dual | **Entra**, pero Ollama es el camino probado | La clase `HuggingFaceProvider` son ~40 líneas; el camino de la demo es Ollama |
| Ingest multimedia (JPG/MP3/MP4) | **Cortado** | Formatos solo *sugeridos*. No suman en rúbrica y meten Whisper + OCR + binarios de sistema |
| Formatos de documento | PDF, TXT, MD, CSV, DOCX | Cubre el requisito con dependencias que ya están |
| Despliegue en la nube | **Al final**, cuando lo local esté verificado | Decisión del usuario |

**Modelo local por defecto: `qwen3.5:4b`**, que ya está descargado. Un 4B en este portátil
entra en el presupuesto de latencia de §11.2 con margen; `llama3:latest` queda de respaldo.

**Documento de la demo en vivo:** el ejemplo original del usuario — un texto con
afirmaciones internas que no existen en ninguna otra fuente. Es la prueba más contundente de
que la respuesta salió del documento y no del modelo.

**Orden de construcción, por riesgo:**

1. Esqueleto del repo, docker-compose, Postgres + pgvector arriba
2. Modelos de datos y auth local — sin esto no hay nada que demostrar
3. Grafo de LangGraph y RAG, con el corpus semilla de fútbol
4. Carga y procesamiento de documentos
5. Frontend: login, chat con el orbe, documentos
6. Documento técnico y README
7. Despliegue en la nube, si queda tiempo

## 11. Resoluciones tras la revisión de diseño

Un revisor independiente leyó este documento como si tuviera que construirlo sin poder
preguntar. Levantó ocho huecos. Estos son los cinco que resuelvo yo.

### 11.1 El corpus de fútbol es global; lo que sube cada usuario es suyo

El hueco era real y tenía dos formas de romper la demo. Si la recuperación filtra
estrictamente por `user_id` y el corpus semilla pertenece a una cuenta, cualquier jurado que
se registre en la URL pública obtiene un agente que no sabe nada de fútbol y lo rechaza todo
— que se lee como sistema roto, no como control de alucinaciones. Y si todo fuera global, lo
que sube un usuario cambiaría las respuestas de otro, que contradice el ejemplo que motivó
el trabajo.

Regla: los documentos semilla se ingestan con `owner_id = NULL` e `is_public = true`. Los
subidos por un usuario quedan con su `owner_id` e `is_public = false`. Toda recuperación
filtra por `is_public = true OR owner_id = <usuario actual>`. El jurado ve el fútbol; nadie
ve los documentos de otro.

### 11.2 Presupuesto de latencia: 20 segundos por respuesta

Siete nodos pueden implicar hasta cinco llamadas secuenciales al modelo. En un i7-1255U sin
GPU eso son minutos, y "la demo se arrastra" ya figuraba como modo de fallo. Se fija un
presupuesto y el grafo se diseña para cumplirlo:

| Nodo | Coste | Cómo se acota |
|---|---|---|
| `clasificar` | 1 llamada | `num_predict=8`, devuelve una sola palabra |
| `reformular` | 0 o 1 | se salta cuando no hay historial, que es el caso de la primera pregunta |
| `recuperar` | 0 | búsqueda vectorial, sin modelo |
| `evaluar` | 1 llamada | salida estructurada corta, `num_predict=64` |
| `generar` | 1 llamada | `num_predict=512` |
| `verificar` | 0 o 1 | apagable por variable de entorno |
| `historial` | 0 | escritura en Postgres |

Camino típico: tres llamadas, dos de ellas muy cortas. El modelo local por defecto se decide
**midiendo**, no por catálogo: se cronometra `qwen3.5:4b` (ya descargado) contra
`llama3.1:8b` y gana el que entre en presupuesto. La medición se hace al terminar el grafo,
antes de construir el frontend, para que una mala noticia llegue cuando todavía hay margen.

### 11.3 Keycloak llega hasta el frontend, pero es lo primero que se corta

El revisor señaló con razón que "el resto del backend no sabe cuál está activo" vale para el
backend pero no para el frontend: `local` es un POST de formulario que devuelve JWTs, y
`keycloak` es un redirect OIDC con callback, almacén de tokens y logout distintos. Son dos
flujos de verdad.

Como el usuario pidió explícitamente las dos, se hace completo: botón "Entrar con Keycloak"
y flujo OIDC de punta a punta. Pero se construye **después** de que el camino crítico esté
funcionando, y es el primer candidato a recortar si el tiempo aprieta, porque el enunciado
solo *recomienda* Keycloak y lo que se despliega es `local`.

### 11.4 El ingest multimedia va al final

JPG por OCR y MP3/MP4 por Whisper son formatos *sugeridos*, no exigidos, y no suman en la
rúbrica nada que PDF/TXT/DOCX no sumen ya. A cambio meten Whisper, un motor de OCR y
binarios de sistema en el entorno local y en el Dockerfile. Se programan los últimos, detrás
de `ENABLE_MEDIA_INGEST`, y la imagen de la nube no los lleva.

### 11.5 El documento de la demo no será sobre el Mundial 2026

Era un error de diseño y conviene dejarlo escrito. El Mundial 2026 ya se jugó, mi
conocimiento se corta antes del resultado, y la regla del corpus ("hechos verificables,
nada posterior a 2022") no cubría ese archivo. Afirmar un campeón equivocado delante del
jurado tumbaría exactamente la tesis que el proyecto defiende.

Se separa en dos: "¿quién ganó el Mundial 2026?" se queda como demo de **rechazo** (es
seguro: la base para en 2022). Para la demo de **carga**, un documento que nadie pueda
discutir. Pendiente de que el usuario elija; la recomendación es su propio ejemplo original,
un texto con afirmaciones internas que no existen en ninguna otra parte, porque demuestra
sin ambigüedad que la respuesta salió del documento y no del modelo.

### 11.6 Lo que queda abierto por tiempo

El diseño lleva a propósito casi el doble del alcance exigido: dos proveedores de LLM, dos
de autenticación, seis estrategias anti-alucinación donde piden dos, ingest multimedia, UI
animada a mano y tres servicios en la nube. Sin fecha de entrega no hay línea de corte.

Orden de recorte, de lo primero que cae a lo último: ingest multimedia → Keycloak en el
frontend → nodo `verificar` → despliegue en la nube. El núcleo intocable es auth local +
grafo + RAG + documentos + frontend, que es lo que cubre los ocho requisitos mínimos.

### 11.7 Verificado sobre la máquina

El revisor afirmó modelos que no están. Comprobado directamente: Ollama tiene `qwen3.5:4b`
(3.4 GB) y `llama3:latest` (4.7 GB); **no** hay `llama3.1:8b` ni `qwen2.5:7b`. Que haya un
modelo de 4B ya descargado juega a favor del presupuesto de §11.2. El directorio del
proyecto todavía no es un repositorio git. Hay 174 GB libres.
