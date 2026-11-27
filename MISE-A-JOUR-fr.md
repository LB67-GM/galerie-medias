# Galerie Médias 4.0 — mettre à jour un site déjà installé

Ce fichier sert si le site tourne déjà. Première installation : [INSTALL-fr.md](INSTALL-fr.md).

Autres langues : [English](MISE-A-JOUR-en.md), [Español](MISE-A-JOUR-es.md), [Deutsch](MISE-A-JOUR-de.md).

Après la mise à jour, l’onglet **Paramètres** affiche **Galerie Médias 4.0** (aussi en haut à gauche).

## Quoi de neuf en 4.0

- Nouvel onglet **Cinéma** (accessible aux comptes administrateur et **lecture**) : lecteur vidéo open source intégré avec streaming **HLS à la volée** (`hls.js`), choix de piste audio, sous-titres, chapitres, qualité et **reprise de lecture** (*Continuer la lecture*).
- Formats pris en charge dans Cinéma : fichiers vidéo (`.mp4`, `.m4v`, `.mkv`, `.avi`, `.mpg`, `.mov`…), structures et images **DVD** (`VIDEO_TS`, `.iso`), **Blu-ray** (`BDMV`, `.iso`), et **lecteur optique physique** optionnel (laissez vide sur un serveur sans lecteur).
- Filtres par **Type** (Film, Série, Clip musical, Documentaire), **Catégorie** et **Année**, avec enrichissement à la demande via **Wikidata / Wikipédia** (données ouvertes CC0, sans clé API) et édition manuelle verrouillable.
- Bouton **Télé (DLNA)** intégré dans le lecteur Cinéma (port `8766` sur le réseau local).
- Migration automatique de la base SQLite et des réglages : dans **Paramètres → Cinéma**, indiquez votre dossier vidéo (par exemple `/mnt/cinema`), enregistrez, puis cliquez **Indexer Cinéma**.
- Deux indexations distinctes : **Indexer Photos** (barre d’outils en haut, pour la bibliothèque Photos) et **Indexer Cinéma** (onglet Cinéma ou Paramètres → Cinéma, pour les films/séries/clips). Les films et clips peuvent être envoyés à la **Corbeille** (30 jours, restaurables ou supprimables définitivement).
- Menus : **Photos, Cinéma, Personnes, Scènes, Doublons, Carte, Albums, Corbeille, Paramètres**.
- Langue (français, anglais, espagnol, allemand) et thème de couleur, en haut à droite. Le choix reste dans ce navigateur.
- **Mot de passe oublié** : dans Paramètres → Courriel, indiquez le serveur et l’adresse du site, puis le courriel de chaque compte. Le lien est valable une heure.
- Le thème **Ambre** est le même qu’avant. Les autres : Encre, Océan, Forêt, Papier, Jour.
- Le menu **?** ouvre l’aide, dans la langue du site.
- Le site n’écoute qu’en **HTTPS**.

Les **photos** et la **base** (visages, albums, comptes) ne bougent pas. On remplace seulement le programme.

## Passer de 3.0 à 4.0 : migration automatique et activation de Cinéma

- **Ce qui est automatique au premier démarrage en 4.0** : vos photos, visages, scènes, albums, comptes, réglages (`config.json`) et certificats HTTPS restent intacts. La base SQLite ajoute automatiquement les tables **Cinéma** (catalogue, catégories, reprise de lecture et corbeille 30 jours). Aucun nouveau paquet Python n’est obligatoire et il est **inutile de réindexer vos photos**.
- **Si vous n’utilisez pas encore Cinéma** : vous n’avez rien à changer ; la galerie Photos continue de fonctionner exactement comme en 3.0.
- **Pour activer l’onglet Cinéma après la mise à jour** :
  1. Ouvrez **Paramètres → Cinéma**.
  2. Indiquez le **Dossier Cinéma** qui contient vos films, séries, clips ou dossiers DVD/Blu-ray (ex. `/mnt/cinema` ou `D:\Videos\Cinema`).
  3. *(Optionnel)* Indiquez votre **Lecteur optique physique** natif (ex. `/dev/sr0`, `/Volumes/...` ou `D:\`). Laissez ce champ vide sur un ordinateur ou un serveur sans lecteur optique.
  4. Cliquez **Enregistrer**, puis **Indexer Cinéma** (indépendant du bouton **Indexer Photos** dans la barre d’outils en haut).
  5. *(Optionnel)* Cliquez **Enrichir (Wikidata)** pour remplir automatiquement catégories, années, réalisateurs et résumés (données ouvertes CC0, sans clé API).

## Windows

1. Fermez la fenêtre noire. Le site doit être arrêté.
2. Décompressez le nouveau zip **par-dessus le même dossier** (souvent `Documents\galerie-medias\`). Remplacez les fichiers.
3. Ne touchez pas à `C:\Users\VOTRENOM\AppData\Roaming\GaleriePhotos\`.
4. Ne recopiez pas les photos.
5. Double-cliquez `reparer-installation.bat` et laissez la fenêtre aller jusqu’à la fin.
6. Double-cliquez `ouvrir-galerie.bat`.
7. Dans le navigateur : **Ctrl+F5**.
8. Paramètres : **Galerie Médias 4.0**.

Inutile de tout réindexer. La télévision utilise aussi le port **8766** : `autoriser-parefeu.bat` une fois, si elle ne voit pas le site.

## macOS

1. Quittez la fenêtre Terminal (`start-mac.command`).
2. Décompressez le nouveau zip **par-dessus le même dossier**.
3. Ne touchez pas à `Bibliothèque/Application Support/GaleriePhotos`.
4. Double-clic `reparer-installation-mac.command`, ou relancez `start-mac.command`.
5. Rechargez la page (Cmd+Shift+R).
6. Paramètres : **Galerie Médias 4.0**.

## Linux

1. Arrêtez le site (fermez le terminal, ou `systemctl --user stop photo-library.service` si vous utilisez un service systemd).
2. Remplacez les fichiers du programme dans le même dossier. Ne supprimez pas `~/.config/galerie-photos/` ni `~/.cache/photo-library/`.
3. Relancez `bash start-linux.sh` (ou `systemctl --user start photo-library.service`). Si `REQUIS-fr.md` a changé, `start-linux.sh` remet les paquets à jour.
4. Rechargez la page (**Ctrl+F5**).
5. Paramètres : **Galerie Médias 4.0**. *(Optionnel : montez votre dossier vidéo, par exemple `/mnt/cinema`, puis configurez-le dans **Paramètres → Cinéma**.)*

## À ne pas faire

| Ne pas… | Pourquoi |
|---------|----------|
| Installer dans un **nouveau** dossier et tout réindexer | Visages, albums et comptes sont dans GaleriePhotos, pas dans le zip |
| Effacer `AppData\Roaming\GaleriePhotos`, Application Support ou `~/.config/galerie-photos` | Même raison |
| Recopier les photos « pour être sûr » | Inutile |
| Lancer le zip sans le décompresser | Le site ne trouvera pas Python |
| Lancer deux fenêtres en même temps | Le port est déjà pris |

## Si ça ne démarre plus

1. Fermez toutes les fenêtres du site.
2. `reparer-installation.bat`, `reparer-installation-mac.command`, ou `bash start-linux.sh`.
3. Relancez `ouvrir-galerie.bat`, `start-mac.command` ou `start-linux.sh`.
4. Le fichier `reparer-installation.log`, à côté des scripts, contient le détail.

Disque introuvable : `lister-disques.bat`, puis corrigez le chemin dans Paramètres.
