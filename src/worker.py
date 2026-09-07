import os
import json
import asyncio
import signal
import logging
import polars as pl
import redis.asyncio as redis
from psycopg_pool import AsyncConnectionPool

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Infrastructure Setup ---
DB_USER = os.getenv("POSTGRES_USER", "stef_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "stef_secure_password_2026")
DB_NAME = os.getenv("POSTGRES_DB", "synchrotron_telemetry")
CONN_STR = f"postgresql://{DB_USER}:{DB_PASS}@stef-db:5432/{DB_NAME}"

class PhysicsWorkerPool:
    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.shutdown_event = asyncio.Event()
        self.redis = redis.Redis(host="stef-redis", port=6379, decode_responses=True)
        self.pool = AsyncConnectionPool(CONN_STR, open=False)

    async def setup_database(self):
        """Creates the results table for the Z Boson reconstructed masses."""
        await self.pool.open()
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS physics_events (
                        id SERIAL PRIMARY KEY,
                        pt1 FLOAT, eta1 FLOAT, phi1 FLOAT,
                        pt2 FLOAT, eta2 FLOAT, phi2 FLOAT,
                        invariant_mass FLOAT,
                        is_z_boson BOOLEAN,
                        processed_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                await conn.commit()

    async def _worker_task(self, worker_id: int):
        """The parallel worker executing the physics calculations."""
        while not self.shutdown_event.is_set():
            try:
                # 1. Pull from Redis (Blocks for 1 sec, then loops to check shutdown)
                result = await self.redis.blpop("cms_collisions", timeout=1.0)
                if not result:
                    continue 
                
                _, payload_json = result
                data = json.loads(payload_json)
                
                # 2. Polars Invariant Mass Calculation
                df = pl.DataFrame([data])
                df = df.with_columns(
                    mass=(
                        2 * pl.col("pt1") * pl.col("pt2") *
                        ((pl.col("eta1") - pl.col("eta2")).cosh() - (pl.col("phi1") - pl.col("phi2")).cos())
                    ).sqrt()
                ).with_columns(
                    is_z_boson=pl.col("mass").is_between(85.0, 95.0)
                )
                
                mass_val = df["mass"][0]
                is_z = df["is_z_boson"][0]
                
                if is_z:
                    logging.info(f"[Worker {worker_id}] Z Boson detected! Mass: {mass_val:.2f} GeV")
                
                # 3. PostgreSQL Storage
                async with self.pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """INSERT INTO physics_events 
                            (pt1, eta1, phi1, pt2, eta2, phi2, invariant_mass, is_z_boson) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                            (data['pt1'], data['eta1'], data['phi1'], data['pt2'], data['eta2'], data['phi2'], float(mass_val), bool(is_z))
                        )
                        await conn.commit()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"[Worker {worker_id}] Error: {e}")

    async def run(self):
        """Orchestrates the worker pool and handles SIGTERM."""
        await self.setup_database()
        logging.info(f"Spawning {self.num_workers} parallel physics workers...")
        workers = [asyncio.create_task(self._worker_task(i)) for i in range(self.num_workers)]
        
        # Wait until a shutdown signal is received
        await self.shutdown_event.wait()
        
        logging.warning("Graceful shutdown initiated. Cancelling idle workers...")
        for w in workers:
            w.cancel()
        
        # Safely close connections
        await self.pool.close()
        await self.redis.aclose()

async def main():
    pool = PhysicsWorkerPool(num_workers=4)
    loop = asyncio.get_running_loop()
    
    # OS Signals for Graceful Degradation (Module 3.5)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: pool.shutdown_event.set())
        
    await pool.run()

if __name__ == "__main__":
    asyncio.run(main())