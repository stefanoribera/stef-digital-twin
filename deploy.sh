#!/bin/bash
set -e

echo "[*] Initializing EOSC Zero-Copy Infrastructure..."

echo "[*] Establishing isolated internal network (stef_net)..."
docker network create stef_net 2>/dev/null || true

echo "[*] Deploying Tier-3 Sovereign State (PostgreSQL) and Tier-1 Broker (Redis)..."
docker compose -f compose.state.yml -f compose.broker.yml up -d

echo "[*] Probing PostgreSQL TCP socket for deterministic readiness..."
RETRIES=0
# Dynamic polling loop via the pg_isready utility
until docker compose -f compose.state.yml exec -T stef-db pg_isready -U stef_admin -d synchrotron_telemetry > /dev/null 2>&1; do
    if [ $RETRIES -ge 30 ]; then
        echo "[-] FATAL: PostgreSQL failed to initialize within 30 seconds."
        exit 1
    fi
    echo "[-] Waiting for database allocation (Attempt $((RETRIES+1))/30)..."
    sleep 1
    RETRIES=$((RETRIES+1))
done

echo "[+] Database is strictly operational. State layer secured."
echo "[*] Compiling component-aware Docker images (API & Worker)..."
docker compose -f compose.api.yml -f compose.worker.yml build

echo "[*] Deploying Tier-2 Compute Engine..."
docker compose -f compose.api.yml -f compose.worker.yml up -d

echo "[+] Phase 4 Backend Infrastructure is ONLINE."
