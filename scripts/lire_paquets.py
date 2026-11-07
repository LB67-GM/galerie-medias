#!/usr/bin/env python3
"""Lit la liste de paquets commune aux quatre fichiers REQUIS."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("fr", "en", "es", "de")


def block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    found = re.search(r"```requirements\n(.*?)```", text, re.S)
    if not found:
        raise SystemExit(f"bloc requirements absent : {path.name}")
    lines = []
    for line in found.group(1).splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            lines.append(item)
    if not lines:
        raise SystemExit(f"liste vide : {path.name}")
    return "\n".join(lines) + "\n"


def packages() -> str:
    blocks = [block(ROOT / f"REQUIS-{lang}.md") for lang in LANGS]
    if len(set(blocks)) != 1:
        raise SystemExit("Les listes de paquets des quatre fichiers REQUIS diffèrent.")
    return blocks[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hash", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    data = packages()
    if args.write:
        args.write.write_text(data, encoding="utf-8")
    if args.hash:
        print(hashlib.sha256(data.encode("utf-8")).hexdigest())
    elif not args.write:
        sys.stdout.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
