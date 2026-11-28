# Galerie Médias 4.1 — actualizar un sitio ya instalado

Este archivo sirve si el sitio ya funciona. Primera instalación: [INSTALL-es.md](INSTALL-es.md).

Otros idiomas: [Français](MISE-A-JOUR-fr.md), [English](MISE-A-JOUR-en.md), [Deutsch](MISE-A-JOUR-de.md).

Después de la actualización, **Ajustes** muestra **Galerie Médias 4.1** (también arriba a la izquierda).

## Novedades de la 4.1

- Botón **TV** de una película (Cine): el mensaje indica que la primera conversión puede tardar **de 4 a 5 minutos**. El archivo preparado se conserva: la misma película empieza después enseguida.
- Esta conversión hacia el televisor es más rápida que en la 4.0 (codificación H.264 720p acelerada). Un vídeo corto de la galería Fotos conserva el mensaje de alrededor de un minuto.
- La reproducción de una película en el navegador (HLS) sigue empezando en pocos segundos.
- No hay que reindexar. Fotos, cuentas y ajustes no se mueven.

## Novedades de la 4.0

- Nueva pestaña **Cine** (para cuentas de administrador y de **lectura**): reproductor de vídeo de código abierto integrado con transmisión **HLS en directo** (`hls.js`), pistas de audio, subtítulos, capítulos, calidad y **Seguir viendo**.
- Formatos compatibles en Cine: archivos de vídeo (`.mp4`, `.m4v`, `.mkv`, `.avi`, `.mpg`, `.mov`…), carpetas/imágenes **DVD** (`VIDEO_TS`, `.iso`), **Blu-ray** (`BDMV`, `.iso`) y **unidad óptica física** opcional (deje vacío en un servidor sin lector).
- Filtros por **Tipo** (Película, Serie, Videoclip, Documental), **Categoría** y **Año**, con enriquecimiento bajo demanda desde **Wikidata / Wikipedia** (datos abiertos CC0, sin clave API) y edición manual bloqueable.
- Botón **TV (DLNA)** integrado en el reproductor de Cine (puerto `8766` en la red local).
- Migración automática de SQLite y ajustes: en **Ajustes → Cine**, indique su carpeta de vídeos (p. ej. `/mnt/cinema`), guarde y pulse **Indexar Cine**.
- Dos indexaciones independientes: **Indexar Fotos** (barra superior, para la biblioteca de Fotos) e **Indexar Cine** (pestaña Cine o Ajustes → Cine, para películas/series/clips). Las películas y clips pueden enviarse a la **Papelera** (30 días, restaurables o eliminables definitivamente).
- Menús: **Fotos, Cine, Personas, Escenas, Duplicados, Mapa, Álbumes, Papelera, Ajustes**.
- Idioma (francés, inglés, español, alemán) y tema de color, arriba a la derecha. La elección se queda en este navegador.
- **Contraseña olvidada**: en Ajustes → Correo, indique el servidor y la dirección del sitio, luego el correo de cada cuenta. El enlace dura una hora.
- El tema **Ámbar** no cambia. Los otros: Tinta, Océano, Bosque, Papel, Día.
- El menú **?** abre la ayuda, en el idioma del sitio.
- El sitio solo escucha en **HTTPS**.

Las **fotos** y la **base** (rostros, álbumes, cuentas) no se mueven. Solo se sustituye el programa.

## Pasar de 3.0 a 4.0: migración automática y activación de Cine

- **Automático en el primer arranque de la 4.0**: sus fotos, rostros, escenas, álbumes, cuentas, ajustes (`config.json`) y certificados HTTPS permanecen intactos. SQLite crea automáticamente las nuevas tablas de **Cine** (catálogo, categorías, reanudación y papelera de 30 días). No se requiere ningún paquete Python adicional y **no hace falta volver a indexar las fotos**.
- **Si aún no usa Cine**: no necesita cambiar nada; la galería de Fotos sigue funcionando igual que en la 3.0.
- **Para activar la pestaña Cine después de actualizar**:
  1. Abra **Ajustes → Cine**.
  2. Indique la **Carpeta Cine** con sus películas, series, videoclips o carpetas DVD/Blu-ray (p. ej. `/mnt/cinema` o `D:\Videos\Cinema`).
  3. *(Opcional)* Indique su **Unidad óptica física** nativa (p. ej. `/dev/sr0`, `/Volumes/...` o `D:\`). Déjelo vacío en un equipo o servidor sin lector óptico.
  4. Pulse **Guardar** y luego **Indexar Cine** (independiente de **Indexar Fotos** en la barra superior).
  5. *(Opcional)* Pulse **Enriquecer (Wikidata)** para completar categorías, año, director y resumen automáticamente (datos abiertos CC0, sin clave API).

## Windows

1. Cierre la ventana negra. El sitio debe estar parado.
2. Descomprima el zip nuevo **sobre la misma carpeta** (a menudo `Documents\galerie-medias\`). Sustituya los archivos.
3. No toque `C:\Users\SUNOMBRE\AppData\Roaming\GaleriePhotos\`.
4. No vuelva a copiar las fotos.
5. Doble clic en `reparer-installation.bat` y espere al final.
6. Doble clic en `ouvrir-galerie.bat`.
7. En el navegador: **Ctrl+F5**.
8. Ajustes: **Galerie Médias 4.1**.

No hace falta volver a indexar todo. El televisor usa también el puerto **8766**: `autoriser-parefeu.bat` una vez, si no ve el sitio.

## macOS

1. Cierre la ventana de Terminal (`start-mac.command`).
2. Descomprima el zip nuevo **sobre la misma carpeta**.
3. No toque `Biblioteca/Application Support/GaleriePhotos`.
4. Doble clic en `reparer-installation-mac.command`, o vuelva a lanzar `start-mac.command`.
5. Recargue la página (Cmd+Shift+R).
6. Ajustes: **Galerie Médias 4.1**.

## Linux

1. Pare el sitio (cierre el terminal, o ejecute `systemctl --user stop photo-library.service` si usa un servicio systemd).
2. Sustituya los archivos del programa en la misma carpeta. No borre `~/.config/galerie-photos/` ni `~/.cache/photo-library/`.
3. Vuelva a lanzar `bash start-linux.sh` (o `systemctl --user start photo-library.service`). Si `REQUIS-es.md` cambió, `start-linux.sh` actualiza los paquetes.
4. Recargue la página (**Ctrl+F5**).
5. Ajustes: **Galerie Médias 4.1**. *(Opcional: monte su carpeta de vídeos, por ejemplo `/mnt/cinema`, y configúrela en **Ajustes → Cine**.)*

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
