# ==============================================================================
# Stage 1: Builder (C-extension Compilation)
# ==============================================================================
FROM python:3.14-slim AS builder

# uv fijado por version: `:latest` hace el build irreproducible y mete en la
# imagen lo que sea que Astral publique ese dia (riesgo de cadena de suministro).

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /bin/

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

# uv.lock TIENE que entrar al build: sin el, `uv sync` reresuelve desde cero y
# las dependencias (todas con >=) se instalan en la version mas nueva que haya
# ese dia, lockfile ignorado. --locked falla si el lock esta desincronizado.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# ==============================================================================
# Stage 2: Runtime (Production Lightweight Image)
# ==============================================================================
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /bin/

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

# Usuario sin privilegios. Antes todo corria como root, y con `.:/app` montado
# eso da escritura como root sobre el repo del host.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

# Copy virtual environment from Stage 1
COPY --from=builder /opt/venv /opt/venv
# `COPY . .` depende de .dockerignore para no hornear .env, .git y data/
COPY --chown=appuser:appuser . .

USER appuser

CMD ["tail", "-f", "/dev/null"]
