from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def venv_executable(name: str) -> Path | None:
    if sys.platform == "win32":
        bins = [ROOT / ".venv" / "Scripts" / f"{name}.exe"]
    else:
        bins = [ROOT / ".venv" / "bin" / name]
        bins.append(ROOT.parent / "icloud-archive" / ".venv" / "bin" / name)
    for cand in bins:
        if cand.is_file():
            return cand
    found = shutil.which(name)
    return Path(found) if found else None
