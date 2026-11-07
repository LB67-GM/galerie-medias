#!/bin/bash
# Double-clic : réapplique le pare-feu Mac (règle persistante).
cd "$(dirname "$0")"
echo
echo "  Autorisation permanente du pare-feu (Python : site 8765 et TV 8766)."
echo "  Mot de passe de session si demandé."
echo
rm -f .firewall-ok
chmod +x scripts/allow_firewall_mac.sh 2>/dev/null || true
scripts/allow_firewall_mac.sh --force || true
echo
echo "  Terminé. La règle reste après un redémarrage."
echo "  Sur cet Mac : https://127.0.0.1:8765"
LANIP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [ -z "$LANIP" ]; then
  LANIP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [ -n "$LANIP" ]; then
  echo "  iPhone (même Wi-Fi) : https://${LANIP}:8765"
fi
echo
read -r -p "Fermer cette fenêtre : entrée. " _
