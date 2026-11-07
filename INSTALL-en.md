# Galerie Médias — installation

Version **3.0**. The site stays on your computer. Photos may stay on a USB disk. The database (SQLite, thumbnails, settings) stays on the computer, never on the USB disk. The site listens only on **HTTPS**. There is no `http://` address.

The same guide: [Français](INSTALL-fr.md), [Español](INSTALL-es.md), [Deutsch](INSTALL-de.md). Requirements: [REQUIS-en.md](REQUIS-en.md). In the site: `static/install/`. The menus are explained in the **?** help.

## Where the files are

- Photos: the folder set in **Settings**. Example: `E:\Photos`.
- Windows: `C:\Users\YOURNAME\AppData\Roaming\GaleriePhotos\` (`ouvrir-dossier-base.bat`).
- macOS: `Library/Application Support/GaleriePhotos/`.
- Linux: `~/.config/galerie-photos/`.

Unpack the program into Documents, not from inside the still-open zip.

## Windows

1. [Python 3.10+](https://www.python.org/downloads/) from python.org, not the Microsoft Store. Check **Add python.exe to PATH**.
2. Unpack, for example into `Documents\galerie-medias\`.
3. `preparer-python.bat` (creates `.venv`, without opening the site).
4. `ouvrir-galerie.bat` or `start-windows.bat`. The first time takes a few minutes and needs Internet. Firewall: **Yes**. Wi-Fi must be **Private**.
5. The browser opens [https://127.0.0.1:8765](https://127.0.0.1:8765). On the first visit, continue to the site (home certificate).

Leave the black window open. It follows the Windows language (French, English, Spanish, German).

Useful: `creer-raccourci-bureau.bat`, `lister-disques.bat`, `autoriser-parefeu.bat` (ports **8765** and **8766**), `reparer-installation.bat`, `gerer-utilisateurs.bat`.

## macOS

1. Python 3.10+: [python.org](https://www.python.org/downloads/) or `brew install python`.
2. Double-click `start-mac.command`. If macOS blocks it: right-click → **Open**.
3. A password may be requested for the firewall (permanent rule). Refusing it still lets you use the site on this computer. Try again: `autoriser-parefeu-mac.command`.
4. Address: `https://127.0.0.1:8765`. Continue to the site on the first visit.

New version: `reparer-installation-mac.command`. The window follows the Mac language. Sorting: `classer-annee-mois-mac.command`, then `classer-lieux-mac.command`.

## Linux

1. Python 3.10+. Debian or Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`. Fedora: `sudo dnf install python3`.
2. Unpack, for example into `~/Documents/galerie-medias/`.
3. `bash start-linux.sh`.
4. The script prepares `.venv`, tries to open ports 8765 and 8766 (firewalld or ufw), then starts the site. Refusing the administrator password still lets you use the site on this computer.
5. Address: `https://127.0.0.1:8765`. Continue to the site on the first visit.

Leave the terminal open. Messages follow `LANG` (fr, en, es, de; otherwise French).

## HTTPS and a certificate through DNS

On the first start, a **home certificate** is created. The browser warns once.

For a public name, for example `https://photos.example.com:8765`, the certificate comes from **Let’s Encrypt**, proved through **DNS**. No port is opened on the router. The certificate follows the name: when you move, change the DNS address, not the certificate. The same steps are in the help, section HTTPS.

1. Register the name at a registrar that also hosts DNS. Cloudflare is suitable. Do not pay for an extra certificate.
2. **A** record, name **@**, address of the computer on the home network. Cloudflare cloud **grey**. Do not forward port 8765 to the Internet.
3. The command that requests the certificate depends on the system. Let’s Encrypt: https://letsencrypt.org/ . Certbot: https://certbot.eff.org/ . WireGuard, the VPN used to reach the house away from Wi-Fi: https://www.wireguard.com/install/ .

Linux: `sudo apt-get install certbot python3-certbot-dns-cloudflare`, token in `/etc/letsencrypt/cloudflare.ini` (mode 600), then `sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --dns-cloudflare-propagation-seconds 30 -d photos.example.com`. Copy `fullchain.pem` and `privkey.pem` into `~/.config/galerie-photos/cache/letsencrypt/` (or `~/.cache/photo-library/letsencrypt/` if the cache is there).

macOS: Homebrew (https://brew.sh/), `brew install certbot`, then the Cloudflare module inside Certbot’s environment. Copy `fullchain.pem` and `privkey.pem` into `~/Library/Application Support/GaleriePhotos/cache/letsencrypt/`.

Windows: the Linux command does not run as-is. Copy the two files you already have, or install Python (https://www.python.org/downloads/) and then `py -m pip install certbot certbot-dns-cloudflare`. Put the two files in `C:\Users\YOURNAME\AppData\Roaming\GaleriePhotos\cache\letsencrypt\`.

The detail is in the site help, section HTTPS. Without those two files, the home certificate stays in use.

The television (LG, Samsung) uses port **8766** without a certificate. That is not the address of the site.

## First use

1. Plug in the disk.
2. **Settings**: photo folder, then **Save**.
3. Sort before indexing. Loose photos, or photos already by year: `classer-lieux`. A mixed tree (DCIM): `classer-annee-mois`, then `classer-lieux`. Choice 1 previews, choice 2 writes. Linux: `.venv/bin/python tools/sort_annee_mois.py SOURCE DEST`, then `.venv/bin/python tools/sort_lieux.py -d DEST`, with `--apply` to write.
4. **Index**.

Folders on disk are named `Annee 2024` and `Juin 2024`.

## Update

Close the site. Unpack the new zip over the same folder. Do not delete GaleriePhotos or `~/.config/galerie-photos`. Do not copy the photos again. Then `reparer-installation.bat`, `reparer-installation-mac.command`, or `bash start-linux.sh`. See [MISE-A-JOUR-en.md](MISE-A-JOUR-en.md).

## If the page does not open

- Python: python.org, PATH checked, start again.
- Close the old window and open `https://127.0.0.1:8765`.
- `http://` does not answer: the site is HTTPS only.
- Photos: disk plugged in, right drive letter (`lister-disques.bat`).
