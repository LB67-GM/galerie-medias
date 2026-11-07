# Galerie Médias 3.0 — actualizar un sitio ya instalado

Este archivo sirve si el sitio ya funciona. Primera instalación: [INSTALL-es.md](INSTALL-es.md).

Otros idiomas: [Français](MISE-A-JOUR-fr.md), [English](MISE-A-JOUR-en.md), [Deutsch](MISE-A-JOUR-de.md).

Después de la actualización, **Ajustes** muestra **Galerie Médias 3.0** (también arriba a la izquierda).

## Novedades de la 3.0

- Menús: **Fotos, Personas, Escenas, Duplicados, Mapa, Álbumes, Papelera, Ajustes**.
- Idioma (francés, inglés, español, alemán) y tema de color, arriba a la derecha. La elección se queda en este navegador.
- **Contraseña olvidada**: en Ajustes → Correo, indique el servidor y la dirección del sitio, luego el correo de cada cuenta. El enlace dura una hora.
- El tema **Ámbar** no cambia. Los otros: Tinta, Océano, Bosque, Papel, Día.
- El menú **?** abre la ayuda, en el idioma del sitio.
- El sitio solo escucha en **HTTPS**.

Las **fotos** y la **base** (rostros, álbumes, cuentas) no se mueven. Solo se sustituye el programa.

## Windows

1. Cierre la ventana negra. El sitio debe estar parado.
2. Descomprima el zip nuevo **sobre la misma carpeta** (a menudo `Documents\galerie-medias\`). Sustituya los archivos.
3. No toque `C:\Users\SUNOMBRE\AppData\Roaming\GaleriePhotos\`.
4. No vuelva a copiar las fotos.
5. Doble clic en `reparer-installation.bat` y espere al final.
6. Doble clic en `ouvrir-galerie.bat`.
7. En el navegador: **Ctrl+F5**.
8. Ajustes: **Galerie Médias 3.0**.

No hace falta volver a indexar todo. El televisor usa también el puerto **8766**: `autoriser-parefeu.bat` una vez, si no ve el sitio.

## macOS

1. Cierre la ventana de Terminal (`start-mac.command`).
2. Descomprima el zip nuevo **sobre la misma carpeta**.
3. No toque `Biblioteca/Application Support/GaleriePhotos`.
4. Doble clic en `reparer-installation-mac.command`, o vuelva a lanzar `start-mac.command`.
5. Recargue la página (Cmd+Shift+R).
6. Ajustes: **Galerie Médias 3.0**.

## Linux

1. Pare el sitio (cierre el terminal, o pare el servicio si lo hay).
2. Sustituya los archivos del programa en la misma carpeta. No borre `~/.config/galerie-photos/` ni `~/.cache/photo-library/`.
3. Vuelva a lanzar `bash start-linux.sh`. Si `REQUIS-es.md` cambió, el script actualiza los paquetes.
4. Recargue la página (Ctrl+F5).
5. Ajustes: **Galerie Médias 3.0**.

## No haga esto

| No… | Por qué |
|-----|---------|
| Instalar en una carpeta **nueva** y volver a indexar todo | Rostros, álbumes y cuentas están en GaleriePhotos, no en el zip |
| Borrar `AppData\Roaming\GaleriePhotos`, Application Support o `~/.config/galerie-photos` | El mismo motivo |
| Volver a copiar las fotos «por si acaso» | No hace falta |
| Abrir el zip sin descomprimirlo | El sitio no encontrará Python |
| Abrir dos ventanas a la vez | El puerto ya está ocupado |

## Si ya no arranca

1. Cierre todas las ventanas del sitio.
2. `reparer-installation.bat`, `reparer-installation-mac.command`, o `bash start-linux.sh`.
3. Vuelva a lanzar `ouvrir-galerie.bat`, `start-mac.command` o `start-linux.sh`.
4. El archivo `reparer-installation.log`, junto a los scripts, tiene el detalle.

Disco no encontrado: `lister-disques.bat`, luego corrija la ruta en Ajustes.
