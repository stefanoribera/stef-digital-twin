import os
import time
import polars as pl
import numpy as np
import psycopg
from datetime import datetime, timedelta

# 1. Configuration & Secrets
DB_USER = os.getenv("POSTGRES_USER", "stef_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "stef_secure_password_2026")
DB_NAME = os.getenv("POSTGRES_DB", "synchrotron_telemetry")
DB_HOST = "stef-db" # Resolves automatically via Docker internal DNS
DB_PORT = "5432"

CONN_STR = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def setup_database():
    """Creates the telemetry table if it doesn't exist."""
    print("[*] Verifying database schema...")
    with psycopg.connect(CONN_STR) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    sensor_id INTEGER NOT NULL,
                    radiation_level FLOAT NOT NULL
                );
            """)
            # Create an index on timestamp for fast time-series queries
            cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry(timestamp);")
        conn.commit()

def generate_telemetry(num_rows: int = 1_000_000) -> pl.DataFrame:
    """Generates 1M rows using Rust/C memory allocation (Zero Python loops)."""
    print(f"[*] Generating {num_rows} rows of simulated Synchrotron telemetry...")
    start_time = time.time()
    
    df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 1) + timedelta(seconds=num_rows-1),
            interval="1s",
            eager=True
        ),
        "sensor_id": np.random.randint(1, 101, num_rows),
        "radiation_level": np.random.normal(loc=15.0, scale=2.5, size=num_rows)
    })
    
    print(f"[+] Generation complete in {time.time() - start_time:.3f} seconds.")
    return df

def bulk_insert_telemetry(df: pl.DataFrame):
    """Streams data into Postgres using the ultra-fast COPY protocol."""
    print("[*] Initiating binary bulk insert via COPY protocol...")
    start_time = time.time()
    
    # Convert Polars DataFrame to a list of tuples for psycopg
    records = df.rows()
    
    with psycopg.connect(CONN_STR) as conn:
        with conn.cursor() as cur:
            with cur.copy("COPY telemetry (timestamp, sensor_id, radiation_level) FROM STDIN") as copy:
                for record in records:
                    copy.write_row(record)
        conn.commit()
        
    print(f"[+] Bulk insert of {len(df)} rows completed in {time.time() - start_time:.3f} seconds.")

if __name__ == "__main__":
    print("=== OPERATION DIGITAL TWIN: DATA INGESTION ===")
    setup_database()
    telemetry_df = generate_telemetry(1_000_000)
    bulk_insert_telemetry(telemetry_df)
    print("=== INGESTION SUCCESSFUL ===")