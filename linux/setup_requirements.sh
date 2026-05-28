#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo
echo "Document Converter Linux setup"
echo "------------------------------"

install_python_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Install Python 3, venv, and pip with your distro package manager, then rerun this script."
    exit 1
  fi

  local py_version=""
  if command -v python3 >/dev/null 2>&1; then
    py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  fi

  sudo apt-get update
  if [[ -n "$py_version" ]]; then
    sudo apt-get install -y "python${py_version}-venv" python3-venv python3-pip
  else
    sudo apt-get install -y python3 python3-venv python3-pip
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found."
  echo "Debian/Ubuntu detected. Installing Python packages with apt when available."
  install_python_packages
fi

tmp_venv="$(mktemp -d)"
if ! python3 -m venv "$tmp_venv/check" >/dev/null 2>&1; then
  echo "Python venv/ensurepip support is missing. Installing venv packages."
  rm -rf "$tmp_venv"
  install_python_packages
else
  rm -rf "$tmp_venv"
fi

"$SCRIPT_DIR/serversetup.sh"
