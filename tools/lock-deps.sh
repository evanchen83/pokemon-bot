#!/usr/bin/env bash
set -euo pipefail

echo "🔒 Locking dependencies in python:3.11-slim..."

docker run --rm \
  -v "$PWD:/app" \
  -w /app \
  python:3.11-slim bash -c "
    apt-get update && apt-get install -y curl git build-essential &&
    curl -sSL https://install.python-poetry.org | python3 - &&
    export PATH=\"/root/.local/bin:\$PATH\" &&
    poetry lock
  "

echo "✅ poetry.lock updated!"
