import secrets

import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Path, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from psycopg_pool import AsyncConnectionPool

from src.config import (
    CONN_STR,
    MAX_QUEUE_DEPTH,
    QUEUE_NAME,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    require_env,
)
from src.schemas import CollisionPayload, TelemetryPayload  # noqa: F401

# --- 1. Configuration & Infrastructure Routing ---
# Las credenciales viven en src/config.py y no tienen valor por defecto.
INGEST_API_KEY = require_env("INGEST_API_KEY")

# --- 2. Connection Pools ---
pool = AsyncConnectionPool(CONN_STR, open=False)
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    max_connections=64,
)
redis_client = redis.Redis(connection_pool=redis_pool)

# --- 3. Server Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[*] Opening Async PostgreSQL Pool...")
    await pool.open()
    yield
    print("[*] Closing Async PostgreSQL Pool...")
    await pool.close()
    await redis_client.aclose()

class _BodyTooLarge(HTTPException):
    """Debe heredar de HTTPException.

    FastAPI envuelve el parseo del cuerpo en `except Exception -> HTTP 400`,
    asi que una excepcion propia se convertiria en un 400 generico. Solo
    HTTPException se re-lanza intacta y llega al manejador de Starlette.
    """

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request body too large.",
        )


class BodySizeLimitMiddleware:
    """Rechaza cuerpos grandes ANTES de leerlos.

    Hace falta un middleware ASGI, no una dependencia: FastAPI lee y parsea el
    cuerpo entero antes de resolver Depends(require_api_key), asi que la clave
    de API no protege de un POST de 1 GiB. Comprobado: un body corrupto sin
    clave devuelve 422, no 401.
    """

    def __init__(self, app, max_bytes: int = 16 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await self._reject(send)
            return

        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await self._reject(send)

    @staticmethod
    async def _reject(send):
        body = b'{"detail":"Request body too large."}'
        await send({
            "type": "http.response.start",
            "status": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "headers": [(b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})


app = FastAPI(lifespan=lifespan, title="CERN Digital Twin API", version="2.0.0")

# El payload legitimo son 6 floats: 16 KiB es holgadisimo.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=16 * 1024)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 sin reflejar la entrada del atacante.

    El handler por defecto de FastAPI incluye el campo `input` en la respuesta.
    Si ese input contiene Infinity o NaN (json.loads los acepta), json.dumps
    revienta al serializar la respuesta y el 422 se convierte en un 500 no
    controlado con traceback completo en el log. Repetirlo llena el disco.
    """
    detail = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        content={"detail": detail})

# Comprobar el tope y encolar en una sola operacion atomica. Hacerlo en dos
# pasos (LLEN y luego LPUSH) deja una ventana en la que N peticiones
# concurrentes ven hueco a la vez y todas encolan, saltandose el limite.
#
# RPUSH, no LPUSH: el worker consume con BLPOP, que saca por la cabeza. Con
# LPUSH se encolaba tambien por la cabeza, o sea una PILA: bajo carga los
# eventos antiguos no se procesaban nunca. RPUSH por la cola + BLPOP por la
# cabeza es una cola FIFO de verdad.
_PUSH_IF_SPACE = """
if redis.call('LLEN', KEYS[1]) >= tonumber(ARGV[2]) then
  return 0
end
return redis.call('RPUSH', KEYS[1], ARGV[1])
"""

# --- 4. Authentication ---
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Autenticacion de la ruta de escritura. compare_digest evita timing attacks."""
    expected = INGEST_API_KEY.encode("utf-8")
    provided = (api_key or "").encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )

# --- 5. Endpoints ---
@app.post(
    "/collision",
    summary="Ingest CMS collision event",
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_collision(payload: CollisionPayload):
    """Tier-0 Ingestion: encola cinematica relativista validada en Redis."""
    # Backpressure explicita: sin este tope la cola crece hasta agotar la RAM
    # del broker, porque nada limita el ritmo de POST /collision.
    depth = await redis_client.eval(
        _PUSH_IF_SPACE, 1, QUEUE_NAME, payload.model_dump_json(), str(MAX_QUEUE_DEPTH)
    )
    if not depth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion queue saturated. Retry later.",
            headers={"Retry-After": "1"},
        )

    return {"status": "queued", "queue_depth": depth}

@app.get("/telemetry/{sensor_id}", summary="Retrieve recent telemetry (FAIR Compliant)")
async def get_telemetry(sensor_id: int = Path(ge=1, le=100)):
    """Fetches the last 10 readings for a specific sensor, wrapped in JSON-LD."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT timestamp, radiation_level FROM telemetry WHERE sensor_id = %s ORDER BY timestamp DESC LIMIT 10",
                (sensor_id,)
            )
            records = await cur.fetchall()

    if not records:
        raise HTTPException(status_code=404, detail="Sensor data not found.")

    # FAIR Data Implementation (EOSC D3.3)
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Synchrotron Radiation Telemetry - Sensor {sensor_id}",
        "description": "Time-series radiation levels recorded by generic synchrotron sensor.",
        "identifier": sensor_id,
        "data": [
            {
                "@type": "Observation",
                "observationDate": str(r[0]),
                "value": r[1],
                "unitText": "mSv/h"
            } for r in records
        ]
    }
