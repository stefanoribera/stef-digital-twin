# EOSC Digital Twin PoC: Asynchronous High-Energy Physics Pipeline

## Executive Summary

This repository contains a Proof-of-Concept (PoC) data pipeline I engineered to simulate the ingestion, buffering, processing, and zero-copy visualization of a High-Energy Physics Digital Twin.

I aligned the architecture strictly with **European Open Science Cloud (EOSC-Synergy)** guidelines:

* **D3.1 (Software Quality):** Containerized, decoupled microservices built via component-aware dependency trees.
* **D3.3 (FAIR Data Principles):** Implementation of JSON-LD metadata for machine-actionable interoperability.

## 🏗️ System Architecture

I shattered the monolithic infrastructure into an event-driven, fully asynchronous microservice architecture spanning five atomic tiers over an isolated Docker network (`stef_net`).

1. **Tier-0: API Gateway (`FastAPI`)**
* Acts as the ingestion node. I deployed ASGI middleware to reject massive payloads before memory allocation.
* Executes an atomic Lua script to enforce HTTP backpressure, securely offloading telemetry to the broker.


2. **Tier-1: Message Broker (`Redis 7.2`)**
* In-memory FIFO queue decoupling the ingestion layer from the compute layer.


3. **Tier-2: Compute Engine (`Python asyncio` + `Polars`)**
* A headless pool of asynchronous workers. Pulls payloads from Redis and utilizes the Rust-backed Polars engine for hardware-squeezed, vectorized kinematic calculations.


4. **Tier-3: Sovereign State (`PostgreSQL 18` + `pgvector`)**
* Persistent storage layer for validated physics events, mounted outside the container lifecycle to prevent version boundary corruption.


5. **Tier-4: Presentation Layer (`Streamlit` + `PyArrow`)**
* Zero-copy visualization dashboard. Intercepts raw Inter-Process Communication (IPC) binary streams via ADBC drivers, entirely bypassing JSON serialization overhead.



## ⚛️ The Physics Payload: CERN CMS Open Data

To validate the pipeline under realistic computational loads, the system processes public collision data from the **CERN CMS Detector** (Dimuon dataset).

The `Polars` compute workers calculate the **Invariant Mass ($M$)** of muon pairs using relativistic kinematics:


$$M = \sqrt{2 p_{t1} p_{t2} (\cosh(\eta_1 - \eta_2) - \cos(\phi_1 - \phi_2))}$$

**Current Benchmark Metrics:**

* Successfully ingested and processed **4,108 relativistic collision events**.
* Isolated **105 Z-Boson mass resonances** (~91.2 GeV) under heavy concurrent load.

## 🛡️ Site Reliability Engineering (SRE) Features

I engineered this pipeline for absolute resilience in distributed Grid environments:

* **Deterministic Deployment:** The `deploy.sh` orchestrator probes TCP sockets (`pg_isready`) to enforce strict boot sequencing, eliminating race conditions between the State and Compute tiers.
* **Zero-Copy Memory Access:** I implemented ADBC (`adbc_driver_postgresql`) to stream database tables directly into Apache Arrow binary format, instantiating DataFrames without memory replication.
* **Restricted Kernel Footprint:** I dropped all unnecessary OS capabilities (`cap_drop: [ALL]`) across the compute and presentation containers to minimize the attack surface.
* **Component-Aware Compilation:** I injected specific `uv` build arguments (`api`, `compute`, `ui`) to ensure containers compile only the absolute minimum required dependencies.

## 🚀 Quick Start (Local Deployment)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Clone the repository
git clone https://github.com/stefanoribera/stef-digital-twin.git
cd stef-digital-twin

# 2. Sanitize the host environment (Clear ghost networks and poisoned volumes)
docker compose -f compose.state.yml down -v
docker network prune -f

# 3. Execute deterministic infrastructure deployment
./deploy.sh

# 4. Ingest physics payloads to test the pipeline
uv run python -m src.ingest

```

*Access the Zero-Copy Dashboard at `[http://127.0.0.1:8501](http://127.0.0.1:8501)*`

## 🗺️ Future Architectural Enhancements

* [x] **Memory Optimization:** Implement Zero-Copy memory architecture using Apache Arrow and ADBC.
* [x] **Observability:** Deploy an isolated Presentation Layer (Streamlit) communicating strictly via REST IPC streams.
* [ ] **High Availability:** Refactor the deployment topology into Kubernetes Helm charts for auto-scaling Compute nodes.
* [ ] **Quality Assurance:** Implement CI/CD Quality Gates (Pytest, strict 70% coverage threshold) to fulfill automated deployment requirements.

---

*Engineered as a technical artifact for EOSC infrastructure integration and evaluation.*