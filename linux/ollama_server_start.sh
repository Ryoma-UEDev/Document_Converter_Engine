#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

OLLAMA_ROOT="$ROOT_DIR/.standalone/ollama"
OLLAMA_BIN="$OLLAMA_ROOT/bin"
OLLAMA_LIB="$OLLAMA_ROOT/lib/ollama"
export OLLAMA_MODELS="$OLLAMA_ROOT/models"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

mkdir -p "$OLLAMA_MODELS" "$OLLAMA_ROOT/imports"

if [[ -x "$OLLAMA_BIN/ollama" ]]; then
  OLLAMA_EXE="$OLLAMA_BIN/ollama"
  if [[ -d "$OLLAMA_LIB" ]]; then
    export LD_LIBRARY_PATH="$OLLAMA_LIB:${LD_LIBRARY_PATH:-}"
  fi
elif command -v ollama >/dev/null 2>&1; then
  OLLAMA_EXE="$(command -v ollama)"
else
  echo "Ollama was not found."
  echo "Run linux/setup_ollama_standalone.sh first, or install Ollama system-wide."
  exit 1
fi

echo
echo "Starting local Ollama server"
echo "----------------------------"
echo "API:"
echo "http://$OLLAMA_HOST/v1"
echo
echo "Models folder:"
echo "$OLLAMA_MODELS"
echo
echo "In Document Converter settings use:"
echo "Ollama Base URL: http://localhost:11434/v1"
echo
echo "Press Ctrl+C to stop the Ollama server."
echo

exec "$OLLAMA_EXE" serve
