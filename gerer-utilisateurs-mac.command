#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Galerie Médias — comptes"
echo
echo "  Lister :              ./gerer-utilisateurs-mac.command --list"
echo "  Créer :               ./gerer-utilisateurs-mac.command --create IDENTIFIANT --role lecture"
echo "  Mot de passe / pause : ./gerer-utilisateurs-mac.command --set-password IDENTIFIANT"
echo "  Déverrouiller :       ./gerer-utilisateurs-mac.command --unlock IDENTIFIANT"
echo "  Effacer :             ./gerer-utilisateurs-mac.command --delete IDENTIFIANT --yes"
echo
echo "Aucun e-mail. Compte en pause (3 essais) ou mot de passe oublié : --set-password."
echo
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
exec "$PY" run.py --portable users "$@"
