#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONNOUSERSITE=1
unset PYTHONPATH || true

if [[ -x ".standalone/python/bin/python" ]]; then
  PYTHON_EXE="$ROOT_DIR/.standalone/python/bin/python"
elif [[ -d ".venv" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON_EXE="python"
else
  echo "Python environment missing."
  echo "Run linux/setup_requirements.sh first."
  exit 1
fi

if command -v xdg-open >/dev/null 2>&1; then
  (sleep 2; xdg-open "http://localhost:8000/" >/dev/null 2>&1 || true) &
fi

"$PYTHON_EXE" -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
