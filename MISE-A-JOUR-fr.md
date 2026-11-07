# Galerie Médias 3.0 — mettre à jour un site déjà installé

Ce fichier sert si le site tourne déjà. Première installation : [INSTALL-fr.md](INSTALL-fr.md).

Autres langues : [English](MISE-A-JOUR-en.md), [Español](MISE-A-JOUR-es.md), [Deutsch](MISE-A-JOUR-de.md).

Après la mise à jour, l’onglet **Paramètres** affiche **Galerie Médias 3.0** (aussi en haut à gauche).

## Quoi de neuf en 3.0

- Menus : **Photos, Personnes, Scènes, Doublons, Carte, Albums, Corbeille, Paramètres**.
- Langue (français, anglais, espagnol, allemand) et thème de couleur, en haut à droite. Le choix reste dans ce navigateur.
- **Mot de passe oublié** : dans Paramètres → Courriel, indiquez le serveur et l’adresse du site, puis le courriel de chaque compte. Le lien est valable une heure.
- Le thème **Ambre** est le même qu’avant. Les autres : Encre, Océan, Forêt, Papier, Jour.
- Le menu **?** ouvre l’aide, dans la langue du site.
- Le site n’écoute qu’en **HTTPS**.

Les **photos** et la **base** (visages, albums, comptes) ne bougent pas. On remplace seulement le programme.

## Windows

1. Fermez la fenêtre noire. Le site doit être arrêté.
2. Décompressez le nouveau zip **par-dessus le même dossier** (souvent `Documents\galerie-medias\`). Remplacez les fichiers.
3. Ne touchez pas à `C:\Users\VOTRENOM\AppData\Roaming\GaleriePhotos\`.
4. Ne recopiez pas les photos.
5. Double-cliquez `reparer-installation.bat` et laissez la fenêtre aller jusqu’à la fin.
6. Double-cliquez `ouvrir-galerie.bat`.
7. Dans le navigateur : **Ctrl+F5**.
8. Paramètres : **Galerie Médias 3.0**.

Inutile de tout réindexer. La télévision utilise aussi le port **8766** : `autoriser-parefeu.bat` une fois, si elle ne voit pas le site.

## macOS

1. Quittez la fenêtre Terminal (`start-mac.command`).
2. Décompressez le nouveau zip **par-dessus le même dossier**.
3. Ne touchez pas à `Bibliothèque/Application Support/GaleriePhotos`.
4. Double-clic `reparer-installation-mac.command`, ou relancez `start-mac.command`.
5. Rechargez la page (Cmd+Shift+R).
6. Paramètres : **Galerie Médias 3.0**.

## Linux

1. Arrêtez le site (fermez le terminal, ou arrêtez le service s’il y en a un).
2. Remplacez les fichiers du programme dans le même dossier. Ne supprimez pas `~/.config/galerie-photos/` ni `~/.cache/photo-library/`.
3. Relancez `bash start-linux.sh`. Si `REQUIS-fr.md` a changé, le script remet les paquets à jour.
4. Rechargez la page (Ctrl+F5).
5. Paramètres : **Galerie Médias 3.0**.

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
