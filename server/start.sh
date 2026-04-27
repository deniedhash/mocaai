#!/usr/bin/env bash
# MOCA Phase 1 — Full startup sequence
# Run this from inside server/ directory: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚡ MOCA Phase 1 — Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Start infrastructure
echo ""
echo "▶ Starting Docker services (postgres + redis)..."
docker compose up -d
echo "   Waiting for services to be healthy..."
sleep 5

# 2. Run migrations
echo ""
echo "▶ Running Alembic migrations..."
PYTHONPATH="$SCRIPT_DIR" .venv/bin/alembic upgrade head

echo ""
echo "▶ Migrations complete."

# 3. Start FastAPI server (foreground)
echo ""
echo "▶ Starting MOCA server on port 8000..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PYTHONPATH="$SCRIPT_DIR" .venv/bin/uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir "$SCRIPT_DIR"
