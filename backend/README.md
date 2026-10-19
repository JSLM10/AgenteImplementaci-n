# Backend — VAR

API REST con FastAPI. Expone el agente LangGraph, la autenticación y la carga de
documentos. Todos los endpoints bajo `/api` exigen token salvo cinco rutas públicas.

## Puesta en marcha

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Necesita PostgreSQL con pgvector en marcha (`docker compose up -d postgres` desde la raíz)
y un Ollama con el modelo descargado.

El primer arranque descarga el modelo de embeddings y siembra el corpus de fútbol de
`seed/`. Los siguientes no repiten el trabajo.

## Organización

```
app/
├── main.py          montaje de routers y auditoría de seguridad
├── core/
│   ├── config.py    toda la configuración, leída del entorno
│   ├── security.py  hashing de contraseñas y emisión de JWT
│   └── deps.py      identificación del usuario (JWT propio o Keycloak)
├── api/routes/      controladores: auth, chat, documents, health
├── services/        lógica: auth, agente, conversaciones, documentos, ingesta, siembra
├── agents/          grafo, nodos, prompts, estado, proveedor de modelo
├── vectorstore/     embeddings y búsqueda con umbral
├── db/              modelos SQLAlchemy y sesión
└── schemas/         modelos Pydantic de entrada y salida
```

La separación es deliberada: un controlador no construye prompts ni abre conexiones a la
base vectorial, y un nodo del agente no sabe que existe HTTP.

## Endpoints

| Método | Ruta | Token |
|---|---|:---:|
| `GET` | `/api/health` | — |
| `GET` | `/api/health/grafo` | — |
| `POST` | `/api/auth/register` | — |
| `POST` | `/api/auth/login` | — |
| `POST` | `/api/auth/refresh` | — |
| `GET` | `/api/auth/me` | ✔ |
| `POST` | `/api/auth/logout` | ✔ |
| `POST` | `/api/chat` | ✔ |
| `GET` | `/api/conversations` | ✔ |
| `GET` | `/api/conversations/{id}` | ✔ |
| `DELETE` | `/api/conversations/{id}` | ✔ |
| `POST` | `/api/documents` | ✔ |
| `GET` | `/api/documents` | ✔ |
| `GET` | `/api/documents/{id}` | ✔ |
| `DELETE` | `/api/documents/{id}` | ✔ |

Documentación interactiva en `/docs`.

### Cómo se protegen

Hay dos routers con el mismo prefijo `/api`. El privado lleva la dependencia de
autenticación aplicada a todo lo que cuelgue de él, así que **un endpoint nuevo nace
protegido** salvo que alguien lo registre a propósito en el público.

Además, al importar `app.main` se recorre la tabla de rutas y se comprueba que toda ruta
bajo `/api` o exige token o está en `RUTAS_PUBLICAS`. Si no, la aplicación no arranca.
La prueba `tests/test_seguridad.py` comprueba lo mismo en integración continua.

## Pruebas

```bash
uv run pytest                           # rápidas, sin red ni base de datos
uv run python -m scripts.probar_agente  # el agente completo, con tiempos reales
```

## Notas de operación

- **No cambies `EMBEDDING_MODEL` después de ingestar documentos.** Los vectores guardados
  tendrían otra dimensión y otro espacio semántico, y la búsqueda devolvería resultados
  sin sentido. Para cambiarlo hay que vaciar la colección y reingestar todo.
- **`OLLAMA_REASONING` debe quedarse en `false`** con modelos de razonamiento. Con el
  razonamiento activo, las llamadas cortas agotan su presupuesto de tokens dentro del
  bloque `<think>` y devuelven texto vacío.
- El procesamiento de documentos corre en segundo plano. El `POST` responde de inmediato
  con estado `PROCESANDO`; el cliente consulta `GET /api/documents/{id}` hasta `LISTO`.
