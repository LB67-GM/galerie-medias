# Galerie Médias — installation

Version **3.0**. Le site reste sur votre ordinateur. Les photos peuvent rester sur un disque USB. La base (SQLite, miniatures, réglages) reste sur l’ordinateur, jamais sur le USB. Le site n’écoute qu’en **HTTPS**. Il n’y a pas d’adresse `http://`.

La même notice : [English](INSTALL-en.md), [Español](INSTALL-es.md), [Deutsch](INSTALL-de.md). Prérequis : [REQUIS-fr.md](REQUIS-fr.md). Dans le site : `static/install/`. Les menus sont expliqués dans l’aide **?**.

## Où sont les fichiers

- Photos : le dossier indiqué dans **Paramètres**. Exemple : `E:\Photos`.
- Windows : `C:\Users\VOTRENOM\AppData\Roaming\GaleriePhotos\` (`ouvrir-dossier-base.bat`).
- macOS : `Bibliothèque/Application Support/GaleriePhotos/`.
- Linux : `~/.config/galerie-photos/`.

Décompressez le programme dans Documents, pas depuis le zip encore ouvert.

## Windows

1. [Python 3.10+](https://www.python.org/downloads/) depuis python.org, pas le Microsoft Store. Cochez **Add python.exe to PATH**.
2. Décompressez, par exemple dans `Documents\galerie-medias\`.
3. `preparer-python.bat` (crée `.venv`, sans ouvrir le site).
4. `ouvrir-galerie.bat` ou `start-windows.bat`. La première fois, quelques minutes, Internet requis. Pare-feu : **Oui**. Le Wi-Fi doit être **Privé**.
5. Le navigateur ouvre [https://127.0.0.1:8765](https://127.0.0.1:8765). Premier passage : continuer vers le site (certificat de la maison).

Laissez la fenêtre noire ouverte. Elle suit la langue de Windows (français, anglais, espagnol, allemand).

Utiles : `creer-raccourci-bureau.bat`, `lister-disques.bat`, `autoriser-parefeu.bat` (ports **8765** et **8766**), `reparer-installation.bat`, `gerer-utilisateurs.bat`.

## macOS

1. Python 3.10+ : [python.org](https://www.python.org/downloads/) ou `brew install python`.
2. Double-clic sur `start-mac.command`. Si macOS bloque : clic droit → **Ouvrir**.
3. Mot de passe possible pour le pare-feu (règle permanente). Refuser laisse le site utilisable sur cet ordinateur. Réessayer : `autoriser-parefeu-mac.command`.
4. Adresse : `https://127.0.0.1:8765`. Continuer vers le site au premier passage.

Nouvelle version : `reparer-installation-mac.command`. La fenêtre suit la langue du Mac. Classement : `classer-annee-mois-mac.command`, puis `classer-lieux-mac.command`.

## Linux

1. Python 3.10+. Debian ou Ubuntu : `sudo apt-get install python3 python3-venv python3-pip`. Fedora : `sudo dnf install python3`.
2. Décompressez, par exemple dans `~/Documents/galerie-medias/`.
3. `bash start-linux.sh`.
4. Le script prépare `.venv`, tente d’ouvrir les ports 8765 et 8766 (firewalld ou ufw), puis lance le site. Un refus du mot de passe d’administrateur laisse le site utilisable sur cet ordinateur.
5. Adresse : `https://127.0.0.1:8765`. Continuer vers le site au premier passage.

Laissez le terminal ouvert. Les messages suivent `LANG` (fr, en, es, de ; sinon français).

## HTTPS et certificat par le DNS

Au premier démarrage, un **certificat de la maison** est créé. Le navigateur avertit une fois.

Pour un nom public, par exemple `https://photos.example.com:8765`, le certificat vient de **Let’s Encrypt**, prouvé par le **DNS**. Aucun port n’est ouvert sur la box. Le certificat suit le nom : lors d’un déménagement, changez l’adresse DNS, pas le certificat. Le détail est aussi dans l’aide, section HTTPS.

1. Réservez le nom chez un bureau qui héberge le DNS. Cloudflare convient. Ne payez pas un certificat en plus.
2. Enregistrement **A**, nom **@**, adresse de l’ordinateur sur le réseau de la maison. Nuage Cloudflare **gris**. Ne redirigez pas le port 8765 vers Internet.
3. La commande qui demande le certificat dépend du système. Let’s Encrypt : https://letsencrypt.org/ . Certbot : https://certbot.eff.org/ . WireGuard, le VPN pour joindre la maison hors du Wi-Fi : https://www.wireguard.com/install/ .

Linux : `sudo apt-get install certbot python3-certbot-dns-cloudflare`, jeton dans `/etc/letsencrypt/cloudflare.ini` (droits 600), puis `sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --dns-cloudflare-propagation-seconds 30 -d photos.example.com`. Copiez `fullchain.pem` et `privkey.pem` dans `~/.config/galerie-photos/cache/letsencrypt/` (ou `~/.cache/photo-library/letsencrypt/` si le cache est là).

macOS : Homebrew (https://brew.sh/), `brew install certbot`, puis le module Cloudflare dans l’environnement de Certbot. Copiez `fullchain.pem` et `privkey.pem` dans `~/Library/Application Support/GaleriePhotos/cache/letsencrypt/`.

Windows : la commande Linux ne fonctionne pas telle quelle. Copiez les deux fichiers déjà obtenus, ou installez Python (https://www.python.org/downloads/) puis `py -m pip install certbot certbot-dns-cloudflare`. Déposez les deux fichiers dans `C:\Users\VOTRENOM\AppData\Roaming\GaleriePhotos\cache\letsencrypt\`.

Le détail est dans l’aide du site, section HTTPS. Sans ces deux fichiers, le certificat de la maison reste en service.

La télé (LG, Samsung) utilise le port **8766** sans certificat. Ce n’est pas l’adresse du site.

## Première utilisation

1. Branchez le disque.
2. **Paramètres** : dossier des photos, puis **Enregistrer**.
3. Classez avant d’indexer. En vrac ou déjà par année : `classer-lieux`. Arbre disparate (DCIM) : `classer-annee-mois`, puis `classer-lieux`. Choix 1 = simuler, 2 = écrire. Linux : `.venv/bin/python tools/sort_annee_mois.py SOURCE DEST`, puis `.venv/bin/python tools/sort_lieux.py -d DEST`, avec `--apply` pour écrire.
4. **Indexer**.

Les dossiers sur le disque s’appellent `Annee 2024` et `Juin 2024`.

## Mise à jour

Fermez le site. Décompressez le nouveau zip par-dessus le même dossier. Ne supprimez pas GaleriePhotos ni `~/.config/galerie-photos`. Ne recopiez pas les photos. Puis `reparer-installation.bat`, `reparer-installation-mac.command`, ou `bash start-linux.sh`. Voir [MISE-A-JOUR-fr.md](MISE-A-JOUR-fr.md).

## Si la page ne s’ouvre pas

- Python : python.org, case PATH, relancez.
- Fermez l’ancienne fenêtre et ouvrez `https://127.0.0.1:8765`.
- `http://` ne répond pas : le site est uniquement en HTTPS.
- Photos : disque branché, bonne lettre (`lister-disques.bat`).
