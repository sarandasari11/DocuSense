#!/usr/bin/env bash
# Render build script for DocuSense backend
set -o errexit

echo "==> Updating pip..."
python -m pip install --upgrade pip

echo "==> Installing Python dependencies from backend/requirements.txt..."
python -m pip install -r backend/requirements.txt

echo "==> Render build finished successfully!"
