#!/usr/bin/env bash
# Local development: FastAPI on 5001, Vite on 5173 proxying /chat to it.
# Open http://localhost:5173
set -euo pipefail

if [ -f .env ]; then
  set -a; source .env; set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Set ANTHROPIC_API_KEY first: put it in .env or export ANTHROPIC_API_KEY=..." >&2
  exit 1
fi

python3 -m uvicorn server.app:app --port 5001 --reload &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT

cd frontend && npm run dev
