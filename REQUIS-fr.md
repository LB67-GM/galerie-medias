# Galerie Médias — prérequis

Version **4.1**. Autres langues : [English](REQUIS-en.md), [Español](REQUIS-es.md), [Deutsch](REQUIS-de.md).

Installation pas à pas : [INSTALL-fr.md](INSTALL-fr.md).

## Système

- **Python 3.10 ou plus récent**, avec `venv` et `pip`.
  - Windows : [python.org](https://www.python.org/downloads/), case **Add python.exe to PATH**. Pas le Microsoft Store.
  - macOS : [python.org](https://www.python.org/downloads/) ou `brew install python`.
  - Debian ou Ubuntu : `sudo apt-get install python3 python3-venv python3-pip`.
  - Fedora : `sudo dnf install python3`.
- **Internet** la première fois, pour télécharger les paquets.
- **ffmpeg** est utile pour les dates des vidéos. Les miniatures et la lecture des vidéos iPhone (HEVC) utilisent le binaire fourni par le paquet `imageio-ffmpeg`.
- SQLite est inclus dans Python. Il n’est pas dans la liste ci-dessous.

## Paquets Python

La même liste est dans les trois autres langues. Les scripts de démarrage la lisent ici.

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

Installation à la main, dans le dossier du site :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
```

Windows : `python -m venv .venv`, puis `.venv\Scripts\python.exe scripts\lire_paquets.py --write .paquets.txt`, puis `.venv\Scripts\pip install -r .paquets.txt`. Les scripts `preparer-python.bat`, `start-windows.bat`, `start-mac.command` et `start-linux.sh` font cette installation.

| Paquet | Rôle |
|--------|------|
| `cryptography` | Mots de passe enregistrés (iCloud, courriel) |
| `fastapi`, `uvicorn`, `python-multipart` | Site web |
| `pillow`, `pillow-heif` | Photos, y compris HEIC |
| `numpy`, `opencv-python-headless`, `onnxruntime`, `insightface`, `scipy` | Visages |
| `imageio-ffmpeg` | Conversion vidéo pour le navigateur et la télévision |
| `icloudpd` | Téléchargement iCloud, si vous l’utilisez |
| `reverse-geocoder` | Ville à partir du GPS |

`insightface` est le moteur de visages le plus précis. S’il ne s’installe pas, le site démarre quand même : la détection retombe sur OpenCV. Relancer l’installation plus tard ajoute ce moteur.
