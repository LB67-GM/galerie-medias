# Galerie Médias 4.2 — update a site that is already installed

Use this file when the site is already running. First install: [INSTALL-en.md](INSTALL-en.md).

Other languages: [Français](MISE-A-JOUR-fr.md), [Español](MISE-A-JOUR-es.md), [Deutsch](MISE-A-JOUR-de.md).

After the update, **Settings** shows **Galerie Médias 4.2** (also at the top left).

## What is new in 4.2

- **TV** from a film: the window says “Touch a TV to send the film there.” It no longer asks you to open a photo.
- The film is converted to H.264 720p with AAC audio, the format an LG or Samsung television plays. The first time, allow 4 to 5 minutes. The same film then starts right away.
- Nothing to re-index. Photos, accounts and settings stay where they are.

## What is new in 4.1

- **TV** button for a film (Cinema): the message says the first conversion can take **4 to 5 minutes**. The prepared file is kept, so the same film then starts right away.
- The film is converted to H.264 720p with AAC audio, the format an LG or Samsung television plays. Sending the file unchanged (4K or a profile that is too high) showed “format not supported”. A short video from the Photos gallery still uses the about-one-minute message.
- Playing a film in the browser (HLS) still starts within seconds.
- Nothing to re-index. Photos, accounts and settings stay where they are.

## What is new in 4.0

- New **Cinema** tab (available to both administrator and **viewer** accounts): built-in open-source video player with live **HLS streaming** (`hls.js`), audio tracks, subtitles, chapters, quality presets, and **Continue watching**.
- Supported formats in Cinema: video files (`.mp4`, `.m4v`, `.mkv`, `.avi`, `.mpg`, `.mov`…), **DVD** folders/images (`VIDEO_TS`, `.iso`), **Blu-ray** folders/images (`BDMV`, `.iso`), and optional native **optical drive** (leave empty on a server without a drive).
- Filters by **Type** (Movie, Series, Music clip, Documentary), **Category**, and **Year**, with on-demand **Wikidata / Wikipedia** enrichment (CC0 open data, no API key) and lockable manual editing.
- **TV (DLNA)** casting inside the Cinema player (port `8766` on the local network).
- Automatic SQLite and settings migration: in **Settings → Cinema**, enter your video folder (e.g. `/mnt/cinema`), save, then click **Index Cinema**.
- Two separate indexing actions: **Index Photos** (top toolbar, for the Photos library) and **Index Cinema** (Cinema tab or Settings → Cinema, for movies/series/clips). Movies and clips can be moved to **Trash** (30 days, restorable or permanently deletable).
- Menus: **Photos, Cinema, People, Scenes, Duplicates, Map, Albums, Trash, Settings**.
- Language (French, English, Spanish, German) and colour theme, top right. The choice stays in this browser.
- **Forgot password**: in Settings → Email, enter the server and the site address, then each account’s email. The link lasts one hour.
- The **Amber** theme is unchanged. The others: Ink, Ocean, Forest, Paper, Daylight.
- The **?** menu opens the help, in the site language.
- The site listens only on **HTTPS**.

**Photos** and the **database** (faces, albums, accounts) stay where they are. Only the program is replaced.

## Upgrading from 3.0 to 4.0: automatic migration and enabling Cinema

- **Automatic on first start in 4.0**: your photos, faces, scenes, albums, accounts, settings (`config.json`), and HTTPS certificates stay untouched. SQLite automatically creates the new **Cinema** tables (catalog, categories, resume progress, and 30-day trash). No new Python package is required and you **do not need to re-index your photos**.
- **If you do not use Cinema yet**: nothing to change; the Photos gallery keeps working just like in 3.0.
- **To enable the Cinema tab after updating**:
  1. Open **Settings → Cinema**.
  2. Enter the **Cinema folder** containing your movies, series, clips, or DVD/Blu-ray folders (e.g. `/mnt/cinema` or `D:\Videos\Cinema`).
  3. *(Optional)* Enter your native **Physical optical drive** (e.g. `/dev/sr0`, `/Volumes/...`, or `D:\`). Leave blank on a computer or server without an optical drive.
  4. Click **Save**, then **Index Cinema** (separate from **Index Photos** in the top Tools bar).
  5. *(Optional)* Click **Enrich (Wikidata)** to automatically populate categories, release years, directors, and summaries (CC0 open data, no API key required).

## Windows

1. Close the black window. The site must be stopped.
2. Unpack the new zip **over the same folder** (often `Documents\galerie-medias\`). Replace the files.
3. Do not touch `C:\Users\YOURNAME\AppData\Roaming\GaleriePhotos\`.
4. Do not copy the photos again.
5. Double-click `reparer-installation.bat` and wait until the window finishes.
6. Double-click `ouvrir-galerie.bat`.
7. In the browser: **Ctrl+F5**.
8. Settings: **Galerie Médias 4.2**.

There is no need to index everything again. The television also uses port **8766**: run `autoriser-parefeu.bat` once if the TV cannot see the site.

## macOS

1. Quit the Terminal window (`start-mac.command`).
2. Unpack the new zip **over the same folder**.
3. Do not touch `Library/Application Support/GaleriePhotos`.
4. Double-click `reparer-installation-mac.command`, or start `start-mac.command` again.
5. Reload the page (Cmd+Shift+R).
6. Settings: **Galerie Médias 4.2**.

## Linux

1. Stop the site (close the terminal, or run `systemctl --user stop photo-library.service` if using a systemd service).
2. Replace the program files in the same folder. Do not delete `~/.config/galerie-photos/` or `~/.cache/photo-library/`.
3. Run `bash start-linux.sh` again (or `systemctl --user start photo-library.service`). If `REQUIS-en.md` changed, `start-linux.sh` updates the packages.
4. Reload the page (**Ctrl+F5**).
5. Settings: **Galerie Médias 4.2**. *(Optional: mount your video folder, e.g. `/mnt/cinema`, then configure it in **Settings → Cinema**.)*

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
