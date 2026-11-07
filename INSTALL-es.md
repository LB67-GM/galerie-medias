# Galerie Médias — instalación

Versión **3.0**. El sitio permanece en su ordenador. Las fotos pueden quedarse en un disco USB. La base (SQLite, miniaturas, ajustes) permanece en el ordenador, nunca en el USB. El sitio solo escucha en **HTTPS**. No hay dirección `http://`.

La misma guía: [Français](INSTALL-fr.md), [English](INSTALL-en.md), [Deutsch](INSTALL-de.md). Requisitos: [REQUIS-es.md](REQUIS-es.md). En el sitio: `static/install/`. Los menús se explican en la ayuda **?**.

## Dónde están los archivos

- Fotos: la carpeta indicada en **Ajustes**. Ejemplo: `E:\Photos`.
- Windows: `C:\Users\SUNOMBRE\AppData\Roaming\GaleriePhotos\` (`ouvrir-dossier-base.bat`).
- macOS: `Library/Application Support/GaleriePhotos/`.
- Linux: `~/.config/galerie-photos/`.

Descomprima el programa en Documentos, no desde el zip todavía abierto.

## Windows

1. [Python 3.10+](https://www.python.org/downloads/) desde python.org, no desde Microsoft Store. Marque **Add python.exe to PATH**.
2. Descomprima, por ejemplo en `Documents\galerie-medias\`.
3. `preparer-python.bat` (crea `.venv`, sin abrir el sitio).
4. `ouvrir-galerie.bat` o `start-windows.bat`. La primera vez, unos minutos, hace falta Internet. Cortafuegos: **Sí**. La Wi-Fi debe ser **Privada**.
5. El navegador abre [https://127.0.0.1:8765](https://127.0.0.1:8765). En la primera visita, continúe hacia el sitio (certificado de casa).

Deje la ventana negra abierta. Sigue el idioma de Windows (francés, inglés, español, alemán).

Útiles: `creer-raccourci-bureau.bat`, `lister-disques.bat`, `autoriser-parefeu.bat` (puertos **8765** y **8766**), `reparer-installation.bat`, `gerer-utilisateurs.bat`.

## macOS

1. Python 3.10+: [python.org](https://www.python.org/downloads/) o `brew install python`.
2. Doble clic en `start-mac.command`. Si macOS lo bloquea: clic derecho → **Abrir**.
3. Puede pedirse la contraseña para el cortafuegos (regla permanente). Rechazarla deja el sitio usable en este ordenador. Reintentar: `autoriser-parefeu-mac.command`.
4. Dirección: `https://127.0.0.1:8765`. Continúe hacia el sitio en la primera visita.

Versión nueva: `reparer-installation-mac.command`. La ventana sigue el idioma del Mac. Clasificación: `classer-annee-mois-mac.command`, luego `classer-lieux-mac.command`.

## Linux

1. Python 3.10+. Debian o Ubuntu: `sudo apt-get install python3 python3-venv python3-pip`. Fedora: `sudo dnf install python3`.
2. Descomprima, por ejemplo en `~/Documents/galerie-medias/`.
3. `bash start-linux.sh`.
4. El script prepara `.venv`, intenta abrir los puertos 8765 y 8766 (firewalld o ufw) y luego inicia el sitio. Rechazar la contraseña de administrador deja el sitio usable en este ordenador.
5. Dirección: `https://127.0.0.1:8765`. Continúe hacia el sitio en la primera visita.

Deje el terminal abierto. Los mensajes siguen `LANG` (fr, en, es, de; si no, francés).

## HTTPS y certificado por DNS

En el primer arranque se crea un **certificado de casa**. El navegador avisa una vez.

Para un nombre público, por ejemplo `https://photos.example.com:8765`, el certificado viene de **Let’s Encrypt**, demostrado por **DNS**. No se abre ningún puerto en el router. El certificado sigue al nombre: en una mudanza, cambie la dirección DNS, no el certificado. Los mismos pasos están en la ayuda, sección HTTPS.

1. Reserve el nombre en un registrador que también aloje el DNS. Cloudflare sirve. No pague un certificado aparte.
2. Registro **A**, nombre **@**, dirección del ordenador en la red de casa. Nube de Cloudflare **gris**. No redirija el puerto 8765 hacia Internet.
3. La orden que pide el certificado depende del sistema. Let’s Encrypt: https://letsencrypt.org/ . Certbot: https://certbot.eff.org/ . WireGuard, la VPN para llegar a casa fuera de la Wi-Fi: https://www.wireguard.com/install/ .

Linux: `sudo apt-get install certbot python3-certbot-dns-cloudflare`, token en `/etc/letsencrypt/cloudflare.ini` (permisos 600), luego `sudo certbot certonly --dns-cloudflare --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini --dns-cloudflare-propagation-seconds 30 -d photos.example.com`. Copie `fullchain.pem` y `privkey.pem` en `~/.config/galerie-photos/cache/letsencrypt/` (o `~/.cache/photo-library/letsencrypt/` si el caché está ahí).

macOS: Homebrew (https://brew.sh/), `brew install certbot`, luego el módulo de Cloudflare en el entorno de Certbot. Copie `fullchain.pem` y `privkey.pem` en `~/Library/Application Support/GaleriePhotos/cache/letsencrypt/`.

Windows: la orden de Linux no funciona tal cual. Copie los dos archivos ya obtenidos, o instale Python (https://www.python.org/downloads/) y luego `py -m pip install certbot certbot-dns-cloudflare`. Deje los dos archivos en `C:\Users\SUNOMBRE\AppData\Roaming\GaleriePhotos\cache\letsencrypt\`.

El detalle está en la ayuda del sitio, sección HTTPS. Sin esos dos archivos, el certificado de casa sigue en servicio.

El televisor (LG, Samsung) usa el puerto **8766** sin certificado. No es la dirección del sitio.

## Primer uso

1. Conecte el disco.
2. **Ajustes**: carpeta de las fotos, luego **Guardar**.
3. Clasifique antes de indexar. Sueltas o ya por año: `classer-lieux`. Árbol dispar (DCIM): `classer-annee-mois`, luego `classer-lieux`. Opción 1 = simular, 2 = escribir. Linux: `.venv/bin/python tools/sort_annee_mois.py ORIGEN DESTINO`, luego `.venv/bin/python tools/sort_lieux.py -d DESTINO`, con `--apply` para escribir.
4. **Indexar**.

Las carpetas del disco se llaman `Annee 2024` y `Juin 2024`.

## Actualización

Cierre el sitio. Descomprima el zip nuevo sobre la misma carpeta. No borre GaleriePhotos ni `~/.config/galerie-photos`. No vuelva a copiar las fotos. Luego `reparer-installation.bat`, `reparer-installation-mac.command` o `bash start-linux.sh`. Véase [MISE-A-JOUR-es.md](MISE-A-JOUR-es.md).

## Si la página no se abre

- Python: python.org, casilla PATH, vuelva a lanzar.
- Cierre la ventana antigua y abra `https://127.0.0.1:8765`.
- `http://` no responde: el sitio es solo HTTPS.
- Fotos: disco conectado, letra correcta (`lister-disques.bat`).
