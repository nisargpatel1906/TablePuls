FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

COPY backend/pyproject.toml backend/uv.lock* /app/backend/
COPY packages /app/packages
COPY infra/cascades /app/infra/cascades

WORKDIR /app/backend
RUN uv sync --no-dev --frozen || uv sync --no-dev

COPY backend /app/backend

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data/snapshots /app/data/models && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
