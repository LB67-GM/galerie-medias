#!/usr/bin/env python3
"""Construit l’archive Mac/Windows (sans cache, sans .venv, sans secrets)."""

from __future__ import annotations

import shutil
import stat
import tarfile
import zipfile
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from photo_library.version import APP_VERSION
DIST = ROOT / "dist"
NAME = "galerie-medias"
STAMP = date.today().isoformat()

INCLUDE_FILES = [
    "run.py",
    "LICENSE",
    "NOTICE",
    "lisezmoi.md",
    "readme.md",
    "INSTALL-fr.md",
    "INSTALL-en.md",
    "INSTALL-es.md",
    "INSTALL-de.md",
    "REQUIS-fr.md",
    "REQUIS-en.md",
    "REQUIS-es.md",
    "REQUIS-de.md",
    "MISE-A-JOUR-fr.md",
    "MISE-A-JOUR-en.md",
    "MISE-A-JOUR-es.md",
    "MISE-A-JOUR-de.md",
    "start-mac.command",
    "start-linux.sh",
    "start-windows.bat",
    "ouvrir-galerie.bat",
    "reparer-installation.bat",
    "reparer-installation-mac.command",
    "lister-disques.bat",
    "creer-raccourci-bureau.bat",
    "ouvrir-dossier-base.bat",
    "autoriser-parefeu.bat",
    "autoriser-parefeu-mac.command",
    "classer-annee-mois.bat",
    "classer-annee-mois-mac.command",
    "classer-lieux.bat",
    "classer-lieux-mac.command",
    "preparer-python.bat",
    "gerer-utilisateurs.bat",
    "gerer-utilisateurs-mac.command",
]
INCLUDE_DIRS = ["photo_library", "static", "scripts"]
SKIP_DIR_NAMES = {".venv", "__pycache__", "dist", ".git"}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo"}
SKIP_SCRIPT_NAMES = {
    "pack_distrib.py",
    "weekly_index.py",
    "weekly_backup.py",
}


def copy_tree(src: Path, dest: Path) -> None:
    for path in src.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix in SKIP_FILE_SUFFIXES:
            continue
        rel = path.relative_to(src)
        if src.name == "scripts" and path.name in SKIP_SCRIPT_NAMES:
            continue
        out = dest / rel
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)


def stage() -> Path:
    if DIST.exists():
        shutil.rmtree(DIST)
    staged = DIST / NAME
    staged.mkdir(parents=True)
    for name in INCLUDE_FILES:
        src = ROOT / name
        if not src.is_file():
            raise SystemExit(f"manquant : {src}")
        shutil.copy2(src, staged / name)
    for name in INCLUDE_DIRS:
        copy_tree(ROOT / name, staged / name)
    tools = staged / "tools"
    tools.mkdir()
    sort_src = ROOT.parent / "photo-sort-lieux" / "sort_lieux.py"
    if not sort_src.is_file():
        raise SystemExit(f"manquant : {sort_src}")
    shutil.copy2(sort_src, tools / "sort_lieux.py")
    mois_src = ROOT.parent / "photo-sort-lieux" / "sort_annee_mois.py"
    if not mois_src.is_file():
        raise SystemExit(f"manquant : {mois_src}")
    shutil.copy2(mois_src, tools / "sort_annee_mois.py")
    (staged / "VERSION.txt").write_text(f"{APP_VERSION}\n{STAMP}\n", encoding="utf-8")
    for mac_start in (
        "start-linux.sh",
        "start-mac.command",
        "reparer-installation-mac.command",
        "classer-annee-mois-mac.command",
        "classer-lieux-mac.command",
        "gerer-utilisateurs-mac.command",
    ):
        start = staged / mac_start
        if start.is_file():
            start.chmod(start.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (staged / "scripts" / "icloud_from_config.py").chmod(
        (staged / "scripts" / "icloud_from_config.py").stat().st_mode | stat.S_IXUSR
    )
    (staged / "scripts" / "sort_from_config.py").chmod(
        (staged / "scripts" / "sort_from_config.py").stat().st_mode | stat.S_IXUSR
    )
    restore = staged / "scripts" / "restore_backup.py"
    if restore.is_file():
        restore.chmod(restore.stat().st_mode | stat.S_IXUSR)
    completer = staged / "scripts" / "completer_lieux.py"
    if completer.is_file():
        completer.chmod(completer.stat().st_mode | stat.S_IXUSR)
    mois = staged / "tools" / "sort_annee_mois.py"
    if mois.is_file():
        mois.chmod(mois.stat().st_mode | stat.S_IXUSR)
    fw = staged / "scripts" / "allow_firewall_mac.sh"
    if fw.is_file():
        fw.chmod(fw.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    fwmac = staged / "autoriser-parefeu-mac.command"
    if fwmac.is_file():
        fwmac.chmod(fwmac.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return staged


def pack(staged: Path) -> tuple[Path, Path]:
    archive = f"{NAME}-{APP_VERSION}-{STAMP}"
    tar_path = DIST / f"{archive}.tar.gz"
    zip_path = DIST / f"{archive}.zip"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(staged, arcname=NAME)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in staged.rglob("*"):
            if path.is_file():
                zf.write(path, NAME + "/" + str(path.relative_to(staged)))
    return tar_path, zip_path


def main() -> int:
    staged = stage()
    tar_path, zip_path = pack(staged)
    print(tar_path)
    print(zip_path)
    print(f"contenu : {staged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
