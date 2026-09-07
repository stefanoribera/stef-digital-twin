# EOSC Digital Twin PoC: Asynchronous High-Energy Physics Pipeline

![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![PostgreSQL 18](https://img.shields.io/badge/PostgreSQL-18-blue.svg)
![EOSC Alignment](https://img.shields.io/badge/EOSC--Synergy-D3.1%20%7C%20D3.3-success.svg)

## Executive Summary
This repository contains a Proof-of-Concept (PoC) data pipeline engineered to simulate the ingestion, buffering, and processing of a High-Energy Physics Digital Twin. 

The architecture is strictly aligned with the **European Open Science Cloud (EOSC-Synergy)** guidelines, specifically targeting:
*   **D3.1 (Software Quality):** Containerized, decoupled microservices with graceful degradation.
*   **D3.3 (FAIR Data Principles):** Implementation of JSON-LD metadata for machine-actionable interoperability.

## 🏗️ System Architecture

The system implements an event-driven, asynchronous microservice architecture to prevent I/O blocking during high-velocity data ingestion.

1. **Tier-0: API Gateway (`FastAPI`)**
   * Acts as the ingestion node. Receives raw telemetry and immediately offloads it to the message broker.
   * Implements connection pooling and HTTP backpressure to survive Denial of Service (DoS) load spikes.
   * Injects JSON-LD metadata into responses to satisfy FAIR interoperability standards.
2. **Tier-1: Message Broker (`Redis 7.2`)**
   * In-memory queue decoupling the ingestion layer from the compute layer.
3. **Tier-2: Compute Node (`Python asyncio` + `Polars`)**
   * A headless pool of asynchronous workers.
   * Pulls payloads from Redis and utilizes the Rust-backed `Polars` engine for multi-threaded, vectorized kinematic calculations.
4. **Tier-3: Sovereign State (`PostgreSQL 18`)**
   * Persistent storage layer for processed physics events.

## ⚛️ The Physics Payload: CERN CMS Open Data
To validate the pipeline under realistic computational loads, the system processes public collision data from the **CERN CMS Detector** (Dimuon dataset). 

The `Polars` compute workers calculate the **Invariant Mass ($M$)** of muon pairs using relativistic kinematics:
$$M = \sqrt{2 p_{t1} p_{t2} (\cosh(\eta_1 - \eta_2) - \cos(\phi_1 - \phi_2))}$$

**Current Benchmark Metrics:**
* Successfully ingested and processed **4,108 relativistic collision events**.
* Isolated **105 Z-Boson mass resonances** (~91 GeV) under heavy concurrent load.

## 🛡️ Site Reliability Engineering (SRE) Features
This pipeline is engineered for resilience in HPC/Grid environments:
* **Graceful Shutdown:** The `asyncio` event loop intercepts OS-level `SIGTERM` signals (e.g., during a Kubernetes pod scale-down). It aborts idle tasks, finishes active database transactions, and closes connection pools cleanly to guarantee zero data corruption.
* **Resource Capping:** Docker Compose limits are strictly enforced to prevent container starvation.
* **Connection Pooling:** Redis and PostgreSQL connections are pooled to prevent file descriptor exhaustion (`MaxConnectionsError`) during high-throughput spikes.

## 🚀 Quick Start (Local Deployment)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Clone the repository
git clone [https://github.com/yourusername/eosc-digital-twin-poc.git](https://github.com/yourusername/eosc-digital-twin-poc.git)
cd eosc-digital-twin-poc

# 2. Spin up the infrastructure (Detached mode)
docker compose up -d stef-db stef-redis stef-api stef-worker

# 3. Monitor the compute workers
docker compose logs -f stef-worker
```

## 🗺️ Future Architectural Enhancements
- [ ] **Memory Optimization:** Implement Zero-Copy memory architecture using Apache Arrow and ADBC (`adbc_driver_postgresql`) to eliminate Python object overhead during database ingestion.
- [ ] **Observability:** Deploy an isolated Presentation Layer (Streamlit) communicating strictly via REST to visualize real-time particle resonances.
- [ ] **Quality Assurance:** Implement CI/CD Quality Gates (Pytest, strict 70% coverage threshold) to fulfill automated deployment requirements.
- [ ] **Grid Readiness:** Prepare the container ecosystem for rootless execution (`udocker`) to comply with European supercomputer security policies.

---
*Engineered as a technical artifact for EOSC infrastructure integration and evaluation.*
