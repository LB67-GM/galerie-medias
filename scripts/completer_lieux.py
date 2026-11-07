#!/usr/bin/env python3
"""Parcourt toutes les photos : index manquant + lieux vides.

Dry-run par défaut. Un lieu déjà nommé n’est pas modifié, sauf enveloppe
(Vacances/Voyage) remplacée par le sous-dossier (Portugal, Marseille…).

  python scripts/completer_lieux.py
  python scripts/completer_lieux.py --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from photo_library.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["completer-lieux", *sys.argv[1:]]))
