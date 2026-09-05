import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from psycopg_pool import AsyncConnectionPool

# --- Configuration ---
DB_USER = os.getenv("POSTGRES_USER", "stef_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "stef_secure_password_2026")
DB_NAME = os.getenv("POSTGRES_DB", "synchrotron_telemetry")
DB_HOST = "stef-db"

CONN_STR = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

# --- Connection Pool ---
pool = AsyncConnectionPool(CONN_STR, open=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the databse pool lifecycle"""
    print("[*] Opening Async PostgreSQL Pool...")
    await pool.open()
    yield
    print("[*] Closing Async PostgreSQL Pool...")
    await pool.closed()

app = FastAPI(lifespan=lifespan, title="Synchrotron Telemetry API", version="1.0.0")

# --- Data Validation Scheme ---
class TelemetryPayload(BaseModel):
    sensor_id: int
    radiation_level: float

# --- Endpoints ---
@app.post("/telemetry", summary="Ingest single telemetry reading")
async def ingest_telemetry(payload: TelemetryPayload):
    """Receives a JSON payload and asynchronously writes it to the database."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
               "INSERT INTO telemetry (timestamp, sensor_id, radiation_level) VALUES (NOW(), %s, %s)",
                (payload.sensor_id, payload.radiation_level) 
            )
            await conn.commit()
    return {"status": "success", "message": f"Recorded sensor {payload.sensor_id}"}

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
        
    # --- FAIR Data Implementation: JSON-LD Wrapper ---
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
                "unitText": "mSv/h" # milliSieverts per hour
            } for r in records
        ]
    }