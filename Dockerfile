# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + copy frontend dist ─────────────────────────────
FROM python:3.11-slim

# System deps for psycopg2, lxml, playwright, chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (cache-bust: v3)
COPY backend/ ./backend/

# Copy data files (H1B CSV + interview corpus)
COPY data/ ./data/

# Copy built frontend into place so FastAPI can serve it
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
