# Galerie Médias — requirements

Version **3.0**. Other languages: [Français](REQUIS-fr.md), [Español](REQUIS-es.md), [Deutsch](REQUIS-de.md).

Step-by-step install: [INSTALL-en.md](INSTALL-en.md).

## System

- **Python 3.10 or newer**, with `venv` and `pip`.
  - Windows: [python.org](https://www.python.org/downloads/), tick **Add python.exe to PATH**. Not the Microsoft Store.
  - macOS: [python.org](https://www.python.org/downloads/) or `brew install python`.
  - Debian or Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`.
  - Fedora: `sudo dnf install python3`.
- **Internet** the first time, to download the packages.
- **ffmpeg** helps with video dates. Thumbnails and iPhone video playback (HEVC) use the binary shipped by the `imageio-ffmpeg` package.
- SQLite is included in Python. It is not in the list below.

## Python packages

The same list is in the three other languages. The start scripts read it here.

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

Manual install, in the site folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
```

Windows: `python -m venv .venv`, then `.venv\Scripts\python.exe scripts\lire_paquets.py --write .paquets.txt`, then `.venv\Scripts\pip install -r .paquets.txt`. The scripts `preparer-python.bat`, `start-windows.bat`, `start-mac.command` and `start-linux.sh` do this install.

| Package | Role |
|---------|------|
| `cryptography` | Stored passwords (iCloud, email) |
| `fastapi`, `uvicorn`, `python-multipart` | Web site |
| `pillow`, `pillow-heif` | Photos, including HEIC |
| `numpy`, `opencv-python-headless`, `onnxruntime`, `insightface`, `scipy` | Faces |
| `imageio-ffmpeg` | Video conversion for the browser and the television |
| `icloudpd` | iCloud download, if you use it |
| `reverse-geocoder` | City from GPS |

`insightface` is the more precise face engine. If it does not install, the site still starts: detection falls back to OpenCV. Running the install again later adds that engine.
