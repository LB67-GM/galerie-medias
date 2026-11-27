# Galerie Médias

French version: [lisezmoi.md](lisezmoi.md).

Local web site **Galerie Médias** (version **4.0**): view, filter and export photos and videos from the folder set in **Settings** (the library stays where it is), and watch movies, series, clips, DVD and Blu-ray in the **Cinema** tab (live HLS streaming + Wikidata CC0 metadata). Languages: French, English, Spanish and German. Six colour themes. The **?** menu opens the help in the chosen language (`static/help/`). Update of a site that is already installed: [MISE-A-JOUR-en.md](./MISE-A-JOUR-en.md) (also [fr](./MISE-A-JOUR-fr.md), [es](./MISE-A-JOUR-es.md), [de](./MISE-A-JOUR-de.md)). Requirements: [REQUIS-en.md](./REQUIS-en.md).

Filters: year, **month**, place, **moment** (trip, birthday, wedding, party…), type (photo / video), album (including **Favourites**), landscape / building, search (file, place, moment or first name, **whole word**: Rome does not match Andromeda; the cross in the field brings the whole gallery back). There is no separate People menu: a first name is typed in search. Filters **combine** (AND). Year = folder **or** EXIF date. Month = EXIF month **or** a folder such as `January 2006`. Under a year: **Place** = geography (`Lisbon`, `Rome`); **Moment** = everything else (`Holiday Italy`, `Birthday 2024`). With no filter: newest first (folder year, because EXIF is sometimes wrong). **This page** → **All selected**. Counters: library (header), filter, page, checked. Shift+click for a range. Menus stay put while scrolling. **Add to album** only when photos are checked; **Remove from album** too (inside an album, that album); the star is the albums (add or remove). **Place** corrects the displayed place and the map pin, not the folder on disk; mini-map: pin in the centre, drag the map; the folder option is the immediate folder only. **Move** (checked photos): to a folder that already exists in the same year; the file leaves its folder, the video of the same name goes with it, Moment and Place follow. Changing a filter clears the selection. **Deselect**. **Delete**: 500 photos maximum; after confirmation, back to the gallery with no filter. Church / mountain / city labels are set in the **Scenes** tab, not in the gallery bar.

Click a thumbnail: large view (ratio kept). Pinch to zoom (the wheel too). **Rotate / crop**: the original goes to **Trash** (Restore undoes it). iPhone videos (HEVC) are converted for the browser (`/api/media/{id}/play`). Faces: the **X** key means Not this person. **TV (DLNA)** button: next to Slideshow; send to an LG/Samsung television on the LAN (HTTPS 8765, the TV reads HTTP `8766`). Videos are converted to H.264 before sending.

**Map** tab: pins for **place folders** (OpenStreetMap, Internet). Position: GPS of the photos when already indexed (`scan-gps`), otherwise geocoding of the name (`Portugal`, `Rome`…). Click a pin → gallery on that place (other filters cleared). A place set in **Place** stays in the menu. **Place** on checked photos opens a mini-map: the pin stays in the centre, drag the map, the name updates, **Save** moves the world pin. Homonyms: Manhattan is New York, San Jose California is not Spain.

## Requirements

- Python 3.10+
- `ffmpeg` / `ffprobe`: video dates (`ffprobe`). Thumbnails **and** iPhone HEVC playback: `ffmpeg` supplied by `imageio-ffmpeg` (the Fedora “free” `ffmpeg` often has no HEVC). The browser receives H.264 through `/api/media/{id}/play`.

## Install (once)

```bash
cd /path/to/photo-library
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
chmod +x run.py
```

The package list is in [REQUIS-en.md](./REQUIS-en.md) (also fr, es, de). SQLite is inside Python. The scripts `start-linux.sh`, `start-mac.command` and `start-windows.bat` do this install.

## Commands

```bash
cd /path/to/photo-library

.venv/bin/python run.py serve [options]
.venv/bin/python run.py index [--year YYYY | --all] [options]
.venv/bin/python run.py faces [--year YYYY] [options]
.venv/bin/python run.py backup [--dest FOLDER]
.venv/bin/python run.py restore BACKUP-FOLDER [--no-config]
.venv/bin/python run.py completer-lieux [--apply]
.venv/bin/python run.py scan-gps [--year YYYY]
.venv/bin/python run.py users [--list | --create IDENTIFIER --role lecture|admin | --delete IDENTIFIER]
.venv/bin/python scripts/restore_backup.py BACKUP-FOLDER
```

With no subcommand, `serve` starts.

### Accounts

With no account, the site stays open. As soon as there is one, the login page appears.

```bash
.venv/bin/python run.py users --list
.venv/bin/python run.py users --create leo --role lecture
.venv/bin/python run.py users --set-password leo
.venv/bin/python run.py users --unlock leo
.venv/bin/python run.py users --delete leo
```

`--role`: `admin` or `lecture`. Password: **8 characters** minimum (asked, or `--password`). `--email` stores the email. Three tries, then the account is locked. **Forgot password** sends a link when the account email and the server (Settings → Email) are filled in. Otherwise an admin runs `--set-password IDENTIFIER` (new password and unlock) or `--unlock` (same password). `--set-email IDENTIFIER --email …` changes the email. Windows: `gerer-utilisateurs.bat`. Mac: `gerer-utilisateurs-mac.command`.

### Server

HTTPS only. Let’s Encrypt certificate when it is in `cache/letsencrypt/`, otherwise the home certificate (`tls/` in the cache). First visit with the home certificate: continue to the site (it is your computer). There is no HTTP mode.

| Option | Effect |
|--------|--------|
| `--host` | Address (default: `127.0.0.1`) |
| `--port` | Port (default: `8765`) |
| `--tls-host NAME` | Extra name or IP in the home certificate (repeatable) |
| `-d`, `--library PATH` | Library (otherwise the Settings folder) |
| `--cache PATH` | SQLite cache and thumbnails (default: `~/.cache/photo-library`) |

Open [https://127.0.0.1:8765](https://127.0.0.1:8765) on this machine, or `https://<LAN-IP>:8765` from a phone (same certificate warning, once).

### Starting on the local network

The site listens on HTTPS. The local firewall can open ports 8765 (site) and 8766 (television).

Automatic backup: `scripts/systemd/photo-library-backup.timer` (every Wednesday 23:00). Copies SQLite, settings and `site/` to `backup-YYYY-MM-DD` (4 newest kept). Thumbnails are not copied. `scripts/weekly_index.py` reindexes the library; schedule it if you want that.

Do not start a second `run.py serve` at the same time (the port would already be taken).

### Index

Reads the photo folder, updates SQLite, builds thumbnails **locally**.

```bash
.venv/bin/python run.py index --year 2024
.venv/bin/python run.py index --year 2024 --limit 50
.venv/bin/python run.py index --all
```

Without `--year` or `--all`, everything is indexed (slow when the library is large). The index can also be started from the interface.

### Empty places (`completer-lieux`)

Walks the library (**SQLite only**, folders do not move). Sorts Place versus Moment: cities go to Place, the rest (birthdays, weddings, holidays…) goes to Moment. A place locked in the gallery **Place** action is left as it is. Dry-run by default.

```bash
.venv/bin/python run.py completer-lieux
.venv/bin/python run.py completer-lieux --apply
.venv/bin/python scripts/completer_lieux.py --apply
```

`--no-index` skips the search for files missing from SQLite. `--keep-generic` leaves `Vacances` as it is.

### GPS for the map (`scan-gps`)

Reads GPS from the files **once** (EXIF / ISO6709, and the `sort_lieux` index when it exists) and stores it in SQLite. The map uses that GPS (average of the place), otherwise geocoding of the folder name. **Place** still wins.

```bash
.venv/bin/python run.py scan-gps
.venv/bin/python run.py scan-gps --year 2016
```

Later indexes reread GPS only for new or changed files.

### Faces

Local detection (InsightFace when it is installed, otherwise OpenCV YuNet + SFace). No cloud.

Routine:

1. **Index** the photos (button at the top, or `run.py index`).
2. **Detect faces** — first pass, often long. The InsightFace model `buffalo_l` (about 280 MB) downloads once into `~/.insightface/`. That model is not under MIT: InsightFace reserves it for non-commercial research. Without it, detection uses OpenCV (YuNet and SFace).
3. **Faces** tab: automatic groups are often mixed. Check the faces you recognise, **Name the selection**. **Review** brings that person’s first picture to the top of the screen, then **Not …** to remove mistakes. The gallery can then be filtered by that name.
4. **New photos**: **Index** first, then **Detect faces** again. Only files not yet analysed are processed. Those that look like a person already named are attached; the rest appears as new groups.

Without a new index, clicking “Detect faces” again does nothing. Naming a group does not rerun the whole detection.

```bash
.venv/bin/python run.py faces --year 2024
.venv/bin/python run.py faces --year 2024 --limit 20
```

### Landscapes / buildings

**Scenes** tab (like Faces). The gallery only keeps a **filter** (range, city, church…).

1. Choose a **year** (and a place) so everything is not mixed.
2. **Detect landscapes / buildings** — a heuristic, often imperfect.
3. Check the right photos, **Label the selection** (church, mountain, city…).
4. **Review** badge, then **Not …** to remove a mistake. In the large view: **Add** a label or **Not …**.

```bash
.venv/bin/python run.py scenes --year 2025 --place Paris
```

### Backup and restore

Settings → **Backup**: a parent folder (external disk or another folder) and the **Back up now** button. Each run creates `backup-YYYY-MM-DD/` with `library.sqlite`, `config.json`, `secret.key`, `site/` (HTML, CSS, JS, Python), `manifest.json`. Rotation: 4 folders.

Restore (stops the systemd service if needed, then starts it again):

```bash
.venv/bin/python scripts/restore_backup.py /path/backup-2026-09-01
# or without overwriting settings:
.venv/bin/python scripts/restore_backup.py /path/backup-2026-09-01 --no-config
```

Sample systemd units: `scripts/systemd/photo-library-backup.{service,timer}`.

## Archive for another computer

`python scripts/pack_distrib.py` produces `dist/galerie-medias-4.0-YYYY-MM-DD.zip` (and `.tar.gz`). Install: [INSTALL-en.md](./INSTALL-en.md). Update: [MISE-A-JOUR-en.md](./MISE-A-JOUR-en.md). The same files exist in French, Spanish and German.

First time: sort before indexing. A mixed tree: `classer-annee-mois.bat "E:\Loose" "E:\Photos"` (simulation), then `--apply` (copy into `Annee/Mois`), then `classer-lieux.bat "E:\Photos"`. macOS: `classer-annee-mois-mac.command` then `classer-lieux-mac.command`. Linux: `tools/sort_annee_mois.py SOURCE DEST` then `tools/sort_lieux.py -d DEST --all`. Messenger export (dates in `message_*.json`): `tools/sort_lieux.py --facebook --facebook-dir FOLDER` (simulation, then `--apply`).

SQLite and thumbnails stay on the computer. Photos may stay on a USB disk.

## iCloud

Before using the iCloud download in **Settings**, sign in at [icloud.com](https://www.icloud.com) with the same Apple ID, in a browser. Apple sometimes shows its terms and conditions before opening the photos. Until those terms are accepted, the download cannot fetch the photos.

## Licence

Galerie Médias is under the **MIT** licence ([LICENSE](./LICENSE)). Third-party components are listed in [NOTICE](./NOTICE): Leaflet, flag-icons flags, GeoNames cities, tiles © OpenStreetMap contributors, FFmpeg (a separate program, GPL). The InsightFace `buffalo_l` face model is not under MIT.

## Important

1. The library (the Settings folder) stays **read-only**, except trash from the gallery and **Rotate / crop**.
2. Cache and database: `~/.cache/photo-library/` on the machine that runs the site (portable mode: `GaleriePhotos`).
3. Export copies the originals; it does not remove them from the photo folder.
4. Face recognition is not perfect (profiles, children, ageing).
