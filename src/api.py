import os
import json
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from psycopg_pool import AsyncConnectionPool

# --- 1. Configuration & Infrastructure Routing ---
DB_USER = os.getenv("POSTGRES_USER", "stef_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "stef_secure_password_2026")
DB_NAME = os.getenv("POSTGRES_DB", "synchrotron_telemetry")
DB_HOST = "stef-db"
REDIS_HOST = "stef-redis" 

CONN_STR = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

# --- 2. Connection Pools ---
pool = AsyncConnectionPool(CONN_STR, open=False)
# Create a dedicated connection pool allowing up to 1000 concurrent Redis connections
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST, 
    port=6379, 
    decode_responses=True, 
    max_connections=1000
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
    await redis_client.close()

# >>> THIS IS THE VARIABLE YOU TRIPPED OVER <<<
app = FastAPI(lifespan=lifespan, title="CERN Digital Twin API", version="2.0.0")

# --- 4. Strict Pydantic Schemas ---
class TelemetryPayload(BaseModel):
    sensor_id: int
    radiation_level: float

class CollisionPayload(BaseModel):
    pt1: float
    eta1: float
    phi1: float
    pt2: float
    eta2: float
    phi2: float

# --- 5. Endpoints ---
@app.post("/collision", summary="Ingest CMS collision event")
async def ingest_collision(payload: CollisionPayload):
    """Tier-0 Ingestion: Blasts relativistic kinematics into Redis RAM."""
    payload_json = payload.model_dump_json()
    await redis_client.lpush("cms_collisions", payload_json)
    return {"status": "queued", "message": "Collision event buffered."}

@app.get("/telemetry/{sensor_id}", summary="Retrieve recent telemetry (FAIR Compliant)")
async def get_telemetry(sensor_id: int):
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