#!/usr/bin/env python3
"""Télécharge iCloud vers le dossier de triage des réglages (mot de passe chiffré)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.user_config import load_settings
from photo_library.venv_bins import venv_executable


def main() -> int:
    p = argparse.ArgumentParser(description="Télécharge iCloud vers le triage configuré.")
    p.add_argument("--year", "-y", type=int, required=True)
    p.add_argument("--month", "-m", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    cfg = load_settings()
    dest = (cfg.get("triage_dir") or "").strip()
    user = (cfg.get("apple_id") or "").strip()
    password = cfg.get("apple_password") or ""
    if not dest or not user:
        sys.exit("Renseigne le dossier de triage et l’Apple ID dans Réglages, puis relance.")
    if not password:
        sys.exit("Aucun mot de passe enregistré. Saisis-le dans Réglages.")
    icloudpd = venv_executable("icloudpd")
    if icloudpd is None:
        sys.exit("icloudpd introuvable. Installe les dépendances (voir INSTALL.md).")
    dest_path = Path(dest).expanduser()
    dest_path.mkdir(parents=True, exist_ok=True)
    start = date(args.year, args.month or 1, 1)
    if args.month:
        end = date(args.year + (args.month == 12), 1 if args.month == 12 else args.month + 1, 1)
    else:
        end = date(args.year + 1, 1, 1)
    cmd = [
        str(icloudpd),
        "--username",
        user,
        "--password-provider",
        "parameter",
        "--password",
        password,
        "--mfa-provider",
        "webui",
        "--directory",
        str(dest_path),
        "--folder-structure",
        "{:%Y/%m}",
        "--skip-created-before",
        start.isoformat(),
        "--skip-created-after",
        end.isoformat(),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    print(f"Destination : {dest_path}")
    print("Si Apple demande un code : une petite page web s’ouvre pour le 2FA.")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
