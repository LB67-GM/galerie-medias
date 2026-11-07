# Galerie Médias 3.0 — update a site that is already installed

Use this file when the site is already running. First install: [INSTALL-en.md](INSTALL-en.md).

Other languages: [Français](MISE-A-JOUR-fr.md), [Español](MISE-A-JOUR-es.md), [Deutsch](MISE-A-JOUR-de.md).

After the update, **Settings** shows **Galerie Médias 3.0** (also at the top left).

## What is new in 3.0

- Menus: **Photos, People, Scenes, Duplicates, Map, Albums, Trash, Settings**.
- Language (French, English, Spanish, German) and colour theme, top right. The choice stays in this browser.
- **Forgot password**: in Settings → Email, enter the server and the site address, then each account’s email. The link lasts one hour.
- The **Amber** theme is unchanged. The others: Ink, Ocean, Forest, Paper, Daylight.
- The **?** menu opens the help, in the site language.
- The site listens only on **HTTPS**.

**Photos** and the **database** (faces, albums, accounts) stay where they are. Only the program is replaced.

## Windows

1. Close the black window. The site must be stopped.
2. Unpack the new zip **over the same folder** (often `Documents\galerie-medias\`). Replace the files.
3. Do not touch `C:\Users\YOURNAME\AppData\Roaming\GaleriePhotos\`.
4. Do not copy the photos again.
5. Double-click `reparer-installation.bat` and wait until the window finishes.
6. Double-click `ouvrir-galerie.bat`.
7. In the browser: **Ctrl+F5**.
8. Settings: **Galerie Médias 3.0**.

There is no need to index everything again. The television also uses port **8766**: run `autoriser-parefeu.bat` once if the TV cannot see the site.

## macOS

1. Quit the Terminal window (`start-mac.command`).
2. Unpack the new zip **over the same folder**.
3. Do not touch `Library/Application Support/GaleriePhotos`.
4. Double-click `reparer-installation-mac.command`, or start `start-mac.command` again.
5. Reload the page (Cmd+Shift+R).
6. Settings: **Galerie Médias 3.0**.

## Linux

1. Stop the site (close the terminal, or stop the service if there is one).
2. Replace the program files in the same folder. Do not delete `~/.config/galerie-photos/` or `~/.cache/photo-library/`.
3. Run `bash start-linux.sh` again. If `REQUIS-en.md` changed, the script updates the packages.
4. Reload the page (Ctrl+F5).
5. Settings: **Galerie Médias 3.0**.

## Do not

| Do not… | Why |
|---------|-----|
| Install into a **new** folder and index everything again | Faces, albums and accounts live in GaleriePhotos, not in the zip |
| Delete `AppData\Roaming\GaleriePhotos`, Application Support, or `~/.config/galerie-photos` | Same reason |
| Copy the photos again “to be safe” | Unnecessary |
| Run the zip without unpacking it | Python will not be found |
| Open two windows at once | The port is already in use |

## If it no longer starts

1. Close every site window.
2. Run `reparer-installation.bat`, `reparer-installation-mac.command`, or `bash start-linux.sh`.
3. Start `ouvrir-galerie.bat`, `start-mac.command`, or `start-linux.sh` again.
4. `reparer-installation.log`, next to the scripts, has the detail.

Disk not found: `lister-disques.bat`, then fix the path in Settings.
