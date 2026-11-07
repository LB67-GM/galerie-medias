# Galerie Médias 3.0 — eine bereits installierte Seite aktualisieren

Diese Datei gilt, wenn die Seite schon läuft. Erste Installation: [INSTALL-de.md](INSTALL-de.md).

Andere Sprachen: [Français](MISE-A-JOUR-fr.md), [English](MISE-A-JOUR-en.md), [Español](MISE-A-JOUR-es.md).

Nach der Aktualisierung zeigt **Einstellungen** **Galerie Médias 3.0** (auch oben links).

## Neu in 3.0

- Menüs: **Fotos, Personen, Szenen, Duplikate, Karte, Alben, Papierkorb, Einstellungen**.
- Sprache (Französisch, Englisch, Spanisch, Deutsch) und Farbthema, oben rechts. Die Wahl bleibt in diesem Browser.
- **Passwort vergessen**: unter Einstellungen → E-Mail den Server und die Adresse der Seite eintragen, dann die E-Mail jedes Kontos. Der Link gilt eine Stunde.
- Das Thema **Bernstein** bleibt. Die anderen: Tinte, Ozean, Wald, Papier, Tag.
- Das Menü **?** öffnet die Hilfe, in der Sprache der Seite.
- Die Seite hört nur auf **HTTPS**.

Die **Fotos** und die **Datenbank** (Gesichter, Alben, Konten) bleiben. Nur das Programm wird ersetzt.

## Windows

1. Schließen Sie das schwarze Fenster. Die Seite muss angehalten sein.
2. Entpacken Sie das neue Zip **über denselben Ordner** (oft `Documents\galerie-medias\`). Ersetzen Sie die Dateien.
3. Fassen Sie `C:\Users\IHRNAME\AppData\Roaming\GaleriePhotos\` nicht an.
4. Kopieren Sie die Fotos nicht erneut.
5. Doppelklick auf `reparer-installation.bat` und warten Sie bis zum Ende.
6. Doppelklick auf `ouvrir-galerie.bat`.
7. Im Browser: **Strg+F5**.
8. Einstellungen: **Galerie Médias 3.0**.

Ein vollständiges neues Indexieren ist unnötig. Der Fernseher nutzt auch Port **8766**: einmal `autoriser-parefeu.bat`, wenn er die Seite nicht sieht.

## macOS

1. Beenden Sie das Terminal-Fenster (`start-mac.command`).
2. Entpacken Sie das neue Zip **über denselben Ordner**.
3. Fassen Sie `Library/Application Support/GaleriePhotos` nicht an.
4. Doppelklick auf `reparer-installation-mac.command`, oder starten Sie `start-mac.command` erneut.
5. Laden Sie die Seite neu (Cmd+Shift+R).
6. Einstellungen: **Galerie Médias 3.0**.

## Linux

1. Halten Sie die Seite an (Terminal schließen, oder den Dienst anhalten, falls es einen gibt).
2. Ersetzen Sie die Programmdateien im selben Ordner. Löschen Sie nicht `~/.config/galerie-photos/` und nicht `~/.cache/photo-library/`.
3. Starten Sie `bash start-linux.sh` erneut. Wenn `REQUIS-de.md` sich geändert hat, aktualisiert das Skript die Pakete.
4. Laden Sie die Seite neu (Strg+F5).
5. Einstellungen: **Galerie Médias 3.0**.

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
