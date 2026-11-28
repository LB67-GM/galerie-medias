# Galerie Médias — Installation

Version **4.1**. Die Seite bleibt auf Ihrem Computer. Die Fotos dürfen auf einem USB-Datenträger bleiben. Die Datenbank (SQLite, Miniaturen, Einstellungen) bleibt auf dem Computer, nie auf dem USB-Datenträger. Die Seite hört nur auf **HTTPS**. Es gibt keine Adresse `http://`.

Dieselbe Anleitung: [Français](INSTALL-fr.md), [English](INSTALL-en.md), [Español](INSTALL-es.md). Voraussetzungen: [REQUIS-de.md](REQUIS-de.md). In der Seite: `static/install/`. Die Menüs stehen in der Hilfe **?**.

## Wo die Dateien liegen

- Fotos: der Ordner aus **Einstellungen**. Beispiel: `E:\Photos`.
- Windows: `C:\Users\IHRNAME\AppData\Roaming\GaleriePhotos\` (`ouvrir-dossier-base.bat`).
- macOS: `Library/Application Support/GaleriePhotos/`.
- Linux: `~/.config/galerie-photos/`.

Entpacken Sie das Programm in Dokumente, nicht aus dem noch geöffneten Zip.

## Windows

1. [Python 3.10+](https://www.python.org/downloads/) von python.org, nicht aus dem Microsoft Store. Häkchen bei **Add python.exe to PATH**.
2. Entpacken, zum Beispiel nach `Documents\galerie-medias\`.
3. `preparer-python.bat` (legt `.venv` an, ohne die Seite zu öffnen).
4. `ouvrir-galerie.bat` oder `start-windows.bat`. Beim ersten Mal einige Minuten, Internet nötig. Firewall: **Ja**. Das WLAN muss **privat** sein.
5. Der Browser öffnet [https://127.0.0.1:8765](https://127.0.0.1:8765). Beim ersten Besuch weiter zur Seite gehen (Haus-Zertifikat).

Lassen Sie das schwarze Fenster offen. Es folgt der Windows-Sprache (Französisch, Englisch, Spanisch, Deutsch).

Nützlich: `creer-raccourci-bureau.bat`, `lister-disques.bat`, `autoriser-parefeu.bat` (Ports **8765** und **8766**), `reparer-installation.bat`, `gerer-utilisateurs.bat`.

## macOS

1. Python 3.10+: [python.org](https://www.python.org/downloads/) oder `brew install python`.
2. Doppelklick auf `start-mac.command`. Wenn macOS blockiert: Rechtsklick → **Öffnen**.
3. Für die Firewall kann ein Passwort verlangt werden (dauerhafte Regel). Eine Ablehnung lässt die Seite auf diesem Computer nutzbar. Erneut: `autoriser-parefeu-mac.command`.
4. Adresse: `https://127.0.0.1:8765`. Beim ersten Besuch weiter zur Seite gehen.

Neue Version: `reparer-installation-mac.command`. Das Fenster folgt der Sprache des Mac. Sortieren: `classer-annee-mois-mac.command`, danach `classer-lieux-mac.command`.

## Linux

1. Python 3.10+. Debian oder Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`. Fedora: `sudo dnf install python3`.
2. Entpacken, zum Beispiel nach `~/Documents/galerie-medias/`.
3. `bash start-linux.sh`.
4. Das Skript bereitet `.venv` vor, versucht die Ports 8765 und 8766 zu öffnen (firewalld oder ufw) und startet dann die Seite. Ein abgelehntes Administratorpasswort lässt die Seite auf diesem Computer nutzbar.
5. Adresse: `https://127.0.0.1:8765`. Beim ersten Besuch weiter zur Seite gehen.

Lassen Sie das Terminal offen. Die Meldungen folgen `LANG` (fr, en, es, de; sonst Französisch).

## HTTPS und ein Zertifikat über DNS

Beim ersten Start entsteht ein **Haus-Zertifikat**. Der Browser warnt einmal.

Für einen öffentlichen Namen, zum Beispiel `https://photos.example.com:8765`, kommt das Zertifikat von **Let’s Encrypt**, nachgewiesen über **DNS**. An der Box wird kein Port geöffnet. Das Zertifikat folgt dem Namen: beim Umzug ändern Sie die DNS-Adresse, nicht das Zertifikat. Dieselben Schritte stehen in der Hilfe, Abschnitt HTTPS.

1. Reservieren Sie den Namen bei einer Stelle, die auch das DNS betreibt. Cloudflare eignet sich. Zahlen Sie kein zusätzliches Zertifikat.
2. **A**-Eintrag, Name **@**, Adresse des Computers im Hausnetz. Cloudflare-Wolke **grau**. Leiten Sie Port 8765 nicht ins Internet weiter.
3. Der Befehl, der das Zertifikat anfordert, hängt vom System ab. Let’s Encrypt: https://letsencrypt.org/ . Certbot: https://certbot.eff.org/ . WireGuard, das VPN, um das Haus außerhalb des WLAN zu erreichen: https://www.wireguard.com/install/ .

Linux: `sudo apt-get install certbot python3-certbot-dns-cloudflare`, Token in `/etc/letsencrypt/cloudflare.ini` (Rechte 600), dann `sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --dns-cloudflare-propagation-seconds 30 -d photos.example.com`. Kopieren Sie `fullchain.pem` und `privkey.pem` nach `~/.config/galerie-photos/cache/letsencrypt/` (oder `~/.cache/photo-library/letsencrypt/`, wenn der Cache dort liegt).

macOS: Homebrew (https://brew.sh/), `brew install certbot`, dann das Cloudflare-Modul in Certbots Umgebung. Kopieren Sie `fullchain.pem` und `privkey.pem` nach `~/Library/Application Support/GaleriePhotos/cache/letsencrypt/`.

Windows: der Linux-Befehl läuft nicht unverändert. Kopieren Sie die beiden schon vorhandenen Dateien, oder installieren Sie Python (https://www.python.org/downloads/) und danach `py -m pip install certbot certbot-dns-cloudflare`. Legen Sie die beiden Dateien nach `C:\Users\IHRNAME\AppData\Roaming\GaleriePhotos\cache\letsencrypt\`.

Die Einzelheiten stehen in der Hilfe der Seite, Abschnitt HTTPS. Ohne diese beiden Dateien bleibt das Haus-Zertifikat in Betrieb.

Der Fernseher (LG, Samsung) nutzt Port **8766** ohne Zertifikat. Das ist nicht die Adresse der Seite.

## Erste Verwendung

1. Datenträger anschließen.
2. **Einstellungen**: Fotoordner, dann **Speichern**.
3. Vor dem Indexieren sortieren. Lose oder schon nach Jahr: `classer-lieux`. Gemischter Baum (DCIM): `classer-annee-mois`, dann `classer-lieux`. Wahl 1 simuliert, Wahl 2 schreibt. Linux: `.venv/bin/python tools/sort_annee_mois.py QUELLE ZIEL`, dann `.venv/bin/python tools/sort_lieux.py -d ZIEL`, mit `--apply` zum Schreiben.
4. **Indexieren**.

Die Ordner auf der Festplatte heißen `Annee 2024` und `Juin 2024`.

## Aktualisierung

Seite schließen. Das neue Zip über denselben Ordner entpacken. GaleriePhotos und `~/.config/galerie-photos` nicht löschen. Die Fotos nicht erneut kopieren. Danach `reparer-installation.bat`, `reparer-installation-mac.command` oder `bash start-linux.sh`. Siehe [MISE-A-JOUR-de.md](MISE-A-JOUR-de.md).

## Wenn die Seite nicht aufgeht

- Python: python.org, PATH gesetzt, erneut starten.
- Altes Fenster schließen und `https://127.0.0.1:8765` öffnen.
- `http://` antwortet nicht: die Seite ist nur HTTPS.
- Fotos: Datenträger angeschlossen, richtiger Buchstabe (`lister-disques.bat`).
