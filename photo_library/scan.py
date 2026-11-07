from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from photo_library.copies import fill_dhashes
from photo_library.jobs import emit
from photo_library.config import IMAGE_SUFFIXES, MEDIA_SUFFIXES, VIDEO_SUFFIXES
from photo_library.gps import extract_gps
from photo_library.metadata import taken_at_for
from photo_library.paths import (
    parse_path_labels,
    pair_key_of,
    skip_dir_name,
    year_dir,
    year_from_folder,
)
from photo_library.places import place_from_relpath, user_alias_map
from photo_library.thumbs import dhash_from_image, make_thumb, thumb_file

Progress = Callable[[int, int | None, str], None]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def kind_of(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "photo"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    return None


def iter_media(
    library: Path, year: int | None = None, limit: int | None = None
) -> list[Path]:
    roots: list[Path]
    if year is not None:
        found = year_dir(library, year)
        roots = [found] if found else []
    else:
        roots = [library]

    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not skip_dir_name(d)]
            dirnames.sort(key=str.lower)
            for name in sorted(filenames, key=str.lower):
                if name.startswith("._") or name.startswith("."):
                    continue
                path = Path(dirpath) / name
                if path.suffix.lower() in MEDIA_SUFFIXES:
                    files.append(path)
                    if limit is not None and len(files) >= limit:
                        return files
    return files


def upsert_media_file(
    conn,
    library: Path,
    cache: Path,
    path: Path,
    aliases: dict[str, str],
    *,
    year_hint: int | None = None,
) -> dict | None:
    try:
        rel = str(path.resolve().relative_to(library))
    except ValueError:
        return None
    st = path.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    kind = kind_of(path)
    if not kind:
        return None
    year_val, _folder, moment = parse_path_labels(rel)
    place = place_from_relpath(rel, aliases)
    pkey = pair_key_of(rel)
    if year_val is None and year_hint is not None:
        year_val = year_hint
    if year_val is None:
        year_val = year_from_folder(path.parent.name)

    row = conn.execute(
        """
        SELECT id, size, mtime_ns, thumb_ok, dhash, place_locked, gps_scanned
        FROM media WHERE relpath = ?
        """,
        (rel,),
    ).fetchone()
    changed = row is None or row["size"] != st.st_size or row["mtime_ns"] != mtime_ns
    taken = taken_at_for(path, kind) if changed else None
    locked = bool(row and int(row["place_locked"] or 0))
    thumb_fail = 0
    need_gps = row is None or changed or not int(row["gps_scanned"] or 0)
    gps = extract_gps(path) if need_gps else None

    if row is None:
        cur = conn.execute(
            """
            INSERT INTO media (
                relpath, size, mtime_ns, kind, year, place, taken_at,
                thumb_ok, present, face_scanned, indexed_at, pair_key, moment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 0, ?, ?, ?)
            """,
            (
                rel,
                st.st_size,
                mtime_ns,
                kind,
                year_val,
                place,
                taken,
                now_iso(),
                pkey,
                moment,
            ),
        )
        media_id = int(cur.lastrowid)
        thumb_ok = 0
    elif changed:
        if locked:
            conn.execute(
                """
                UPDATE media SET
                    size=?, mtime_ns=?, kind=?, year=?, taken_at=?,
                    thumb_ok=0, present=1, face_scanned=0, dhash=NULL, indexed_at=?,
                    pair_key=?, moment=?
                WHERE id=?
                """,
                (
                    st.st_size,
                    mtime_ns,
                    kind,
                    year_val,
                    taken,
                    now_iso(),
                    pkey,
                    moment,
                    row["id"],
                ),
            )
        else:
            conn.execute(
                """
                UPDATE media SET
                    size=?, mtime_ns=?, kind=?, year=?, place=?, taken_at=?,
                    thumb_ok=0, present=1, face_scanned=0, dhash=NULL, indexed_at=?,
                    pair_key=?, moment=?
                WHERE id=?
                """,
                (
                    st.st_size,
                    mtime_ns,
                    kind,
                    year_val,
                    place,
                    taken,
                    now_iso(),
                    pkey,
                    moment,
                    row["id"],
                ),
            )
        media_id = int(row["id"])
        thumb_ok = 0
        dest = thumb_file(cache, media_id)
        if dest.exists():
            dest.unlink()
    else:
        if locked:
            conn.execute(
                "UPDATE media SET present=1, year=?, pair_key=?, moment=? WHERE id=?",
                (year_val, pkey, moment, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE media SET present=1, year=?, place=?, pair_key=?, moment=? WHERE id=?",
                (year_val, place, pkey, moment, row["id"]),
            )
        media_id = int(row["id"])
        thumb_ok = int(row["thumb_ok"])

    if need_gps:
        if gps:
            conn.execute(
                "UPDATE media SET gps_lat=?, gps_lon=?, gps_scanned=1 WHERE id=?",
                (gps[0], gps[1], media_id),
            )
        else:
            conn.execute(
                "UPDATE media SET gps_lat=NULL, gps_lon=NULL, gps_scanned=1 WHERE id=?",
                (media_id,),
            )

    dest = thumb_file(cache, media_id)
    if thumb_ok and dest.is_file():
        if not (row and row["dhash"]):
            digest = dhash_from_image(dest)
            if digest:
                conn.execute("UPDATE media SET dhash=? WHERE id=?", (digest, media_id))
        thumb_ok_out = 1
    else:
        try:
            make_thumb(path, dest, kind)
            digest = dhash_from_image(dest)
            conn.execute(
                "UPDATE media SET thumb_ok=1, dhash=? WHERE id=?",
                (digest, media_id),
            )
            thumb_ok_out = 1
        except Exception:
            conn.execute("UPDATE media SET thumb_ok=0 WHERE id=?", (media_id,))
            thumb_ok_out = 0
            thumb_fail = 1
    return {
        "rel": rel,
        "thumb_ok": thumb_ok_out,
        "thumb_fail": thumb_fail,
    }


def index_library(
    conn,
    library: Path,
    cache: Path,
    year: int | None = None,
    limit: int | None = None,
    progress: Progress | None = None,
) -> dict:
    library = library.resolve()
    from photo_library.delete_media import purge_expired

    if progress:
        emit(progress, 0, None, "prog.trashOld", "Corbeille : plus de 30 jours")
    expired = purge_expired(conn, library, cache)
    files = iter_media(library, year=year, limit=limit)
    total = len(files)
    seen: set[str] = set()
    upserted = 0
    thumbs_ok = 0
    thumbs_fail = 0
    aliases = user_alias_map(conn)

    def report(done: int, msg: str) -> None:
        if progress:
            progress(done, total, msg)

    for i, path in enumerate(files, start=1):
        result = upsert_media_file(
            conn, library, cache, path, aliases, year_hint=year
        )
        if not result:
            continue
        seen.add(result["rel"])
        upserted += 1
        thumbs_ok += int(result["thumb_ok"])
        thumbs_fail += int(result["thumb_fail"])
        if result["thumb_fail"]:
            report(i, f"{result['rel']} : miniature impossible")
        if i % 25 == 0:
            conn.commit()
            report(i, result["rel"])

    conn.commit()
    if limit is None:
        if year is None:
            rows = conn.execute("SELECT id, relpath FROM media WHERE present=1")
        else:
            rows = conn.execute(
                "SELECT id, relpath FROM media WHERE present=1 AND year=?",
                (year,),
            )
        missing = [int(r["id"]) for r in rows if r["relpath"] not in seen]
        for media_id in missing:
            conn.execute("UPDATE media SET present=0 WHERE id=?", (media_id,))
        conn.commit()
    hashed = {"hashed": 0, "failed": 0, "total": 0}
    if year is None and limit is None:
        hashed = fill_dhashes(conn, cache, progress)
    report(total, f"Index terminé ({upserted} fichiers)")
    return {
        "files": upserted,
        "thumbs_ok": thumbs_ok,
        "thumbs_fail": thumbs_fail,
        "hashed": hashed.get("hashed", 0),
        "total": total,
        "trash_expired": expired.get("deleted", 0),
    }


def index_missing_files(
    conn,
    library: Path,
    cache: Path,
    *,
    apply: bool = False,
    progress: Progress | None = None,
) -> dict:
    """Indexe uniquement les photos/vidéos absentes de SQLite. Ne marque rien comme manquant."""
    library = library.resolve()
    existing = {str(row["relpath"]) for row in conn.execute("SELECT relpath FROM media")}
    missing_paths: list[Path] = []
    for path in iter_media(library):
        try:
            rel = str(path.resolve().relative_to(library))
        except ValueError:
            continue
        if rel not in existing:
            missing_paths.append(path)
    samples = []
    for path in missing_paths[:12]:
        try:
            samples.append(str(path.resolve().relative_to(library)))
        except ValueError:
            samples.append(str(path))
    if not apply:
        return {"missing": len(missing_paths), "indexed": 0, "samples_missing": samples}
    aliases = user_alias_map(conn)
    indexed = 0
    thumbs_ok = 0
    thumbs_fail = 0
    total = len(missing_paths)
    for i, path in enumerate(missing_paths, start=1):
        result = upsert_media_file(conn, library, cache, path, aliases)
        if not result:
            continue
        indexed += 1
        thumbs_ok += int(result["thumb_ok"])
        thumbs_fail += int(result["thumb_fail"])
        if progress and (i % 25 == 0 or i == total):
            progress(i, total, result["rel"])
        if i % 25 == 0:
            conn.commit()
    conn.commit()
    return {
        "missing": len(missing_paths),
        "indexed": indexed,
        "thumbs_ok": thumbs_ok,
        "thumbs_fail": thumbs_fail,
        "samples_missing": samples,
    }
