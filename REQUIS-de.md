# Galerie Médias — Voraussetzungen

Version **3.0**. Andere Sprachen: [Français](REQUIS-fr.md), [English](REQUIS-en.md), [Español](REQUIS-es.md).

Installation Schritt für Schritt: [INSTALL-de.md](INSTALL-de.md).

## System

- **Python 3.10 oder neuer**, mit `venv` und `pip`.
  - Windows: [python.org](https://www.python.org/downloads/), Haken bei **Add python.exe to PATH**. Nicht der Microsoft Store.
  - macOS: [python.org](https://www.python.org/downloads/) oder `brew install python`.
  - Debian oder Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`.
  - Fedora: `sudo dnf install python3`.
- **Internet** beim ersten Mal, um die Pakete zu laden.
- **ffmpeg** hilft bei Videodaten. Vorschaubilder und die Wiedergabe von iPhone-Videos (HEVC) nutzen die Datei aus dem Paket `imageio-ffmpeg`.
- SQLite ist in Python enthalten. Es steht nicht in der Liste unten.

## Python-Pakete

Dieselbe Liste steht in den drei anderen Sprachen. Die Startskripte lesen sie hier.

```requirements
cryptography>=43
fastapi>=0.115
uvicorn>=0.32
pillow>=11
pillow-heif>=0.21
numpy>=2.0
opencv-python-headless>=4.10
onnxruntime>=1.19
insightface>=0.7.3
imageio-ffmpeg>=0.5
python-multipart>=0.0.9
icloudpd>=1.32.0,<2
reverse-geocoder>=1.5.1,<2
scipy>=1.11
```

Installation von Hand, im Ordner der Seite:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
```

Windows: `python -m venv .venv`, dann `.venv\Scripts\python.exe scripts\lire_paquets.py --write .paquets.txt`, dann `.venv\Scripts\pip install -r .paquets.txt`. Die Skripte `preparer-python.bat`, `start-windows.bat`, `start-mac.command` und `start-linux.sh` erledigen diese Installation.

| Paket | Rolle |
|-------|--------|
| `cryptography` | Gespeicherte Passwörter (iCloud, E-Mail) |
| `fastapi`, `uvicorn`, `python-multipart` | Webseite |
| `pillow`, `pillow-heif` | Fotos, einschließlich HEIC |
| `numpy`, `opencv-python-headless`, `onnxruntime`, `insightface`, `scipy` | Gesichter |
| `imageio-ffmpeg` | Videoumsetzung für den Browser und den Fernseher |
| `icloudpd` | iCloud-Download, wenn Sie ihn nutzen |
| `reverse-geocoder` | Stadt aus dem GPS |

`insightface` ist die genauere Gesichtserkennung. Wenn sie sich nicht installiert, startet die Seite trotzdem: die Erkennung fällt auf OpenCV zurück. Eine spätere Installation fügt diese Erkennung hinzu.
