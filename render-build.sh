#!/usr/bin/env bash
# Render build script for DocuSense backend
set -o errexit

echo "==> Updating pip..."
python -m pip install --upgrade pip

echo "==> Pre-installing CPU-only PyTorch for fast, lightweight builds..."
python -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

echo "==> Installing Python dependencies from backend/requirements.txt..."
python -m pip install --no-cache-dir -r backend/requirements.txt

echo "==> Render build finished successfully!"
