"""Déplace des fichiers vers un dossier déjà présent dans la même année."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from photo_library.config import MEDIA_SUFFIXES
from photo_library.delete_media import path_in_library
from photo_library.locate import clear_locate_cache, locate_library_file
from photo_library.paths import (
    is_technical_folder,
    pair_key_of,
    parse_path_labels,
    skip_dir_name,
    year_from_folder,
)
from photo_library.places import place_from_relpath, user_alias_map

MAX_MOVE = 500


def _norm(relpath: str) -> str:
    return str(relpath or "").replace("\\", "/").strip("/")


def _year_dirname(relpath: str) -> str | None:
    parts = Path(_norm(relpath)).parts
    if parts and year_from_folder(parts[0]) is not None:
        return parts[0]
    return None


def _companion_stems(stem: str) -> set[str]:
    low = stem.lower()
    stems = {low}
    if low.endswith("_hevc"):
        stems.add(low[: -len("_hevc")])
    else:
        stems.add(low + "_hevc")
    return stems


def _unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _bundle(parent: Path, stem: str) -> list[Path]:
    stems = _companion_stems(stem)
    found: list[Path] = []
    try:
        children = list(parent.iterdir())
    except OSError:
        return found
    for child in children:
        if not child.is_file() or child.name.startswith("."):
            continue
        if child.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        if child.stem.lower() in stems:
            found.append(child)
    return found


def _row_for_rel(conn, relpath: str):
    norm = _norm(relpath)
    if not norm:
        return None
    return conn.execute(
        "SELECT * FROM media WHERE replace(relpath, char(92), '/') = ?",
        (norm,),
    ).fetchone()


def _selection_rows(conn, ids: list[int]):
    if not ids:
        raise ValueError("aucune photo")
    if len(ids) > MAX_MOVE:
        raise ValueError(f"Maximum {MAX_MOVE} photos à la fois.")
    rows = []
    year_dir = None
    for media_id in ids:
        row = conn.execute("SELECT * FROM media WHERE id=?", (int(media_id),)).fetchone()
        if row is None or not int(row["present"] or 0):
            raise ValueError("Une photo de la sélection est introuvable.")
        folder = _year_dirname(str(row["relpath"]))
        if folder is None:
            raise ValueError("Certaines photos ne sont pas dans un dossier Année.")
        if year_dir is None:
            year_dir = folder
        elif folder != year_dir:
            raise ValueError("Choisissez des photos de la même année.")
        rows.append(row)
    if year_dir is None:
        raise ValueError("aucune photo")
    return year_dir, rows


def list_destination_folders(library: Path, year_dirname: str) -> list[dict]:
    library = library.resolve()
    root = (library / year_dirname).resolve()
    if not path_in_library(library, root) or not root.is_dir():
        return []
    found: list[dict] = []
    for dirpath, dirnames, _names in os.walk(root):
        current = Path(dirpath).resolve()
        if not path_in_library(library, current):
            dirnames.clear()
            continue
        dirnames[:] = [
            name
            for name in dirnames
            if not skip_dir_name(name) and not is_technical_folder(name)
        ]
        rel = current.relative_to(library)
        if len(rel.parts) < 2:
            continue
        if any(skip_dir_name(part) or is_technical_folder(part) for part in rel.parts[1:]):
            continue
        found.append(
            {
                "path": rel.as_posix(),
                "label": "/".join(rel.parts[1:]),
            }
        )
    found.sort(key=lambda item: item["label"].casefold())
    return found


def move_targets(conn, library: Path, ids: list[int]) -> dict:
    year_dir, _rows = _selection_rows(conn, ids)
    year = year_from_folder(year_dir)
    return {
        "year": year,
        "year_dir": year_dir,
        "folders": list_destination_folders(library, year_dir),
    }


def _dest_dir(library: Path, year_dirname: str, dest_rel: str) -> Path:
    raw = _norm(dest_rel)
    parts = Path(raw).parts
    if not raw or not parts or ".." in parts or Path(raw).is_absolute():
        raise ValueError("dossier refusé")
    if parts[0] != year_dirname or len(parts) < 2:
        raise ValueError("Choisissez un dossier de la même année.")
    if any(skip_dir_name(part) or is_technical_folder(part) for part in parts[1:]):
        raise ValueError("dossier refusé")
    library = library.resolve()
    dest = (library / raw).resolve()
    if not path_in_library(library, dest) or not dest.is_dir():
        raise ValueError("Ce dossier n’existe pas.")
    if dest.relative_to(library).parts[0] != year_dirname:
        raise ValueError("Choisissez un dossier de la même année.")
    return dest


def _source_file(library: Path, relpath: str) -> Path | None:
    library = library.resolve()
    direct = (library / _norm(relpath)).resolve()
    if direct.is_file() and path_in_library(library, direct):
        return direct
    found = locate_library_file(library, relpath)
    if found is None:
        return None
    try:
        found = found.resolve()
    except OSError:
        return None
    if found.is_file() and path_in_library(library, found):
        return found
    return None


def _apply_new_path(conn, media_id: int, library: Path, target: Path, aliases: dict) -> None:
    library = library.resolve()
    new_rel = target.resolve().relative_to(library).as_posix()
    st = target.stat()
    year_val, _place, moment = parse_path_labels(new_rel)
    place = place_from_relpath(new_rel, aliases)
    conn.execute(
        """
        UPDATE media
        SET relpath=?, year=?, place=?, moment=?, pair_key=?, place_locked=0,
            size=?, mtime_ns=?
        WHERE id=?
        """,
        (
            new_rel,
            year_val,
            place,
            moment,
            pair_key_of(new_rel),
            int(st.st_size),
            int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
            int(media_id),
        ),
    )


def move_selected(conn, library: Path, ids: list[int], dest_rel: str) -> dict:
    library = library.resolve()
    year_dir, _rows = _selection_rows(conn, ids)
    dest = _dest_dir(library, year_dir, dest_rel)
    aliases = user_alias_map(conn)
    selected = {int(i) for i in ids}
    moved: list[int] = []
    moved_set: set[int] = set()
    skipped = 0
    renamed = 0
    errors: list[dict] = []
    handled_files: set[str] = set()

    for media_id in ids:
        media_id = int(media_id)
        if media_id in moved_set:
            continue
        row = conn.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
        if row is None:
            errors.append({"id": media_id, "error": "introuvable"})
            continue
        src = _source_file(library, str(row["relpath"]))
        if src is None:
            errors.append({"id": media_id, "error": "fichier absent"})
            continue
        if src.parent.resolve() == dest:
            skipped += 1
            continue
        key = str(src.resolve())
        if key in handled_files:
            continue
        bundle = _bundle(src.parent, src.stem)
        if not any(path.resolve() == src.resolve() for path in bundle):
            bundle.insert(0, src)
        for path in bundle:
            path_key = str(path.resolve())
            if path_key in handled_files:
                continue
            is_primary = path.resolve() == src.resolve()
            current_rel = path.resolve().relative_to(library).as_posix()
            row_hit = _row_for_rel(conn, current_rel)
            if row_hit is None and is_primary:
                row_hit = row
            target = _unique_path(dest / path.name)
            try:
                shutil.move(str(path), str(target))
            except OSError as exc:
                errors.append({"id": media_id, "error": str(exc)})
                break
            if target.name != path.name:
                renamed += 1
            handled_files.add(path_key)
            if row_hit is not None:
                _apply_new_path(conn, int(row_hit["id"]), library, target, aliases)
                hit_id = int(row_hit["id"])
                if hit_id in selected and hit_id not in moved_set:
                    moved_set.add(hit_id)
                    moved.append(hit_id)
        conn.commit()

    if moved:
        clear_locate_cache()
    label = "/".join(dest.relative_to(library).parts[1:])
    return {
        "moved": len(moved),
        "ids": moved,
        "skipped": skipped,
        "renamed": renamed,
        "errors": errors,
        "dest": dest.relative_to(library).as_posix(),
        "dest_label": label,
    }
