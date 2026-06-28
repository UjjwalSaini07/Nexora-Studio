FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 nexora \
    && useradd --uid 1001 --gid nexora --shell /bin/sh --create-home nexora

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# generate_dataset.py.
COPY backend/ ./backend/
COPY dataset/ ./dataset/
RUN python3 dataset/generate_dataset.py --seed-dir dataset --out expanded \
    && chown -R nexora:nexora /app

WORKDIR /app/backend

# Run as non-root user for production security hardening.
USER nexora

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/v1/healthz || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
