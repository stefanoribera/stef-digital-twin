# ==============================================================================
# Stage 1: Component-Aware Builder
# ==============================================================================
FROM python:3.14-slim AS builder

ARG UV_VERSION=0.12.10
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT="/opt/venv" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Require the deployment orchestrator to specify the architectural component
ARG COMPONENT
RUN if [ -z "$COMPONENT" ]; then echo "ERROR: COMPONENT build arg is required (api, compute, or ui)" && exit 1; fi

COPY pyproject.toml uv.lock ./

# Compile ONLY the universal base dependencies AND the specific target component
RUN uv sync --locked --no-install-project --no-dev --extra ${COMPONENT}

# ==============================================================================
# Stage 2: Runtime (Production Lightweight Image)
# ==============================================================================
FROM python:3.14-slim

ARG UV_VERSION=0.12.10
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT="/opt/venv" \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*

# Enforce EGI rootless execution standard
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

# Extract the isolated environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . .

USER appuser

CMD ["tail", "-f", "/dev/null"]

