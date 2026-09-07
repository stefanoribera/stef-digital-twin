import asyncio
import polars as pl
import httpx
import time

# We are executing inside the engine container, so 127.0.0.1 is the most direct network path
API_URL = "http://127.0.0.1:8000/collision"

async def fire_event(client: httpx.AsyncClient, payload: dict):
    """Fires a single HTTP POST request asynchronously."""
    try:
        response = await client.post(API_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"\n[FATAL] Beam Error: {e}")
        raise e

async def simulate_beam():
    print("[*] Loading CMS Dimuon Dataset into RAM...")
    df = pl.read_csv("data/Dimuon_DoubleMu.csv")
    kinematics = df.select(["pt1", "eta1", "phi1", "pt2", "eta2", "phi2"]).to_dicts()
    print(f"[*] Loaded {len(kinematics)} collision events.")
    print("[*] FIRING PARTICLE BEAM. PRESS CTRL+C TO ABORT.")
    
    # ARCHITECTURAL FIX: Explicit Backpressure
    # 1. Disable the 5-second timeout so the client waits for the API
    timeout = httpx.Timeout(None)
    # 2. Strict limits to prevent overwhelming the local Uvicorn worker
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=200)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        while True:
            start_time = time.time()
            # 3. Throttle the batch size to exactly match the connection pool
            batch = kinematics[:200]
            
            tasks = [fire_event(client, event) for event in batch]
            await asyncio.gather(*tasks)
            
            elapsed = time.time() - start_time
            print(f"[+] Blasted 200 events into the API in {elapsed:.3f} seconds.")

if __name__ == "__main__":
    asyncio.run(simulate_beam())