# ==============================================================================
# Stage 1: Builder (C-extension Compilation)
# ==============================================================================
FROM python:3.14-slim AS builder

# Inject official Astral 'uv' binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Force C++ driver to prevent linker errors on missing C++ symbols in wheel builds
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="/opt/venv" \
    CC="g++" \
    CXX="g++"

WORKDIR /app

# Install build tools for PostgreSQL C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev

# ==============================================================================
# Stage 2: Runtime (Production Lightweight Image)
# ==============================================================================
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT="/opt/venv" \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install PostgreSQL 18 client utilities for native backups
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg libpq5 postgresql-common && \
    /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y && \
    apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment from Stage 1
COPY --from=builder /opt/venv /opt/venv
COPY . .

CMD ["tail", "-f", "/dev/null"]