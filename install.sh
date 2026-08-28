#!/usr/bin/env bash
# rw_blueprint install script
# Usage:
#   ./install.sh              # install to user tool dir
#   ./install.sh --system     # install system-wide
#   ./install.sh --dev        # dev install (editable, with dev extras)
#   ./install.sh --rebuild    # force rebuild + reinstall from source
#
# Requires: uv (https://docs.astral.sh/uv/) — install via:
#   curl -LsSf https://astral.sh/uv/install.sh | sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="rw_blueprint"
ENTRY="rw-blueprint"
ENTRY_MCP="rw-blueprint-mcp"
MODE="user"
DEV=0
REBUILD=0

for arg in "$@"; do
  case "$arg" in
    --system) MODE="system" ;;
    --dev)    DEV=1 ;;
    --rebuild) REBUILD=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

# Sanity: uv available
if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' not found. install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

cd "$REPO_ROOT"

if [[ "$DEV" -eq 1 ]]; then
  echo "[install] dev mode: editable install with dev extras"
  uv sync --group dev
  echo
  echo "[install] OK. activate the venv: source .venv/bin/activate"
  echo "  then run: $ENTRY --help"
  exit 0
fi

if [[ "$REBUILD" -eq 1 ]]; then
  echo "[install] rebuild: removing dist/ + any existing tool install"
  rm -rf dist build
  uv tool uninstall "$PKG_NAME" 2>/dev/null || true
fi

echo "[install] building wheel + sdist"
uv build

WHEEL=$(ls dist/*.whl | head -1)
echo "[install] wheel: $WHEEL"

case "$MODE" in
  system)
    echo "[install] installing system-wide (requires sudo)"
    sudo uv tool install --force "$WHEEL"
    ;;
  user|*)
    echo "[install] installing to user tool dir (no sudo)"
    uv tool install --force "$WHEEL"
    ;;
esac

echo
echo "[install] OK."
echo "  $ENTRY      — CLI (validate, generate, probe, reconcile, mcp)"
echo "  $ENTRY_MCP  — MCP server (stdio, for agent clients)"
echo
echo "verify:"
echo "  $ENTRY --help"
