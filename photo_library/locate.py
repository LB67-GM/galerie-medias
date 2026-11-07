from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from photo_library.config import IMAGE_SUFFIXES
from photo_library.paths import parse_path_labels, skip_dir_name, year_from_folder

_year_files: dict[int, dict[str, Path]] = {}


def clear_locate_cache() -> None:
    _year_files.clear()


def _year_roots(library: Path, year: int, prefer: str | None) -> list[Path]:
    roots: list[Path] = []
    try:
        children = list(library.iterdir())
    except OSError:
        return []
    for child in children:
        if child.is_dir() and year_from_folder(child.name) == year:
            roots.append(child)
    if prefer:
        roots.sort(key=lambda p: (p.name != prefer, p.name.lower()))
    unique: list[Path] = []
    seen: set[int] = set()
    for root in roots:
        try:
            ino = root.stat().st_ino
        except OSError:
            continue
        if ino in seen:
            continue
        seen.add(ino)
        unique.append(root)
    return unique


def _file_map(library: Path, year: int, prefer: str | None) -> dict[str, Path]:
    if year in _year_files:
        return _year_files[year]
    mapping: dict[str, Path] = {}
    for root in _year_roots(library, year, prefer):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not skip_dir_name(d)]
            for name in filenames:
                if name.startswith(".") or name.startswith("._"):
                    continue
                if name in mapping:
                    continue
                mapping[name] = Path(dirpath) / name
    _year_files[year] = mapping
    return mapping


def _inside_library(library: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(library.resolve())
        return True
    except (OSError, ValueError):
        return False


def locate_library_file(library: Path, relpath: str) -> Path | None:
    raw = str(relpath or "").replace("\\", "/").strip()
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        return None
    direct = library / path
    try:
        if direct.is_file() and _inside_library(library, direct):
            return direct
    except OSError:
        pass
    parts = path.parts
    if not parts:
        return None
    year = year_from_folder(parts[0])
    if year is None:
        return None
    found = _file_map(library, year, parts[0]).get(path.name)
    if found is not None and found.is_file() and _inside_library(library, found):
        return found
    return None


def locate_still_sibling(library: Path, relpath: str) -> Path | None:
    stem = Path(relpath).stem
    parts = Path(relpath).parts
    year = year_from_folder(parts[0]) if parts else None
    if year is None:
        return None
    mapping = _file_map(library, year, parts[0] if parts else None)
    for suffix in (".HEIC", ".heic", ".JPG", ".jpg", ".JPEG", ".jpeg", ".PNG", ".png"):
        hit = mapping.get(stem + suffix)
        if (
            hit is not None
            and hit.is_file()
            and hit.suffix.lower() in IMAGE_SUFFIXES
            and _inside_library(library, hit)
        ):
            return hit
    for name, path in mapping.items():
        if (
            Path(name).stem == stem
            and path.suffix.lower() in IMAGE_SUFFIXES
            and path.is_file()
            and _inside_library(library, path)
        ):
            return path
    return None


def relpath_of(library: Path, path: Path) -> str:
    try:
        return str(path.relative_to(library))
    except ValueError:
        return str(path.resolve().relative_to(library.resolve()))


def maybe_fix_relpath(conn, library: Path, row, path: Path) -> None:
    new_rel = relpath_of(library, path)
    if new_rel == row["relpath"]:
        return
    year_val, place, moment = parse_path_labels(new_rel)
    locked = 0
    try:
        locked = int(row["place_locked"] or 0)
    except (KeyError, IndexError, TypeError):
        locked = 0
    try:
        if locked:
            conn.execute(
                "UPDATE media SET relpath=?, year=COALESCE(?, year), moment=? WHERE id=?",
                (new_rel, year_val, moment, int(row["id"])),
            )
        else:
            conn.execute(
                "UPDATE media SET relpath=?, year=COALESCE(?, year), place=?, moment=? WHERE id=?",
                (new_rel, year_val, place, moment, int(row["id"])),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        return
