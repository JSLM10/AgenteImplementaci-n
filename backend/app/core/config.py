"""Configuracion centralizada, leida de variables de entorno.

Todo valor ajustable del sistema pasa por aqui. Ningun modulo lee os.environ
por su cuenta: asi hay un unico sitio donde mirar que se puede configurar y
cual es el valor por defecto.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
# backend/ -> raiz del repositorio
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Se leen los dos: el .env de la raiz (el que describe .env.example) y,
    # si existe, uno propio del backend que lo sobreescribe.
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Aplicacion ──────────────────────────────────────────────────────────
    APP_NAME: str = "VAR — Verificador Aumentado de Respuestas"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ─── Base de datos ───────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg://var:var@localhost:5432/vardb"

    # ─── Modelo de lenguaje ──────────────────────────────────────────────────
    LLM_PROVIDER: str = "ollama"  # ollama | huggingface
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:4b"
    # Razonamiento explicito del modelo. Desactivado: con el activo, las
    # llamadas cortas se quedan sin tokens dentro del bloque de pensamiento y
    # devuelven texto vacio, ademas de ir casi a la mitad de velocidad.
    OLLAMA_REASONING: bool = False
    HF_MODEL: str = "Qwen/Qwen2.5-1.5B-Instruct"
    LLM_TEMPERATURE: float = 0.1

    # ─── Embeddings ──────────────────────────────────────────────────────────
    # Fijos a proposito: la base vectorial se comparte entre local y nube, y
    # cambiarlos invalida todos los vectores ya guardados.
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDING_DIMENSIONS: int = 384
    COLLECTION_NAME: str = "var_conocimiento"

    # ─── RAG ─────────────────────────────────────────────────────────────────
    # Seis fragmentos cortos cubren mas terreno que cuatro largos y suman un
    # prompt parecido, asi que el tiempo de respuesta no se resiente.
    RETRIEVAL_K: int = 6
    # E5 comprime el rango de similitud: textos sin relacion rondan ya el 0,75.
    # El umbral filtra lo claramente ajeno, no ordena lo relevante; de ordenar
    # se encarga el troceado, y de decidir, el nodo evaluador.
    RETRIEVAL_MIN_SCORE: float = 0.35
    # Fragmentos cortos y enfocados. Con 1000 caracteres, un parrafo concreto
    # quedaba diluido entre otros del mismo bloque y no llegaba a recuperarse.
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 120
    ENABLE_GROUNDEDNESS_CHECK: bool = False
    MAX_HISTORY_MESSAGES: int = 6

    # ─── Autenticacion ───────────────────────────────────────────────────────
    AUTH_PROVIDER: str = "local"  # local | keycloak
    JWT_SECRET: str = "cambia-esta-clave-en-produccion-por-favor"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    KEYCLOAK_SERVER_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "var"
    KEYCLOAK_CLIENT_ID: str = "var-backend"

    # ─── Documentos ──────────────────────────────────────────────────────────
    MAX_UPLOAD_MB: int = 25
    STORAGE_DIR: str = "./storage"
    ENABLE_MEDIA_INGEST: bool = False

    # ─── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def storage_path(self) -> Path:
        path = Path(self.STORAGE_DIR)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    """Instancia unica. lru_cache evita releer el .env en cada peticion."""
    return Settings()


settings = get_settings()
