#!/bin/bash
# Autorise Python de la galerie dans le pare-feu macOS (liste d’apps persistante).
# UAC / mot de passe seulement si Python n’est pas déjà autorisé.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MARKER="$ROOT/.firewall-ok"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$ROOT/.venv/bin/python3"
fi
if [ ! -x "$PY" ]; then
  exit 0
fi
REAL="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$PY" 2>/dev/null || echo "$PY")"
FW="/usr/libexec/ApplicationFirewall/socketfilterfw"
if [ ! -x "$FW" ]; then
  : > "$MARKER"
  exit 0
fi

already=0
if "$FW" --listapps 2>/dev/null | grep -F "$REAL" >/dev/null 2>&1; then
  already=1
fi
if [ "$already" = 1 ] && [ "${1:-}" != "--force" ]; then
  : > "$MARKER"
  exit 0
fi

echo "Pare-feu Mac : autorisation permanente de la galerie (mot de passe de la session si demandé)…"
if osascript -e "do shell script \"$FW --add \\\"$REAL\\\" ; $FW --unblockapp \\\"$REAL\\\"\" with administrator privileges" >/dev/null 2>&1; then
  echo "Pare-feu : Python autorisé (conserve après redémarrage)."
  : > "$MARKER"
else
  echo "Pare-feu : pas d’autorisation admin — la galerie reste utilisable sur cet ordinateur."
  : > "$MARKER"
fi
exit 0
