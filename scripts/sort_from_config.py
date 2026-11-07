#!/usr/bin/env python3
"""Ingestion triage + classement GPS selon les chemins des Réglages."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.user_config import load_settings


def sort_script() -> Path:
    local = ROOT / "tools" / "sort_lieux.py"
    if local.is_file():
        return local
    sibling = ROOT.parent / "photo-sort-lieux" / "sort_lieux.py"
    if sibling.is_file():
        return sibling
    sys.exit("sort_lieux.py introuvable (tools/ ou projects/photo-sort-lieux).")


def main() -> int:
    p = argparse.ArgumentParser(description="Classe la bibliothèque (année / lieu GPS).")
    p.add_argument("--apply", action="store_true", help="Écrire (sinon simulation)")
    p.add_argument("--triage", action="store_true", help="Ingérer d’abord le dossier de triage iCloud")
    args = p.parse_args()
    cfg = load_settings()
    dest = (cfg.get("library_dest") or cfg.get("library_src") or "").strip()
    src = (cfg.get("library_src") or "").strip()
    triage = (cfg.get("triage_dir") or "").strip()
    if not dest:
        sys.exit("Renseigne le nouvel emplacement dans Réglages.")
    py = sys.executable
    script = str(sort_script())
    dest_path = str(Path(dest).expanduser())
    code = 0
    if args.triage:
        if not triage:
            sys.exit("Renseigne le dossier de triage iCloud dans Réglages.")
        cmd = [py, script, "--library", dest_path, "--triage", "--triage-dir", str(Path(triage).expanduser())]
        if args.apply:
            cmd.append("--apply")
        print("Ingestion triage → bibliothèque…")
        code = subprocess.call(cmd)
        if code:
            return code
    cmd = [py, script, "--library", dest_path, "--all"]
    if src and Path(src).expanduser().resolve() != Path(dest).expanduser().resolve():
        print(f"Source actuelle (non copiée automatiquement) : {src}")
        print("Copie d’abord tes dossiers année vers le nouvel emplacement, ou utilise --triage.")
    if args.apply:
        cmd.append("--apply")
    print("Classement GPS des dossiers année…")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
