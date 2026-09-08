"""Carga centralizada de configuracion y credenciales.

Regla: NINGUNA credencial tiene valor por defecto. Si falta, el proceso no
arranca (fail-fast). Un default hardcodeado en un repo publico es una
credencial publicada.
"""
import os

from psycopg.conninfo import make_conninfo


def require_env(name: str) -> str:
    """Devuelve la variable de entorno o aborta el arranque."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable de entorno obligatoria ausente o vacia: {name}. "
            "Definela en .env (ver .env.example). No existe valor por defecto."
        )
    return value


# --- PostgreSQL ---
DB_HOST = os.getenv("POSTGRES_HOST", "stef-db")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_USER = require_env("POSTGRES_USER")
DB_PASS = require_env("POSTGRES_PASSWORD")
DB_NAME = require_env("POSTGRES_DB")

# make_conninfo escapa el password correctamente. La f-string
# postgresql://user:pass@host se rompe si el password lleva @ : / ? # o espacio.
CONN_STR = make_conninfo(
    host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME
)

# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "stef-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = require_env("REDIS_PASSWORD")

# --- Cola de ingesta ---
QUEUE_NAME = "cms_collisions"
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "100000"))
