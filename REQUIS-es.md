# Galerie Médias — requisitos

Versión **3.0**. Otros idiomas: [Français](REQUIS-fr.md), [English](REQUIS-en.md), [Deutsch](REQUIS-de.md).

Instalación paso a paso: [INSTALL-es.md](INSTALL-es.md).

## Sistema

- **Python 3.10 o más reciente**, con `venv` y `pip`.
  - Windows: [python.org](https://www.python.org/downloads/), casilla **Add python.exe to PATH**. No la Microsoft Store.
  - macOS: [python.org](https://www.python.org/downloads/) o `brew install python`.
  - Debian o Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`.
  - Fedora: `sudo dnf install python3`.
- **Internet** la primera vez, para descargar los paquetes.
- **ffmpeg** ayuda con las fechas de los vídeos. Las miniaturas y la lectura de vídeos de iPhone (HEVC) usan el binario del paquete `imageio-ffmpeg`.
- SQLite va incluido en Python. No está en la lista de abajo.

## Paquetes Python

La misma lista está en los otros tres idiomas. Los scripts de arranque la leen aquí.

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

Instalación a mano, en la carpeta del sitio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
```

Windows: `python -m venv .venv`, luego `.venv\Scripts\python.exe scripts\lire_paquets.py --write .paquets.txt`, luego `.venv\Scripts\pip install -r .paquets.txt`. Los scripts `preparer-python.bat`, `start-windows.bat`, `start-mac.command` y `start-linux.sh` hacen esta instalación.

| Paquete | Papel |
|---------|--------|
| `cryptography` | Contraseñas guardadas (iCloud, correo) |
| `fastapi`, `uvicorn`, `python-multipart` | Sitio web |
| `pillow`, `pillow-heif` | Fotos, incluido HEIC |
| `numpy`, `opencv-python-headless`, `onnxruntime`, `insightface`, `scipy` | Rostros |
| `imageio-ffmpeg` | Conversión de vídeo para el navegador y el televisor |
| `icloudpd` | Descarga de iCloud, si la usa |
| `reverse-geocoder` | Ciudad a partir del GPS |

`insightface` es el motor de rostros más preciso. Si no se instala, el sitio arranca igual: la detección pasa a OpenCV. Volver a lanzar la instalación más tarde añade ese motor.
