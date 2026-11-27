# Galerie Médias 4.0 — eine bereits installierte Seite aktualisieren

Diese Datei gilt, wenn die Seite schon läuft. Erste Installation: [INSTALL-de.md](INSTALL-de.md).

Andere Sprachen: [Français](MISE-A-JOUR-fr.md), [English](MISE-A-JOUR-en.md), [Español](MISE-A-JOUR-es.md).

Nach der Aktualisierung zeigt **Einstellungen** **Galerie Médias 4.0** (auch oben links).

## Neu in 4.0

- Neuer Reiter **Kino** (für Administrator- und **Lesekonten**): integrierter Open-Source-Videoplayer mit Live-**HLS-Streaming** (`hls.js`), Tonspuren, Untertiteln, Kapiteln, Qualitätsstufen und **Weiterschauen**.
- Unterstützte Formate im Kino: Videodateien (`.mp4`, `.m4v`, `.mkv`, `.avi`, `.mpg`, `.mov`…), **DVD**-Ordner/-Images (`VIDEO_TS`, `.iso`), **Blu-ray**-Ordner/-Images (`BDMV`, `.iso`) sowie optional ein natives **optisches Laufwerk** (auf Servern ohne Laufwerk leer lassen).
- Filter nach **Typ** (Film, Serie, Musikclip, Dokumentation), **Kategorie** und **Jahr**, mit optionaler Anreicherung über **Wikidata / Wikipedia** (CC0 Open Data, ohne API-Schlüssel) und sperrbarer manueller Bearbeitung.
- **TV (DLNA)** direkt aus dem Kino-Player (Port `8766` im Heimnetz).
- Automatische SQLite- und Einstellungsmigration: unter **Einstellungen → Kino** Ihren Video-Ordner angeben (z. B. `/mnt/cinema`), speichern und **Kino indizieren** klicken.
- Zwei getrennte Indizierungen: **Fotos indizieren** (Werkzeugleiste oben, für die Fotos-Bibliothek) und **Kino indizieren** (Reiter Kino oder Einstellungen → Kino, für Filme/Serien/Clips). Filme und Clips können in den **Papierkorb** verschoben werden (30 Tage, wiederherstellbar oder endgültig löschbar).
- Menüs: **Fotos, Kino, Personen, Szenen, Duplikate, Karte, Alben, Papierkorb, Einstellungen**.
- Sprache (Französisch, Englisch, Spanisch, Deutsch) und Farbthema, oben rechts. Die Wahl bleibt in diesem Browser.
- **Passwort vergessen**: unter Einstellungen → E-Mail den Server und die Adresse der Seite eintragen, dann die E-Mail jedes Kontos. Der Link gilt eine Stunde.
- Das Thema **Bernstein** bleibt. Die anderen: Tinte, Ozean, Wald, Papier, Tag.
- Das Menü **?** öffnet die Hilfe, in der Sprache der Seite.
- Die Seite hört nur auf **HTTPS**.

Die **Fotos** und die **Datenbank** (Gesichter, Alben, Konten) bleiben. Nur das Programm wird ersetzt.

## Upgrade von 3.0 auf 4.0: automatische Migration und Kino aktivieren

- **Automatisch beim ersten Start in 4.0**: Ihre Fotos, Gesichter, Szenen, Alben, Konten, Einstellungen (`config.json`) und HTTPS-Zertifikate bleiben unverändert. SQLite legt die neuen **Kino**-Tabellen automatisch an (Katalog, Kategorien, Weiterschauen und 30-Tage-Papierkorb). Es sind keine neuen Python-Pakete erforderlich und **Sie müssen Ihre Fotos nicht neu indizieren**.
- **Wenn Sie Kino noch nicht nutzen**: nichts zu tun; die Fotogalerie funktioniert weiter wie in 3.0.
- **So aktivieren Sie den Reiter Kino nach der Aktualisierung**:
  1. Öffnen Sie **Einstellungen → Kino**.
  2. Tragen Sie den **Kino-Ordner** mit Ihren Filmen, Serien, Clips oder DVD-/Blu-ray-Ordnern ein (z. B. `/mnt/cinema` oder `D:\Videos\Cinema`).
  3. *(Optional)* Tragen Sie Ihr lokales **physisches optisches Laufwerk** ein (z. B. `/dev/sr0`, `/Volumes/...` oder `D:\`). Auf einem Computer oder Server ohne Laufwerk einfach leer lassen.
  4. Klicken Sie auf **Speichern** und anschließend auf **Kino indizieren** (getrennt von **Fotos indizieren** in der Werkzeugleiste oben).
  5. *(Optional)* Klicken Sie auf **Anreichern (Wikidata)**, um Kategorien, Jahr, Regisseur und Beschreibung automatisch zu laden (CC0 Open Data, ohne API-Schlüssel).

## Windows

1. Schließen Sie das schwarze Fenster. Die Seite muss angehalten sein.
2. Entpacken Sie das neue Zip **über denselben Ordner** (oft `Documents\galerie-medias\`). Ersetzen Sie die Dateien.
3. Fassen Sie `C:\Users\IHRNAME\AppData\Roaming\GaleriePhotos\` nicht an.
4. Kopieren Sie die Fotos nicht erneut.
5. Doppelklick auf `reparer-installation.bat` und warten Sie bis zum Ende.
6. Doppelklick auf `ouvrir-galerie.bat`.
7. Im Browser: **Strg+F5**.
8. Einstellungen: **Galerie Médias 4.0**.

Ein vollständiges neues Indexieren ist unnötig. Der Fernseher nutzt auch Port **8766**: einmal `autoriser-parefeu.bat`, wenn er die Seite nicht sieht.

## macOS

1. Beenden Sie das Terminal-Fenster (`start-mac.command`).
2. Entpacken Sie das neue Zip **über denselben Ordner**.
3. Fassen Sie `Library/Application Support/GaleriePhotos` nicht an.
4. Doppelklick auf `reparer-installation-mac.command`, oder starten Sie `start-mac.command` erneut.
5. Laden Sie die Seite neu (Cmd+Shift+R).
6. Einstellungen: **Galerie Médias 4.0**.

## Linux

1. Halten Sie die Seite an (Terminal schließen, oder `systemctl --user stop photo-library.service`, falls ein systemd-Dienst läuft).
2. Ersetzen Sie die Programmdateien im selben Ordner. Löschen Sie nicht `~/.config/galerie-photos/` und nicht `~/.cache/photo-library/`.
3. Starten Sie `bash start-linux.sh` erneut (oder `systemctl --user start photo-library.service`). Wenn `REQUIS-de.md` sich geändert hat, aktualisiert `start-linux.sh` die Pakete.
4. Laden Sie die Seite neu (**Strg+F5**).
5. Einstellungen: **Galerie Médias 4.0**. *(Optional: hängen Sie Ihren Video-Ordner ein, z. B. `/mnt/cinema`, und tragen Sie ihn unter **Einstellungen → Kino** ein.)*

## Nicht tun

| Nicht… | Warum |
|--------|--------|
| In einen **neuen** Ordner installieren und alles neu indexieren | Gesichter, Alben und Konten liegen in GaleriePhotos, nicht im Zip |
| `AppData\Roaming\GaleriePhotos`, Application Support oder `~/.config/galerie-photos` löschen | Derselbe Grund |
| Die Fotos „zur Sicherheit“ erneut kopieren | Unnötig |
| Das Zip starten, ohne es zu entpacken | Python wird nicht gefunden |
| Zwei Fenster gleichzeitig öffnen | Der Port ist schon belegt |

## Wenn es nicht mehr startet

1. Schließen Sie alle Fenster der Seite.
2. `reparer-installation.bat`, `reparer-installation-mac.command` oder `bash start-linux.sh`.
3. Starten Sie `ouvrir-galerie.bat`, `start-mac.command` oder `start-linux.sh` erneut.
4. Die Datei `reparer-installation.log` neben den Skripten enthält die Einzelheiten.

Laufwerk nicht gefunden: `lister-disques.bat`, dann den Pfad in den Einstellungen korrigieren.
