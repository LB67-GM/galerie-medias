#!/bin/bash
# Double-clic dans le Finder, ou : bash start-mac.command
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
# shellcheck source=scripts/galerie-text.sh
. "$ROOT/scripts/galerie-text.sh"
galerie_load_messages

echo
echo "  ${MSG_TITLE}"
echo
echo "  ${MSG_PHOTOS}"
echo "  ${MSG_BASE}"
echo "  ${MSG_GUIDE}"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "${MSG_PY_MISSING}"
  echo "${MSG_PY_URL}"
  exit 1
fi
if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"; then
  echo "${MSG_PY_OLD}"
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "${MSG_FIRST}"
  rm -rf .venv
  python3 -m venv .venv
  rm -f .deps-ok
fi

DEPS_HASH="$(python3 scripts/lire_paquets.py --hash)"
OLD_HASH=""
if [ -f .deps-ok ]; then
  OLD_HASH="$(tr -d '\r\n' < .deps-ok)"
fi
if [ "$OLD_HASH" != "$DEPS_HASH" ]; then
  echo "${MSG_INSTALLING}"
  .venv/bin/python -m pip install --upgrade pip
  python3 scripts/lire_paquets.py --write .paquets.txt
  .venv/bin/pip install -r .paquets.txt
  printf '%s\n' "$DEPS_HASH" > .deps-ok
fi

chmod +x scripts/allow_firewall_mac.sh 2>/dev/null || true
scripts/allow_firewall_mac.sh || true

LANIP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [ -z "$LANIP" ]; then
  LANIP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
echo "${MSG_FW}"
echo
echo "  ${MSG_HERE}"
if [ -n "$LANIP" ]; then
  echo "  ${MSG_PHONE} https://${LANIP}:8765"
fi
echo "  ${MSG_FIRST_VISIT}"
echo "  ${MSG_KEEP}"
echo "  ${MSG_STOP}"
echo
echo "  ${MSG_SETTINGS}"
echo "  ${MSG_GUIDE}"
echo
open "https://127.0.0.1:8765/" || true
exec .venv/bin/python run.py --portable serve --host 0.0.0.0 --port 8765
