# Messages de démarrage. Langues : fr, en, es, de. Défaut : fr.

galerie_lang() {
  local raw="${LC_ALL:-${LANG:-fr}}"
  raw="${raw%%.*}"
  raw="${raw%%_*}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    fr|en|es|de) printf '%s\n' "$raw" ;;
    *) printf '%s\n' "fr" ;;
  esac
}

galerie_load_messages() {
  case "$(galerie_lang)" in
    en)
      MSG_TITLE="Galerie Médias"
      MSG_PHOTOS="Photos may stay on a USB disk."
      MSG_BASE="The database (SQLite, thumbnails, settings) stays on THIS computer, never on the USB disk."
      MSG_FIRST="First installation: preparing Python…"
      MSG_VENV_FAIL="Could not create .venv."
      MSG_INSTALLING="Installing programs (a few minutes). Internet is required."
      MSG_FW="Firewall: a password may be requested once. The rule stays after a restart."
      MSG_HERE="On this computer: https://127.0.0.1:8765"
      MSG_PHONE="Phone (same Wi-Fi):"
      MSG_FIRST_VISIT="First visit: continue to the site (home certificate). The site is HTTPS only."
      MSG_KEEP="Leave THIS window open while you use the gallery."
      MSG_STOP="To stop: close this window."
      MSG_SETTINGS="First time: Settings, set the photo folder, Save, then Index."
      MSG_STOPPED="Gallery stopped."
      MSG_PY_MISSING="Python 3.10 or newer is required."
      MSG_PY_OLD="Python 3.10 or newer is required (this version is too old)."
      MSG_PY_URL="Install it from https://www.python.org/downloads/ and start again."
      MSG_GUIDE="Guide: INSTALL-en.md"
      ;;
    es)
      MSG_TITLE="Galerie Médias"
      MSG_PHOTOS="Las fotos pueden quedarse en un disco USB."
      MSG_BASE="La base (SQLite, miniaturas, ajustes) permanece en ESTE ordenador, nunca en el USB."
      MSG_FIRST="Primera instalación: preparación de Python…"
      MSG_VENV_FAIL="No se pudo crear .venv."
      MSG_INSTALLING="Instalación de los programas (unos minutos). Hace falta Internet."
      MSG_FW="Cortafuegos: puede pedirse la contraseña una vez. La regla permanece tras un reinicio."
      MSG_HERE="En este ordenador: https://127.0.0.1:8765"
      MSG_PHONE="Teléfono (la misma Wi-Fi):"
      MSG_FIRST_VISIT="Primera visita: continúe hacia el sitio (certificado de casa). El sitio es solo HTTPS."
      MSG_KEEP="Deje ESTA ventana abierta mientras usa la galería."
      MSG_STOP="Para detener: cierre esta ventana."
      MSG_SETTINGS="Primera vez: Ajustes, indique la carpeta de las fotos, Guardar, luego Indexar."
      MSG_STOPPED="Galería detenida."
      MSG_PY_MISSING="Hace falta Python 3.10 o más reciente."
      MSG_PY_OLD="Hace falta Python 3.10 o más reciente (esta versión es demasiado antigua)."
      MSG_PY_URL="Instálelo desde https://www.python.org/downloads/ y vuelva a lanzar."
      MSG_GUIDE="Guía: INSTALL-es.md"
      ;;
    de)
      MSG_TITLE="Galerie Médias"
      MSG_PHOTOS="Die Fotos dürfen auf einem USB-Datenträger bleiben."
      MSG_BASE="Die Datenbank (SQLite, Miniaturen, Einstellungen) bleibt auf DIESEM Computer, nie auf dem USB-Datenträger."
      MSG_FIRST="Erste Installation: Python wird vorbereitet…"
      MSG_VENV_FAIL=".venv konnte nicht angelegt werden."
      MSG_INSTALLING="Programme werden installiert (einige Minuten). Internet ist nötig."
      MSG_FW="Firewall: einmal kann ein Passwort verlangt werden. Die Regel bleibt nach einem Neustart."
      MSG_HERE="Auf diesem Computer: https://127.0.0.1:8765"
      MSG_PHONE="Telefon (dasselbe WLAN):"
      MSG_FIRST_VISIT="Erster Besuch: weiter zur Seite gehen (Haus-Zertifikat). Die Seite ist nur HTTPS."
      MSG_KEEP="Lassen Sie DIESES Fenster offen, solange Sie die Galerie nutzen."
      MSG_STOP="Zum Beenden: dieses Fenster schließen."
      MSG_SETTINGS="Erstes Mal: Einstellungen, Fotoordner angeben, Speichern, dann Indexieren."
      MSG_STOPPED="Galerie beendet."
      MSG_PY_MISSING="Python 3.10 oder neuer ist erforderlich."
      MSG_PY_OLD="Python 3.10 oder neuer ist erforderlich (diese Version ist zu alt)."
      MSG_PY_URL="Installieren Sie es von https://www.python.org/downloads/ und starten Sie erneut."
      MSG_GUIDE="Anleitung: INSTALL-de.md"
      ;;
    *)
      MSG_TITLE="Galerie Médias"
      MSG_PHOTOS="Les photos peuvent rester sur un disque USB."
      MSG_BASE="La base (SQLite, miniatures, réglages) reste sur CET ordinateur, jamais sur le USB."
      MSG_FIRST="Première installation : préparation de Python…"
      MSG_VENV_FAIL="Échec de la création de .venv."
      MSG_INSTALLING="Installation des programmes (quelques minutes). Internet est nécessaire."
      MSG_FW="Pare-feu : un mot de passe peut être demandé une fois. La règle reste après un redémarrage."
      MSG_HERE="Sur cet ordinateur : https://127.0.0.1:8765"
      MSG_PHONE="Téléphone (même Wi-Fi) :"
      MSG_FIRST_VISIT="Premier passage : continuer vers le site (certificat de la maison). Le site est uniquement en HTTPS."
      MSG_KEEP="Laissez CETTE fenêtre ouverte pendant la galerie."
      MSG_STOP="Pour arrêter : fermez cette fenêtre."
      MSG_SETTINGS="Première fois : Paramètres, indiquez le dossier des photos, Enregistrer, puis Indexer."
      MSG_STOPPED="Galerie arrêtée."
      MSG_PY_MISSING="Python 3.10 ou plus récent est requis."
      MSG_PY_OLD="Python 3.10 ou plus récent est requis (version actuelle trop ancienne)."
      MSG_PY_URL="Installez-le depuis https://www.python.org/downloads/ puis relancez."
      MSG_GUIDE="Guide : INSTALL-fr.md"
      ;;
  esac
}
