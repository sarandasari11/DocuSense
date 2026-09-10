#!/usr/bin/env bash
# Render startup script for DocuSense backend
set -o errexit

echo "==> Running Alembic database migrations..."
cd backend
python -m alembic upgrade head

PORT="${PORT:-8000}"
echo "==> Starting DocuSense FastAPI server on 0.0.0.0:${PORT}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
