FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

COPY cv-worker/pyproject.toml cv-worker/uv.lock* /app/cv-worker/
COPY infra/cascades /app/infra/cascades

WORKDIR /app/cv-worker
RUN uv sync --no-dev --frozen || uv sync --no-dev

COPY cv-worker /app/cv-worker

RUN useradd --create-home --shell /bin/bash cvuser && \
    mkdir -p /app/data/snapshots /app/data/models /app/data/demo && \
    chown -R cvuser:cvuser /app

USER cvuser

EXPOSE 9101

CMD ["uv", "run", "python", "-m", "app.main"]
