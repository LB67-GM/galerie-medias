#!/usr/bin/env python3
"""Restaure une sauvegarde backup-AAAA-MM-JJ (SQLite, réglages, site).

Arrête le site pendant la copie si le service utilisateur systemd est actif,
puis le relance. Les miniatures ne sont pas dans la sauvegarde : relancer Indexer.
Python (.venv) n’est pas dans la sauvegarde : la liste des paquets est dans REQUIS-fr.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.backup import SITE_ROOT, restore_backup
from photo_library.config import DEFAULT_CACHE
from photo_library.user_config import portable_cache_dir

SERVICE = "photo-library.service"


def systemd_user(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def service_is_active() -> bool:
    try:
        proc = systemd_user("is-active", "--quiet", SERVICE)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restaure la base, les réglages et optionnellement le site (HTML/CSS/JS)."
    )
    parser.add_argument("folder", type=Path, help="Dossier backup-AAAA-MM-JJ")
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Ne pas écraser les réglages ni la clé de chiffrement",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help=f"Cache de destination (défaut : {DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Restaurer dans le cache du mode portable (GaleriePhotos)",
    )
    parser.add_argument(
        "--no-service",
        action="store_true",
        help="Ne pas arrêter/relancer photo-library.service",
    )
    parser.add_argument(
        "--no-site",
        action="store_true",
        help="Ne pas restaurer les pages HTML/CSS/JS",
    )
    parser.add_argument(
        "--site-dest",
        type=Path,
        default=None,
        help="Dossier où copier site/ (défaut : ce projet)",
    )
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if args.portable:
        cache = portable_cache_dir()
    else:
        cache = (args.cache or DEFAULT_CACHE).expanduser()

    stopped = False
    if not args.no_service and service_is_active():
        print(f"Arrêt de {SERVICE}…", flush=True)
        stop = systemd_user("stop", SERVICE)
        if stop.returncode != 0:
            print(stop.stderr or stop.stdout, file=sys.stderr)
            return 1
        stopped = True
    elif not args.no_service:
        print(
            "Le site n’est pas géré par systemd (ou est déjà arrêté). "
            "Ferme la galerie avant de restaurer si elle tourne encore.",
            flush=True,
        )

    try:
        result = restore_backup(
            folder,
            cache,
            restore_config=not args.no_config,
            restore_site_to=None if args.no_site else (args.site_dest or SITE_ROOT),
        )
    except Exception as exc:
        print(f"Restauration échouée : {exc}", file=sys.stderr)
        if stopped:
            systemd_user("start", SERVICE)
        return 1

    print("Restauré :", result, flush=True)
    print(
        "Les miniatures n’étaient pas dans la sauvegarde. Relance Indexer après le démarrage.",
        flush=True,
    )

    if stopped:
        print(f"Redémarrage de {SERVICE}…", flush=True)
        start = systemd_user("start", SERVICE)
        if start.returncode != 0:
            print(start.stderr or start.stdout, file=sys.stderr)
            return 1
        print("Site relancé.", flush=True)
    else:
        print(
            "Si le site tourne encore, arrête-le puis : "
            "systemctl --user restart photo-library.service",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
