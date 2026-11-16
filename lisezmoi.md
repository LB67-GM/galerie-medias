# Galerie Médias

Version anglaise : [readme.md](readme.md).

Site web local **Galerie Médias** (version **3.0**) : visualiser, filtrer et exporter photos et vidéos du dossier indiqué dans **Paramètres** (sans déplacer la bibliothèque). Langues français, anglais, espagnol et allemand. Six thèmes de couleur. Le menu **?** ouvre l’aide dans la langue choisie (`static/help/`). Mise à jour d’un site déjà installé : [MISE-A-JOUR-fr.md](./MISE-A-JOUR-fr.md) (aussi [en](./MISE-A-JOUR-en.md), [es](./MISE-A-JOUR-es.md), [de](./MISE-A-JOUR-de.md)). Prérequis : [REQUIS-fr.md](./REQUIS-fr.md).

Filtres : année, **mois**, lieu, **moment** (voyage, anniversaire, mariage, soirée…), type (photo / vidéo), album (dont **Favoris**), paysage / bâtiment, recherche (fichier, lieu, moment ou prénom, **mot entier** : Rome ≠ Andromède ; la croix du champ ramène toute la galerie). Pas de menu Personne à part : un prénom se tape dans la recherche. Ils se **combinent** (ET). Année = dossier **ou** date EXIF. Mois = mois EXIF **ou** dossier `Janvier 2006`. Sous une année : **Lieu** = géographie (`Lisbonne`, `Rome`) ; **Moment** = tout le reste (`Vacances Italie`, `Anniversaire 2024`). Sans filtre : les plus récentes d’abord (année du dossier, pas l’EXIF parfois faux). **Cette page** → **Tout sélectionné**. Compteurs : bibliothèque (en-tête), filtre, page, cochées. Maj+clic pour une plage. Menus collants en défilant. **Ajouter à l’album** seulement si des photos sont cochées ; **Retirer de l’album** aussi (dans un album : retrait de celui-ci) ; étoile = albums (ajouter ou retirer). **Lieu** (corrige le lieu affiché et la pastille sur la carte, pas le dossier sur le disque ; mini-carte : pastille au centre, glisser la carte ; option dossier = dossier immédiat seulement). **Déplacer** (photos cochées) : vers un dossier déjà présent dans la même année ; le fichier quitte son dossier, la vidéo du même nom part avec, Moment et Lieu suivent. Changer un filtre vide la sélection. **Désélectionner**. **Supprimer** : 500 photos max ; après confirmation, retour Galerie sans filtre. L’étiquetage église / montagne / ville se fait dans l’onglet **Paysages**, pas dans le bandeau de la galerie.

Clic sur une miniature : grand format (ratio respecté). Pincer pour zoomer (molette aussi). **Pivoter / rogner** : l’original va dans l’onglet **Corbeille** (Restaurer annule). Les vidéos iPhone (HEVC) sont converties pour le navigateur (`/api/media/{id}/play`). Visages : touche **X** = Pas lui. Bouton **TV (DLNA)** : à côté de Diaporama ; envoi vers une télé LG/Samsung du LAN (HTTPS 8765, la TV lit HTTP `8766`). Les vidéos sont converties en H.264 avant l’envoi.

Onglet **Carte** : pastilles des **dossiers lieu** (OpenStreetMap, Internet). Position : GPS des photos si déjà indexé (`scan-gps`), sinon géocodage du nom (`Portugal`, `Rome`…). Clic pastille → galerie sur ce lieu (autres filtres vidés). Un lieu positionné dans **Lieu** reste dans le menu. **Lieu** sur des photos cochées ouvre une mini-carte : la pastille reste au centre, on glisse la carte, le nom se met à jour, **Enregistrer** déplace la pastille mondiale. Homonymes : Manhattan = New York, San Jose Californie ≠ Espagne.

## Prérequis

- Python 3.10+
- `ffmpeg` / `ffprobe` : métadonnées vidéo (`ffprobe`). Miniatures **et** lecture HEVC iPhone : `ffmpeg` fourni par `imageio-ffmpeg` (le `ffmpeg` Fedora « free » n’a souvent pas HEVC). Le navigateur reçoit du H.264 via `/api/media/{id}/play`.

## Installation (une fois)

```bash
cd /chemin/vers/photo-library
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python scripts/lire_paquets.py --write .paquets.txt
.venv/bin/pip install -r .paquets.txt
chmod +x run.py
```

La liste des paquets est dans [REQUIS-fr.md](./REQUIS-fr.md) (aussi en, es, de). SQLite est dans Python. Les scripts `start-linux.sh`, `start-mac.command` et `start-windows.bat` font cette installation.

## Syntaxe

```bash
cd /chemin/vers/photo-library

.venv/bin/python run.py serve [options]
.venv/bin/python run.py index [--year YYYY | --all] [options]
.venv/bin/python run.py faces [--year YYYY] [options]
.venv/bin/python run.py backup [--dest DOSSIER]
.venv/bin/python run.py restore DOSSIER-BACKUP [--no-config]
.venv/bin/python run.py completer-lieux [--apply]
.venv/bin/python run.py scan-gps [--year YYYY]
.venv/bin/python run.py users [--list | --create IDENTIFIANT --role lecture|admin | --delete IDENTIFIANT]
.venv/bin/python scripts/restore_backup.py DOSSIER-BACKUP
```

Sans sous-commande, `serve` est lancé.

### Comptes

Sans aucun compte, le site reste ouvert. Dès qu’il y en a un, la page de connexion s’affiche.

```bash
.venv/bin/python run.py users --list
.venv/bin/python run.py users --create leo --role lecture
.venv/bin/python run.py users --set-password leo
.venv/bin/python run.py users --unlock leo
.venv/bin/python run.py users --delete leo
```

`--role` : `admin` ou `lecture`. Mot de passe : **8 caractères** minimum (demandé, ou `--password`). `--email` enregistre le courriel. Trois essais, puis le compte est verrouillé. **Mot de passe oublié** envoie un lien si le courriel du compte et le serveur (Paramètres → Courriel) sont renseignés. Sinon un admin lance `--set-password IDENTIFIANT` (nouveau mot de passe + déverrouillage) ou `--unlock` (même mot de passe). `--set-email IDENTIFIANT --email …` change le courriel. Windows : `gerer-utilisateurs.bat` ; Mac : `gerer-utilisateurs-mac.command`.

### Serveur

HTTPS seulement. Certificat Let’s Encrypt s’il est dans `cache/letsencrypt/`, sinon certificat maison (`tls/` dans le cache). Premier passage avec le certificat maison : continuer vers le site (c’est votre ordinateur). Il n’y a pas de mode HTTP.

| Option | Effet |
|--------|--------|
| `--host` | Adresse (défaut : `127.0.0.1`) |
| `--port` | Port (défaut : `8765`) |
| `--tls-host NOM` | Nom ou IP supplémentaire dans le certificat maison (répétable) |
| `-d`, `--library PATH` | Bibliothèque (sinon le dossier de Réglages) |
| `--cache PATH` | Cache SQLite + miniatures (défaut : `~/.cache/photo-library`) |

Ouvrir [https://127.0.0.1:8765](https://127.0.0.1:8765) sur cette machine, ou `https://<IP-LAN>:8765` depuis un téléphone (même avertissement certificat, une fois).

### Démarrage sur le réseau local

Le site écoute en HTTPS. Le pare-feu du réseau local peut ouvrir les ports 8765 (site) et 8766 (télévision).

Sauvegarde automatique : `scripts/systemd/photo-library-backup.timer` (chaque mercredi 23:00). Copie SQLite + réglages + `site/` vers `backup-AAAA-MM-JJ` (4 plus récentes). Les miniatures ne sont pas copiées. `scripts/weekly_index.py` réindexe la bibliothèque ; à planifier si vous le souhaitez.

Ne pas lancer un second `run.py serve` en parallèle (le port serait pris).

### Index

Lit le dossier des photos, met à jour SQLite, génère les miniatures **en local**.

```bash
.venv/bin/python run.py index --year 2024
.venv/bin/python run.py index --year 2024 --limit 50
.venv/bin/python run.py index --all
```

Sans `--year` ni `--all`, tout est indexé (long si la bibliothèque est grande). L’index se relance aussi depuis l’interface.

### Lieux vides (`completer-lieux`)

Parcourt la bibliothèque (**SQLite seulement**, les dossiers ne bougent pas). Reclasse Lieu vs Moment : villes dans Lieu, le reste (anniversaires, mariages, vacances…) dans Moment. Un lieu verrouillé (`Lieu` dans la galerie) n’est pas modifié. Dry-run par défaut.

```bash
.venv/bin/python run.py completer-lieux
.venv/bin/python run.py completer-lieux --apply
.venv/bin/python scripts/completer_lieux.py --apply
```

`--no-index` saute la recherche de fichiers absents de SQLite. `--keep-generic` laisse `Vacances` tel quel.

### GPS pour la carte (`scan-gps`)

Lit le GPS des fichiers **une fois** (EXIF / ISO6709, et l’index de `sort_lieux` s’il existe) et le stocke dans SQLite. La carte utilise ce GPS (moyenne du lieu), sinon le géocodage du nom de dossier. **Lieu** reste prioritaire.

```bash
.venv/bin/python run.py scan-gps
.venv/bin/python run.py scan-gps --year 2016
```

Les index suivants ne relisent le GPS que pour les fichiers nouveaux ou modifiés.

### Visages

Détection locale (InsightFace si installé, sinon OpenCV YuNet + SFace). Aucun cloud.

Routine à suivre :

1. **Indexer** les photos (bouton en haut, ou `run.py index`).
2. **Détecter visages** — première passe, souvent longue. Le modèle InsightFace `buffalo_l` (~280 Mo) se télécharge une fois dans `~/.insightface/`. Ce modèle n’est pas sous MIT : InsightFace le réserve à la recherche non commerciale. Sans lui, la détection utilise OpenCV (YuNet et SFace).
3. Onglet **Visages** : paquets automatiques souvent mélangés. Cochez les visages reconnus, **Nommer la sélection**. **Revoir** amène la première image de cette personne en haut de l’écran, puis **Pas …** pour retirer les erreurs. Ensuite on peut filtrer la galerie par ce nom.
4. **Photos nouvelles** : **Indexer** d’abord, puis **Détecter visages** encore. Seuls les fichiers pas encore analysés sont traités. Ceux qui ressemblent à une personne déjà nommée sont rattachés ; le reste apparaît en nouveaux groupes.

Sans nouvel index, recliquer « Détecter visages » ne refait rien. Nommer un groupe ne relance pas toute la détection.

```bash
.venv/bin/python run.py faces --year 2024
.venv/bin/python run.py faces --year 2024 --limit 20
```

### Paysages / bâtiments

Onglet **Paysages** (comme Visages). La galerie garde seulement un **filtre** (plage, ville, église…).

1. Choisissez une **année** (et un lieu) pour ne pas tout mélanger.
2. **Détecter paysages / bâtiments** — heuristique, souvent imparfaite.
3. Cochez les photos justes, **Étiqueter la sélection** (église, montagne, ville…).
4. Pastille **Revoir**, puis **Pas …** pour retirer une erreur. En grand format : **Ajouter** une étiquette ou **Pas …**.

```bash
.venv/bin/python run.py scenes --year 2025 --place Paris
```

### Sauvegarde et restauration

Réglages → **Sauvegarde** : un dossier parent (disque externe ou autre dossier) et le bouton **Sauvegarder maintenant**. Chaque run crée `backup-AAAA-MM-JJ/` avec `library.sqlite`, `config.json`, `secret.key`, `site/` (HTML, CSS, JS, Python), `manifest.json`. Rotation : 4 dossiers.

Restauration (arrête le service systemd si besoin, puis le relance) :

```bash
.venv/bin/python scripts/restore_backup.py /chemin/backup-2026-09-01
# ou sans écraser les réglages :
.venv/bin/python scripts/restore_backup.py /chemin/backup-2026-09-01 --no-config
```

Unité systemd modèle : `scripts/systemd/photo-library-backup.{service,timer}`.

## Archive pour un autre ordinateur

`python scripts/pack_distrib.py` produit `dist/galerie-medias-3.0-AAAA-MM-JJ.zip` (et `.tar.gz`). Installation : [INSTALL-fr.md](./INSTALL-fr.md). Mise à jour : [MISE-A-JOUR-fr.md](./MISE-A-JOUR-fr.md). Les mêmes fichiers existent en anglais, espagnol et allemand.

Première fois : classer avant d’indexer. Arbre disparate : `classer-annee-mois.bat "E:\Vrac" "E:\Photos"` (simulation), puis `--apply` (copie vers `Annee/Mois`), puis `classer-lieux.bat "E:\Photos"`. macOS : `classer-annee-mois-mac.command` puis `classer-lieux-mac.command`. Linux : `tools/sort_annee_mois.py SOURCE DEST` puis `tools/sort_lieux.py -d DEST --all`. Export Messenger (dates dans `message_*.json`) : `tools/sort_lieux.py --facebook --facebook-dir DOSSIER` (simulation, puis `--apply`).

SQLite et miniatures restent sur l’ordinateur. Les photos peuvent être sur un USB.

## iCloud

Avant d’utiliser le téléchargement iCloud dans **Paramètres**, ouvrez une session sur [icloud.com](https://www.icloud.com) avec le même identifiant Apple, dans un navigateur. Apple affiche parfois ses conditions générales avant d’ouvrir les photos. Tant qu’elles ne sont pas acceptées, le téléchargement ne peut pas récupérer les photos.

## Licence

Galerie Médias est sous licence **MIT** ([LICENSE](./LICENSE)). Les composants tiers sont dans [NOTICE](./NOTICE) : Leaflet, drapeaux flag-icons, villes GeoNames, tuiles © OpenStreetMap contributors, FFmpeg (programme séparé, GPL). Le modèle de visages InsightFace `buffalo_l` n’est pas sous MIT.

## Important

1. La bibliothèque (dossier de Réglages) reste **en lecture seule**, sauf corbeille depuis la galerie et **Pivoter / rogner**.
2. Cache et base : `~/.cache/photo-library/` sur la machine qui fait tourner le site (en mode portable : `GaleriePhotos`).
3. L’export copie les originaux ; il ne les retire pas du dossier des photos.
4. La reconnaissance n’est pas infaillible (profils, enfants, vieillissement).
