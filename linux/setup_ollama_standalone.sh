#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64)
    OLLAMA_ARCH="amd64"
    ;;
  aarch64|arm64)
    OLLAMA_ARCH="arm64"
    ;;
  *)
    echo "Unsupported Linux architecture: $ARCH"
    exit 1
    ;;
esac

OLLAMA_ROOT="$ROOT_DIR/.standalone/ollama"
OLLAMA_BIN="$OLLAMA_ROOT/bin"
OLLAMA_MODELS="$OLLAMA_ROOT/models"
OLLAMA_IMPORTS="$OLLAMA_ROOT/imports"
DOWNLOAD_DIR="$ROOT_DIR/.standalone/downloads"
OLLAMA_ARCHIVE="$DOWNLOAD_DIR/ollama-linux-${OLLAMA_ARCH}.tar.zst"
OLLAMA_URL="https://ollama.com/download/ollama-linux-${OLLAMA_ARCH}.tar.zst"

echo
echo "Document Converter local Ollama setup"
echo "------------------------------------"
echo "Install folder:"
echo "$OLLAMA_ROOT"
echo

mkdir -p "$DOWNLOAD_DIR" "$OLLAMA_BIN" "$OLLAMA_MODELS" "$OLLAMA_IMPORTS"

if [[ -x "$OLLAMA_BIN/ollama" ]]; then
  echo "Ollama already exists:"
  echo "$OLLAMA_BIN/ollama"
  exit 0
fi

if command -v curl >/dev/null 2>&1; then
  curl -fL "$OLLAMA_URL" -o "$OLLAMA_ARCHIVE"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$OLLAMA_ARCHIVE" "$OLLAMA_URL"
else
  echo "curl or wget is required to download Ollama."
  exit 1
fi

if ! tar --help 2>/dev/null | grep -q -- '--zstd'; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing zstd support for tar extraction..."
    sudo apt-get update
    sudo apt-get install -y zstd
  else
    echo "tar on this system does not support .tar.zst archives. Install zstd, then rerun this script."
    exit 1
  fi
fi

tar --zstd -xf "$OLLAMA_ARCHIVE" -C "$OLLAMA_ROOT"

if [[ ! -x "$OLLAMA_BIN/ollama" ]]; then
  echo "Ollama install did not create:"
  echo "$OLLAMA_BIN/ollama"
  exit 1
fi

echo
echo "Local Ollama setup complete."
echo "Models folder:"
echo "$OLLAMA_MODELS"
echo
echo "To start the server, run:"
echo "linux/ollama_server_start.sh"
