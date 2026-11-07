#!/usr/bin/env python3
"""Diagnostic : Python (pas le Store) + présence de start-windows.bat."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        default="",
        help="Fichier (ajout en fin). Vide = stdout seulement.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sw = root / "start-windows.bat"
    exe = sys.executable.replace("\\", "/")
    store = "windowsapps" in exe.lower()
    lines = [
        f"cwd={os.getcwd()}",
        f"root={root}",
        f"start-windows.bat={'OUI' if sw.is_file() else 'NON'}",
        f"start-windows.bat_path={sw}",
        f"start-windows.bat_size={sw.stat().st_size if sw.is_file() else 0}",
        f"executable={sys.executable}",
        f"version={sys.version.replace(chr(10), ' ')}",
        f"prefix={sys.prefix}",
        f"store_alias={'OUI' if store else 'NON'}",
        f"venv_scripts={(root / '.venv' / 'Scripts' / 'python.exe').is_file()}",
        f"ok={'NON' if store or not sw.is_file() else 'OUI'}",
        "",
    ]
    text = "\n".join(lines)
    sys.stdout.write(text)
    if args.log:
        path = Path(args.log)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)
    if store or not sw.is_file():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
