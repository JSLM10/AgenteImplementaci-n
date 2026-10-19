# VAR — Verificador Aumentado de Respuestas

Agente conversacional construido con **LangChain** y **LangGraph** sobre una arquitectura
**RAG**, con modelo de lenguaje ejecutado en local y base de datos vectorial. Responde
preguntas de fútbol a partir de su base de conocimiento y aprende de cualquier documento
que se le suba. Cuando no encuentra respaldo, lo dice en vez de inventárselo.

El nombre viene del videoarbitraje: el VAR revisa la evidencia antes de decidir y, si no
hay imágenes concluyentes, no cambia la decisión. Es exactamente lo que hace este grafo.

**Asignatura:** Implementación e Integración de Software
**Equipo:** Juan Pablo Muñoz · Gabriel Giraldo · Luis Brito

---

## Qué hace

- Chat autenticado contra un agente que **solo** responde con lo que recupera de su base
  vectorial, citando el fragmento y el documento de los que sale cada afirmación.
- Rechazo explícito cuando el contexto no alcanza, con el mensaje que exige el enunciado.
- Carga de documentos (PDF, TXT, MD, CSV, DOCX) que pasan a formar parte de lo que el
  agente puede consultar, procesados en segundo plano.
- Historial de conversaciones por usuario.
- Base de fútbol común a todas las cuentas; los documentos que sube cada usuario son
  privados y solo aparecen en sus respuestas.

---

## Arquitectura

```
                 Navegador
                     │
            React + Vite + Tailwind          ← frontend/
                     │  JWT en cada petición
                     ▼
        ┌──────────────────────────────┐
        │   API FastAPI protegida      │     ← backend/app/api
        │   ──────────────────────     │
        │   auth · chat · documentos   │
        └───────────┬──────────────────┘
                    │
        ┌───────────▼──────────────────┐
        │   Agente LangGraph           │     ← backend/app/agents
        │   7 nodos, 2 bifurcaciones   │
        └─────┬──────────────────┬─────┘
              │                  │
     ┌────────▼───────┐  ┌───────▼────────────┐
     │ Modelo local   │  │ PostgreSQL         │
     │ Ollama / HF    │  │ + pgvector         │
     └────────────────┘  └────────────────────┘
```

El diagrama del grafo, generado por LangGraph a partir del código compilado, está en
`GET /api/health/grafo` y en [docs/documento-tecnico.md](docs/documento-tecnico.md).

### El grafo

```
START → clasificar ─┬─ SALUDO ──────────────► saludo ──────────┐
                    ├─ OTRO ────────────────► rechazar ────────┤
                    └─ PREGUNTA → reformular → recuperar        │
                                                   │           │
                                              evaluar ─┬─ no ──┤
                                                       │       │
                                                       sí      │
                                                       ▼       │
                                                   generar     │
                                                       ▼       │
                                                   verificar ──┤
                                                               ▼
                                                          historial → END
```

| Nodo | Qué hace |
|---|---|
| `clasificar` | Separa saludo, pregunta y mensaje sin contenido |
| `reformular` | Resuelve pronombres con el historial. Se omite en la primera pregunta |
| `recuperar` | Búsqueda vectorial filtrada por visibilidad, con umbral de similitud |
| `evaluar` | Decide si los fragmentos recuperados bastan para responder |
| `generar` | Redacta usando solo el contexto, citando `[1]`, `[2]` |
| `verificar` | Comprueba que la respuesta no se sale del contexto *(opcional)* |
| `rechazar` | Devuelve el rechazo explícito y sugiere subir documentos |
| `historial` | Guarda la interacción en PostgreSQL |

### Control de alucinaciones

El enunciado pide dos estrategias. Están implementadas las seis:

| # | Estrategia | Dónde |
|---|---|---|
| 1 | Umbral mínimo de similitud | `app/vectorstore/store.py` |
| 2 | Nodo evaluador de contexto | `app/agents/nodes.py` → `evaluar` |
| 3 | Prompt que prohíbe el conocimiento externo | `app/agents/prompts.py` |
| 4 | Rechazo explícito | `app/agents/nodes.py` → `rechazar` |
| 5 | Fuentes visibles en la respuesta | `app/schemas/chat.py`, `frontend/src/components/Fuentes.tsx` |
| 6 | Verificación posterior de la respuesta | `app/agents/nodes.py` → `verificar` |

---

## Tecnologías

| Capa | Elección |
|---|---|
| Backend | FastAPI · Python 3.12 · uv |
| Agente | LangChain · LangGraph |
| Modelo local | Ollama (`qwen3.5:4b`) · alternativa HuggingFace Transformers |
| Embeddings | `intfloat/multilingual-e5-small` vía Sentence Transformers |
| Base vectorial | PostgreSQL 16 + pgvector (`langchain-postgres`) |
| Autenticación | JWT propio (bcrypt + PyJWT) · Keycloak opcional |
| Frontend | React 19 · Vite · TypeScript · Tailwind v4 · Motion |
| Contenedores | Docker Compose |

---

## Ejecución local

### Requisitos

- [Docker](https://docker.com) y Docker Compose
- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 por su cuenta)
- [Node.js](https://nodejs.org) 20 o superior
- [Ollama](https://ollama.com) con un modelo descargado

### 1. Variables de entorno

```bash
cp .env.example .env
```

Genera una clave propia para firmar los tokens y pégala en `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Base de datos

```bash
docker compose up -d postgres
```

Levanta PostgreSQL 16 con pgvector en el puerto 5432. La extensión y las tablas las crea
el backend al arrancar.

### 3. Modelo local

```bash
ollama pull qwen3.5:4b
```

Vale cualquier modelo de Ollama; ajusta `OLLAMA_MODEL` en el `.env`. Si el modelo es de
razonamiento, deja `OLLAMA_REASONING=false`: con el razonamiento activo las llamadas
cortas se quedan sin tokens dentro del bloque de pensamiento y devuelven texto vacío.

### 4. Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

En el primer arranque descarga el modelo de embeddings (~118 MB) y siembra la base de
fútbol. Tarda un par de minutos; las siguientes veces arranca en segundos.

- API: http://localhost:8000
- Documentación interactiva: http://localhost:8000/docs

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173

### Todo con Docker

```bash
docker compose up -d --build
```

Frontend en http://localhost:5173 y backend en http://localhost:8000. El backend del
contenedor usa el Ollama del equipo anfitrión a través de `host.docker.internal`.

Perfiles opcionales:

```bash
docker compose --profile ollama up -d      # Ollama en contenedor
docker compose --profile keycloak up -d    # Keycloak con el realm ya importado
```

---

## Comprobaciones

```bash
cd backend

uv run pytest                          # pruebas de seguridad y anti-alucinaciones
uv run python -m scripts.probar_agente # el agente de punta a punta, con tiempos
```

`probar_agente` ejecuta el grafo contra nueve preguntas que cubren los tres
comportamientos exigidos — responder con fundamento, rechazar por falta de información y
atender un saludo — e imprime el camino que siguió cada una por el grafo.

---

## Estructura

```
.
├── backend/
│   ├── app/
│   │   ├── agents/        grafo, nodos, prompts, proveedor de modelo
│   │   ├── api/routes/    controladores
│   │   ├── core/          configuración, seguridad, dependencias
│   │   ├── db/            modelos SQLAlchemy y sesión
│   │   ├── schemas/       entrada y salida de la API
│   │   ├── services/      lógica de negocio
│   │   ├── vectorstore/   embeddings y búsqueda con umbral
│   │   └── main.py        montaje y auditoría de rutas
│   ├── seed/              base de conocimiento inicial de fútbol
│   ├── scripts/           prueba de humo del agente
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/    marco, fuentes, traza del grafo, orbe
│       ├── context/       sesión
│       ├── lib/           cliente de la API
│       └── pages/         login, chat, documentos
├── infra/keycloak/        realm preconfigurado
├── docs/                  documento técnico y diagramas
├── docker-compose.yml
└── .env.example
```

---

## Variables de entorno

Las define y documenta [`.env.example`](.env.example). Las que más cambian el
comportamiento:

| Variable | Por defecto | Para qué |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` en local, `huggingface` en la nube |
| `OLLAMA_MODEL` | `qwen3.5:4b` | Modelo de chat |
| `OLLAMA_REASONING` | `false` | Razonamiento explícito del modelo |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | **No cambiar tras ingestar**: invalida los vectores guardados |
| `RETRIEVAL_K` | `4` | Fragmentos recuperados por pregunta |
| `RETRIEVAL_MIN_SCORE` | `0.35` | Umbral de similitud. Subirlo = más rechazos, más precisión |
| `ENABLE_GROUNDEDNESS_CHECK` | `true` | Nodo extra que verifica la respuesta. Cuesta 0,9 s; apagarlo solo en la nube |
| `AUTH_PROVIDER` | `local` | `local` o `keycloak` |
| `JWT_SECRET` | — | **Cambiar siempre** |

---

## Despliegue

| Pieza | Servicio |
|---|---|
| Backend | Hugging Face Spaces (Docker) |
| Base de datos | Neon — PostgreSQL con pgvector |
| Frontend | Vercel |

El procedimiento completo, con las URL públicas y los problemas encontrados, está en
[docs/documento-tecnico.md](docs/documento-tecnico.md).

> El backend no se despliega en Render pese a ser lo que sugiere el enunciado: su plan
> gratuito da 512 MB de RAM y PyTorch no llega siquiera a cargar. Hugging Face Spaces
> ofrece 16 GB sin coste.

---

## Licencia

Trabajo académico. Uso libre con atribución.
