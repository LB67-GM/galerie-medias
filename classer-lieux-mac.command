#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ $# -lt 1 ]; then
  echo "Usage :"
  echo "  ./classer-lieux-mac.command /chemin/Photos"
  echo "  ./classer-lieux-mac.command /chemin/Photos --apply"
  echo
  echo "sort_lieux : dossiers ville d’après le GPS (même outil que Classer)."
  echo "Sans --apply : simulation."
  exit 1
fi
DEST="$1"
shift
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
exec "$PY" tools/sort_lieux.py -d "$DEST" --all "$@"
