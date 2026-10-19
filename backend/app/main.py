"""Punto de entrada de la API.

Aqui se arma la aplicacion y, sobre todo, se decide que es publico y que no.
El enunciado exige que ningun endpoint quede expuesto sin autenticacion, asi
que la proteccion no se pone endpoint por endpoint -- que es justo como se
olvida -- sino al montar los routers, y ademas se comprueba al arrancar.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.routes import auth, chat, documents, health
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("var")

# ─────────────────────────────────────────────────────────────────────────────
# Rutas publicas. Lista explicita y cerrada: lo que no este aqui exige token.
# ─────────────────────────────────────────────────────────────────────────────
RUTAS_PUBLICAS: frozenset[str] = frozenset(
    {
        "/api/health",
        "/api/health/grafo",
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/refresh",
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando %s v%s", settings.APP_NAME, settings.APP_VERSION)
    init_db()
    logger.info("Base de datos lista")

    settings.storage_path.mkdir(parents=True, exist_ok=True)

    # Carga el corpus de futbol la primera vez. Si ya esta, no hace nada.
    from app.services.seed import sembrar_corpus_inicial

    try:
        sembrar_corpus_inicial()
    except Exception:
        # Sin corpus el agente rechaza todo, que es molesto pero no fatal:
        # el usuario siempre puede subir sus propios documentos.
        logger.exception("No se pudo sembrar el corpus inicial")

    # Precarga del modelo de embeddings. Cargarlo cuesta unos 13 segundos y,
    # sin esto, los paga la primera pregunta que haga un usuario: la diferencia
    # medida es de 25,6 s en frio frente a 11,7 s en caliente.
    try:
        from app.vectorstore.embeddings import get_embeddings

        get_embeddings().embed_query("calentamiento")
        logger.info("Modelo de embeddings en memoria")
    except Exception:
        logger.exception("No se pudo precargar el modelo de embeddings")

    logger.info(
        "Modelo: %s | Auth: %s | Umbral RAG: %.2f",
        settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama" else settings.HF_MODEL,
        settings.AUTH_PROVIDER,
        settings.RETRIEVAL_MIN_SCORE,
    )
    yield
    logger.info("Apagando")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Agente RAG construido con LangChain y LangGraph sobre un modelo de "
        "lenguaje local. Responde únicamente con información recuperada de su "
        "base de conocimiento vectorial, y rechaza de forma explícita cuando "
        "no encuentra respaldo suficiente."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Montaje de routers
#
# Dos routers con el mismo prefijo. El privado lleva la dependencia de
# autenticacion aplicada a todo lo que cuelgue de el, de modo que un endpoint
# nuevo nace protegido salvo que alguien lo ponga a proposito en el publico.
# ─────────────────────────────────────────────────────────────────────────────
api_publico = APIRouter(prefix="/api")
api_privado = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

api_publico.include_router(health.router)
api_publico.include_router(auth.router_publico)

api_privado.include_router(auth.router_privado)
api_privado.include_router(chat.router)
api_privado.include_router(documents.router)

app.include_router(api_publico)
app.include_router(api_privado)


# ─────────────────────────────────────────────────────────────────────────────
# Auditoria de proteccion
# ─────────────────────────────────────────────────────────────────────────────
def _usa_autenticacion(dependant) -> bool:
    """Busca get_current_user en el arbol de dependencias de la ruta."""
    for sub in dependant.dependencies:
        if sub.call is get_current_user or _usa_autenticacion(sub):
            return True
    return False


def auditar_rutas(aplicacion: FastAPI) -> list[str]:
    """Devuelve las rutas de /api que no exigen token y no son publicas."""
    desprotegidas: list[str] = []
    for ruta in aplicacion.routes:
        if not isinstance(ruta, APIRoute) or not ruta.path.startswith("/api"):
            continue
        if ruta.path in RUTAS_PUBLICAS:
            continue
        if not _usa_autenticacion(ruta.dependant):
            desprotegidas.append(f"{','.join(sorted(ruta.methods))} {ruta.path}")
    return desprotegidas


# Se ejecuta al importar el modulo: si alguien anade un endpoint al router
# equivocado, la aplicacion no arranca en vez de quedar expuesta en silencio.
_desprotegidas = auditar_rutas(app)
if _desprotegidas:
    raise RuntimeError(
        "Hay endpoints bajo /api sin autenticación y fuera de la lista de rutas "
        "públicas: " + "; ".join(_desprotegidas)
    )
logger.info(
    "Auditoría de seguridad: %d rutas públicas, el resto exige token",
    len(RUTAS_PUBLICAS),
)


# ─────────────────────────────────────────────────────────────────────────────
# Manejo de errores
# ─────────────────────────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def errores_de_validacion(request: Request, exc: RequestValidationError):
    """Traduce los errores de Pydantic a algo que el frontend pueda mostrar."""
    detalles = []
    for error in exc.errors():
        campo = ".".join(str(p) for p in error.get("loc", []) if p not in ("body", "query"))
        detalles.append({"campo": campo or "petición", "mensaje": error.get("msg", "")})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Los datos enviados no son válidos.", "errores": detalles},
    )


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception):
    """Ultimo recorte: registra la traza y devuelve un mensaje neutro.

    Nunca se devuelve el texto de la excepción al cliente: podría filtrar
    rutas del sistema o fragmentos de la configuración.
    """
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocurrió un error inesperado en el servidor."},
    )


@app.get("/", include_in_schema=False)
def raiz() -> dict:
    return {
        "servicio": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "documentacion": "/docs",
        "salud": "/api/health",
    }
