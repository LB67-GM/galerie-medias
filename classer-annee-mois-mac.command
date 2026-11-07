#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ $# -lt 2 ]; then
  echo "Usage :"
  echo "  ./classer-annee-mois-mac.command /chemin/Vrac /chemin/Photos"
  echo "  ./classer-annee-mois-mac.command /chemin/Vrac /chemin/Photos --apply"
  echo
  echo "Copie SOURCE → DEST/Annee AAAA/Mois AAAA. Sans --apply : simulation."
  echo "Ensuite : sort_lieux.py -d DEST --all  (villes GPS)."
  exit 1
fi
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
exec "$PY" tools/sort_annee_mois.py "$@"
