# Production Dockerfile for Cafeasy (FastAPI + ChromaDB + Hybrid RAG)
FROM python:3.11-slim as base

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install minimal system dependencies (curl for healthchecks, build-essential for C-extensions if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY rag/ ./rag/
COPY scraper/ ./scraper/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Run initial ingestion if vector DB is not yet built
RUN python scripts/ingest.py || true

# Expose server port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Launch production server with Uvicorn (binds to platform $PORT dynamically)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
