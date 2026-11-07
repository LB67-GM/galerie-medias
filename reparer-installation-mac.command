#!/bin/bash
# Double-clic : réinstalle les paquets Python (nouvelle version du zip, ou galerie cassée).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f start-mac.command ]; then
  echo "start-mac.command introuvable dans : $PWD"
  echo "Décompressez tout l’archive dans un dossier, puis relancez ce fichier."
  exit 1
fi
rm -f .deps-ok
exec bash start-mac.command
