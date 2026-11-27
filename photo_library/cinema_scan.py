"""Scan, requêtes SQLite, reprise de lecture et enrichissement du catalogue Cinéma."""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from photo_library.cinema_meta import (
    fetch_wikidata_metadata,
    normalize_categories,
    normalize_media_type,
    parse_local_metadata,
)
from photo_library.cinema_probe import make_cinema_poster, probe_media
from photo_library.jobs import emit

CINEMA_VIDEO_SUFFIXES = frozenset(
    {
        ".mp4",
        ".m4v",
        ".mkv",
        ".mov",
        ".avi",
        ".mpg",
        ".mpeg",
        ".mpe",
        ".wmv",
        ".webm",
        ".ts",
        ".m2ts",
        ".mts",
        ".flv",
        ".ogv",
        ".3gp",
        ".iso",
    }
)
CINEMA_SKIP_DIRS = frozenset(
    {
        "@recycle",
        "@eadir",
        "__macosx",
        ".trash",
        ".corbeille",
        "corbeille",
        ".git",
        ".venv",
    }
)

Progress = Callable[[int, int | None, str], None]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cinema_poster_path(cache: Path, item_id: int) -> Path:
    return cache / "cinema_thumbs" / f"{int(item_id)}.jpg"


def _should_skip_dir(name: str) -> bool:
    low = name.lower()
    return low.startswith(".") or low in CINEMA_SKIP_DIRS


def discover_cinema_entries(root: Path) -> list[tuple[str, Path, str]]:
    """Découvre fichiers vidéo, structures VIDEO_TS (DVD) et BDMV (Blu-ray) dans root.

    Retourne une liste de tuples (source_type, abs_path, relpath_posix).
    """
    if not root.is_dir():
        return []
    found: list[tuple[str, Path, str]] = []
    root_resolved = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        cur = Path(dirpath)
        low_dirs = {d.lower(): d for d in dirnames}
        # Structure DVD (dossier contenant VIDEO_TS/VIDEO_TS.IFO)
        if "video_ts" in low_dirs:
            vts = cur / low_dirs["video_ts"]
            if (vts / "VIDEO_TS.IFO").is_file() or any(
                p.suffix.lower() in {".ifo", ".vob"} for p in vts.iterdir()
            ):
                rel = cur.resolve().relative_to(root_resolved).as_posix()
                if rel != ".":
                    found.append(("dvd", cur, rel))
                    dirnames[:] = []
                    continue
        # Structure Blu-ray (dossier contenant BDMV/index.bdmv)
        if "bdmv" in low_dirs:
            bdmv = cur / low_dirs["bdmv"]
            if (bdmv / "index.bdmv").is_file() or (bdmv / "PLAYLIST").is_dir():
                rel = cur.resolve().relative_to(root_resolved).as_posix()
                if rel != ".":
                    found.append(("bluray", cur, rel))
                    dirnames[:] = []
                    continue

        dirnames[:] = sorted(d for d in dirnames if not _should_skip_dir(d))
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            fpath = cur / fname
            suffix = fpath.suffix.lower()
            if suffix not in CINEMA_VIDEO_SUFFIXES:
                continue
            rel = fpath.resolve().relative_to(root_resolved).as_posix()
            stype = "file"
            if suffix == ".iso":
                stype = "dvd"
            found.append((stype, fpath, rel))

    return found


def _set_item_categories(conn: sqlite3.Connection, item_id: int, categories: list[str]) -> None:
    conn.execute("DELETE FROM cinema_item_categories WHERE item_id=?", (item_id,))
    clean = normalize_categories(categories)
    if clean:
        conn.executemany(
            "INSERT OR IGNORE INTO cinema_item_categories (item_id, category) VALUES (?, ?)",
            [(item_id, c) for c in clean],
        )


def scan_cinema_library(
    conn: sqlite3.Connection,
    cinema_dir: Path,
    cache: Path,
    *,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Indexe le dossier Cinéma sans écraser les fiches verrouillées manuellement."""
    if not cinema_dir.is_dir():
        raise ValueError(f"Dossier Cinéma introuvable : {cinema_dir}")

    emit(progress, 0, None, "prog.cinemaScan", "Recherche des vidéos dans Cinéma…")
    entries = discover_cinema_entries(cinema_dir)
    total = len(entries)
    seen_relpaths: set[str] = set()
    added = 0
    updated = 0
    skipped = 0
    now = _now_iso()

    for idx, (source_type, fpath, relpath) in enumerate(entries, start=1):
        seen_relpaths.add(relpath)
        try:
            st = fpath.stat()
            size = int(st.st_size) if fpath.is_file() else 0
            mtime_ns = int(st.st_mtime_ns)
        except OSError:
            continue

        existing = conn.execute(
            "SELECT * FROM cinema_items WHERE relpath=?", (relpath,)
        ).fetchone()

        unchanged = (
            existing is not None
            and int(existing["size"] or 0) == size
            and int(existing["mtime_ns"] or 0) == mtime_ns
            and int(existing["present"] or 0) == 1
            and int(existing["poster_ok"] or 0) == 1
        )
        if unchanged:
            skipped += 1
            if idx % 20 == 0 or idx == total:
                emit(progress, idx, total, "prog.cinemaScan", f"Cinéma : {idx}/{total}")
            continue

        probe_res = probe_media(fpath) if source_type == "file" else None
        duration_s = probe_res.duration_s if probe_res and probe_res.readable else None
        width = probe_res.width if probe_res and probe_res.readable else None
        height = probe_res.height if probe_res and probe_res.readable else None
        tags = probe_res.tags if probe_res and probe_res.readable else {}

        parsed = parse_local_metadata(relpath, duration_s=duration_s, size=size, tags=tags)

        if existing is None:
            cur = conn.execute(
                """
                INSERT INTO cinema_items (
                    source_type, relpath, title, media_type, year, season, episode,
                    director, overview, wikidata_id, metadata_locked,
                    duration_s, width, height, size, mtime_ns, poster_ok, present, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', '', 0, ?, ?, ?, ?, ?, 0, 1, ?)
                """,
                (
                    source_type,
                    relpath,
                    parsed["title"],
                    parsed["media_type"],
                    parsed["year"],
                    parsed["season"],
                    parsed["episode"],
                    parsed["director"],
                    duration_s,
                    width,
                    height,
                    size,
                    mtime_ns,
                    now,
                ),
            )
            item_id = int(cur.lastrowid)
            _set_item_categories(conn, item_id, parsed["categories"])
            added += 1
        else:
            item_id = int(existing["id"])
            locked = bool(int(existing["metadata_locked"] or 0))
            if locked:
                conn.execute(
                    """
                    UPDATE cinema_items
                    SET source_type=?, duration_s=?, width=?, height=?,
                        size=?, mtime_ns=?, present=1, indexed_at=?
                    WHERE id=?
                    """,
                    (source_type, duration_s, width, height, size, mtime_ns, now, item_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE cinema_items
                    SET source_type=?, title=?, media_type=?, year=?, season=?, episode=?,
                        director=CASE WHEN director='' THEN ? ELSE director END,
                        duration_s=?, width=?, height=?, size=?, mtime_ns=?, present=1, indexed_at=?
                    WHERE id=?
                    """,
                    (
                        source_type,
                        parsed["title"],
                        parsed["media_type"],
                        parsed["year"],
                        parsed["season"],
                        parsed["episode"],
                        parsed["director"],
                        duration_s,
                        width,
                        height,
                        size,
                        mtime_ns,
                        now,
                        item_id,
                    ),
                )
                has_cats = conn.execute(
                    "SELECT 1 FROM cinema_item_categories WHERE item_id=? LIMIT 1",
                    (item_id,),
                ).fetchone()
                if not has_cats and parsed["categories"]:
                    _set_item_categories(conn, item_id, parsed["categories"])
            updated += 1

        poster_dest = cinema_poster_path(cache, item_id)
        poster_ok = 1 if make_cinema_poster(fpath, poster_dest, duration_s=duration_s) else 0
        conn.execute("UPDATE cinema_items SET poster_ok=? WHERE id=?", (poster_ok, item_id))

        if idx % 5 == 0 or idx == total:
            conn.commit()
            emit(progress, idx, total, "prog.cinemaScan", f"Cinéma : {idx}/{total} ({parsed['title']})")

    # Marquer les fichiers retirés comme absents
    existing_present = conn.execute(
        "SELECT id, relpath FROM cinema_items WHERE present=1"
    ).fetchall()
    removed = 0
    for row in existing_present:
        if row["relpath"] not in seen_relpaths:
            conn.execute("UPDATE cinema_items SET present=0 WHERE id=?", (int(row["id"]),))
            removed += 1

    conn.commit()
    emit(
        progress,
        total,
        total or 1,
        "prog.cinemaDone",
        f"Cinéma indexé : {total} vidéos ({added} ajoutées, {updated} mises à jour)",
    )
    return {
        "total": total,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "removed": removed,
    }


def enrich_cinema_library(
    conn: sqlite3.Connection,
    *,
    lang: str = "fr",
    only_missing: bool = True,
    limit: int | None = None,
    progress: Progress | None = None,
    fetcher=None,
) -> dict[str, Any]:
    """Enrichit les fiches Cinéma via Wikidata (CC0) sans écraser les fiches verrouillées."""
    sql = "SELECT * FROM cinema_items WHERE present=1 AND metadata_locked=0"
    if only_missing:
        sql += " AND (wikidata_id='' OR wikidata_id IS NULL)"
    sql += " ORDER BY id ASC"
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"

    rows = conn.execute(sql).fetchall()
    total = len(rows)
    enriched = 0
    missed = 0
    skipped_clips = 0

    for idx, row in enumerate(rows, start=1):
        item_id = int(row["id"])
        title = str(row["title"] or "")
        mtype = str(row["media_type"] or "movie")
        year = row["year"]
        emit(
            progress,
            idx - 1,
            total or 1,
            "prog.cinemaEnrich",
            f"Wikidata {idx}/{total} : {title}",
        )
        if mtype == "clip":
            skipped_clips += 1
            continue
        meta = fetch_wikidata_metadata(
            title,
            year=int(year) if year is not None else None,
            lang=lang,
            media_type=mtype,
            fetcher=fetcher,
        )
        if meta is None:
            missed += 1
        else:
            conn.execute(
                """
                UPDATE cinema_items
                SET title=?, media_type=?, year=?, director=?, overview=?, wikidata_id=?
                WHERE id=? AND metadata_locked=0
                """,
                (
                    meta["title"] or title,
                    normalize_media_type(meta["media_type"]),
                    meta["year"],
                    meta["director"] or str(row["director"] or ""),
                    meta["overview"] or str(row["overview"] or ""),
                    meta["wikidata_id"],
                    item_id,
                ),
            )
            if meta["categories"]:
                _set_item_categories(conn, item_id, meta["categories"])
            conn.commit()
            enriched += 1
        if fetcher is None and idx < total:
            time.sleep(0.25)

    emit(
        progress,
        total,
        total or 1,
        "prog.cinemaEnrichDone",
        f"Wikidata terminé : {enriched} fiches enrichies, {missed} sans correspondance",
    )
    return {
        "total": total,
        "enriched": enriched,
        "missed": missed,
        "skipped_clips": skipped_clips,
    }


def _attach_item_extras(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    user_key: str,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    ids = [int(r["id"]) for r in rows]
    ph = ",".join("?" for _ in ids)
    cat_map: dict[int, list[str]] = {i: [] for i in ids}
    for crow in conn.execute(
        f"SELECT item_id, category FROM cinema_item_categories WHERE item_id IN ({ph}) ORDER BY category",
        ids,
    ).fetchall():
        cat_map[int(crow["item_id"])].append(str(crow["category"]))

    keys = [f"item:{i}" for i in ids]
    kph = ",".join("?" for _ in keys)
    prog_map: dict[str, dict[str, Any]] = {}
    for prow in conn.execute(
        f"SELECT * FROM cinema_progress WHERE user_key=? AND item_key IN ({kph}) ORDER BY updated_at DESC",
        [user_key, *keys],
    ).fetchall():
        ikey = str(prow["item_key"])
        if ikey not in prog_map:
            prog_map[ikey] = {
                "title_index": int(prow["title_index"] or 0),
                "position_s": float(prow["position_s"] or 0),
                "duration_s": float(prow["duration_s"] or 0),
                "audio_idx": prow["audio_idx"],
                "subtitle_idx": prow["subtitle_idx"],
                "updated_at": prow["updated_at"],
            }

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        iid = int(d["id"])
        d["categories"] = cat_map.get(iid, [])
        d["metadata_locked"] = bool(int(d.get("metadata_locked") or 0))
        d["poster_ok"] = bool(int(d.get("poster_ok") or 0))
        d["progress"] = prog_map.get(f"item:{iid}")
        out.append(d)
    return out


def cinema_filters(conn: sqlite3.Connection) -> dict[str, Any]:
    types = [
        {"value": str(r["media_type"]), "count": int(r["c"])}
        for r in conn.execute(
            "SELECT media_type, COUNT(*) AS c FROM cinema_items WHERE present=1 "
            "GROUP BY media_type ORDER BY c DESC, media_type ASC"
        ).fetchall()
    ]
    years = [
        {"value": int(r["year"]), "count": int(r["c"])}
        for r in conn.execute(
            "SELECT year, COUNT(*) AS c FROM cinema_items WHERE present=1 AND year IS NOT NULL "
            "GROUP BY year ORDER BY year DESC"
        ).fetchall()
    ]
    categories = [
        {"value": str(r["category"]), "count": int(r["c"])}
        for r in conn.execute(
            """
            SELECT c.category, COUNT(*) AS c
            FROM cinema_item_categories c
            JOIN cinema_items i ON i.id = c.item_id
            WHERE i.present=1
            GROUP BY c.category
            ORDER BY c DESC, c.category ASC
            """
        ).fetchall()
    ]
    total = int(
        conn.execute("SELECT COUNT(*) FROM cinema_items WHERE present=1").fetchone()[0]
    )
    return {"total": total, "types": types, "years": years, "categories": categories}


def list_cinema_items(
    conn: sqlite3.Connection,
    *,
    media_type: str | None = None,
    category: str | None = None,
    year: int | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 80,
    user_key: str = "default",
) -> dict[str, Any]:
    where = ["i.present=1"]
    params: list[Any] = []
    if media_type:
        where.append("i.media_type=?")
        params.append(normalize_media_type(media_type))
    if year is not None:
        where.append("i.year=?")
        params.append(int(year))
    if category:
        where.append(
            "EXISTS (SELECT 1 FROM cinema_item_categories c WHERE c.item_id=i.id AND c.category=?)"
        )
        params.append(category.strip().lower())
    if q and q.strip():
        needle = f"%{q.strip()}%"
        where.append(
            "(i.title LIKE ? COLLATE NOCASE OR i.relpath LIKE ? COLLATE NOCASE "
            "OR i.director LIKE ? COLLATE NOCASE OR i.overview LIKE ? COLLATE NOCASE)"
        )
        params.extend([needle, needle, needle, needle])

    where_sql = " AND ".join(where)
    total = int(
        conn.execute(f"SELECT COUNT(*) FROM cinema_items i WHERE {where_sql}", params).fetchone()[0]
    )
    rows = conn.execute(
        f"""
        SELECT i.*
        FROM cinema_items i
        WHERE {where_sql}
        ORDER BY i.title COLLATE NOCASE ASC, i.year DESC, i.id ASC
        LIMIT ? OFFSET ?
        """,
        [*params, int(limit), int(offset)],
    ).fetchall()

    return {
        "total": total,
        "offset": int(offset),
        "limit": int(limit),
        "items": _attach_item_extras(conn, rows, user_key=user_key),
    }


def get_cinema_item(
    conn: sqlite3.Connection, item_id: int, *, user_key: str = "default"
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM cinema_items WHERE id=? AND present=1", (int(item_id),)
    ).fetchone()
    if row is None:
        return None
    return _attach_item_extras(conn, [row], user_key=user_key)[0]


def update_cinema_metadata(
    conn: sqlite3.Connection,
    item_id: int,
    *,
    title: str | None = None,
    media_type: str | None = None,
    year: int | None = None,
    clear_year: bool = False,
    director: str | None = None,
    overview: str | None = None,
    categories: list[str] | None = None,
    metadata_locked: bool = True,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM cinema_items WHERE id=? AND present=1", (int(item_id),)
    ).fetchone()
    if row is None:
        return None

    next_title = (title or "").strip() or str(row["title"])
    next_type = normalize_media_type(media_type) if media_type else str(row["media_type"])
    next_year = None if clear_year else (int(year) if year is not None else row["year"])
    next_dir = str(director).strip() if director is not None else str(row["director"] or "")
    next_over = str(overview).strip() if overview is not None else str(row["overview"] or "")

    conn.execute(
        """
        UPDATE cinema_items
        SET title=?, media_type=?, year=?, director=?, overview=?, metadata_locked=?
        WHERE id=?
        """,
        (
            next_title,
            next_type,
            next_year,
            next_dir,
            next_over,
            1 if metadata_locked else 0,
            int(item_id),
        ),
    )
    if categories is not None:
        _set_item_categories(conn, int(item_id), categories)
    conn.commit()
    return get_cinema_item(conn, int(item_id))


def save_cinema_progress(
    conn: sqlite3.Connection,
    *,
    user_key: str,
    item_key: str,
    position_s: float,
    duration_s: float = 0.0,
    title_index: int = 0,
    audio_idx: int | None = None,
    subtitle_idx: int | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    pos = max(0.0, float(position_s))
    dur = max(0.0, float(duration_s))
    # Si presque terminé (> 95% et durée connue > 2 min), remettre la position à 0 (vu)
    if dur > 120 and pos >= dur * 0.95:
        pos = 0.0
    conn.execute(
        """
        INSERT INTO cinema_progress (
            user_key, item_key, title_index, position_s, duration_s,
            audio_idx, subtitle_idx, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_key, item_key, title_index) DO UPDATE SET
            position_s=excluded.position_s,
            duration_s=excluded.duration_s,
            audio_idx=excluded.audio_idx,
            subtitle_idx=excluded.subtitle_idx,
            updated_at=excluded.updated_at
        """,
        (user_key, item_key, int(title_index), pos, dur, audio_idx, subtitle_idx, now),
    )
    conn.commit()
    return {
        "item_key": item_key,
        "title_index": int(title_index),
        "position_s": pos,
        "duration_s": dur,
        "updated_at": now,
    }


def continue_watching(
    conn: sqlite3.Connection, user_key: str, *, limit: int = 12
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.item_key, p.position_s, p.duration_s, p.updated_at, i.*
        FROM cinema_progress p
        JOIN cinema_items i ON ('item:' || i.id) = p.item_key
        WHERE p.user_key=? AND p.position_s >= 15 AND i.present=1
        ORDER BY p.updated_at DESC
        LIMIT ?
        """,
        (user_key, int(limit)),
    ).fetchall()
    return _attach_item_extras(conn, rows, user_key=user_key)


def clear_cinema_progress(
    conn: sqlite3.Connection,
    *,
    user_key: str,
    item_id: int | None = None,
) -> int:
    if item_id is not None:
        cur = conn.execute(
            "DELETE FROM cinema_progress WHERE user_key=? AND item_key=?",
            (user_key, f"item:{int(item_id)}"),
        )
    else:
        cur = conn.execute(
            "DELETE FROM cinema_progress WHERE user_key=?",
            (user_key,),
        )
    conn.commit()
    return int(cur.rowcount or 0)


CINEMA_CORBEILLE = ".corbeille"
CINEMA_KEEP_DAYS = 30


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        cand = dest.with_name(f"{stem}_{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def _in_root(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def cinema_trash_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM cinema_trash").fetchone()
    return int(row[0] if row else 0)


def trash_cinema_item(
    conn: sqlite3.Connection,
    cinema_dir: Path,
    item_id: int,
) -> dict[str, Any]:
    """Déplace un film/clip (ou dossier DVD/Blu-ray) vers `<cinema_dir>/.corbeille/` pour 30 jours."""
    root = cinema_dir.resolve()
    row = conn.execute(
        "SELECT * FROM cinema_items WHERE id=? AND present=1", (int(item_id),)
    ).fetchone()
    if row is None:
        raise ValueError("vidéo introuvable")
    if conn.execute("SELECT 1 FROM cinema_trash WHERE item_id=?", (int(item_id),)).fetchone():
        raise ValueError("déjà dans la corbeille")
    orig = str(row["relpath"] or "")
    if not orig or orig.startswith(CINEMA_CORBEILLE + "/") or orig == CINEMA_CORBEILLE:
        raise ValueError("chemin invalide")
    src = root / orig
    if src.exists() and not _in_root(root, src):
        raise ValueError("chemin hors dossier Cinéma")
    dest = _unique_dest(root / CINEMA_CORBEILLE / orig)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.move(str(src), str(dest))
    trash_rel = dest.relative_to(root).as_posix() if dest.exists() else f"{CINEMA_CORBEILLE}/{orig}"
    stamp = _now_iso()
    conn.execute(
        "INSERT INTO cinema_trash (item_id, orig_relpath, trash_relpath, trashed_at) VALUES (?, ?, ?, ?)",
        (int(item_id), orig, trash_rel, stamp),
    )
    conn.execute(
        "UPDATE cinema_items SET present=0, relpath=? WHERE id=?",
        (trash_rel, int(item_id)),
    )
    conn.execute("DELETE FROM cinema_progress WHERE item_key=?", (f"item:{int(item_id)}",))
    conn.commit()
    return {
        "id": int(item_id),
        "title": str(row["title"] or ""),
        "trashed_at": stamp,
        "keep_days": CINEMA_KEEP_DAYS,
    }


def list_cinema_trash(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        """
        SELECT t.item_id, t.orig_relpath, t.trash_relpath, t.trashed_at,
               i.title, i.media_type, i.year, i.duration_s, i.size, i.mtime_ns, i.poster_ok
        FROM cinema_trash t
        JOIN cinema_items i ON i.id = t.item_id
        ORDER BY t.trashed_at DESC, t.item_id DESC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            dt = datetime.fromisoformat(str(d["trashed_at"]))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            left = max(0, (dt + timedelta(days=CINEMA_KEEP_DAYS) - now).days)
        except ValueError:
            left = CINEMA_KEEP_DAYS
        d["id"] = int(d["item_id"])
        d["days_left"] = left
        out.append(d)
    return out


def restore_cinema_item(
    conn: sqlite3.Connection,
    cinema_dir: Path,
    item_id: int,
) -> dict[str, Any]:
    root = cinema_dir.resolve()
    row = conn.execute(
        """
        SELECT t.orig_relpath, t.trash_relpath, i.title
        FROM cinema_trash t JOIN cinema_items i ON i.id = t.item_id
        WHERE t.item_id=?
        """,
        (int(item_id),),
    ).fetchone()
    if row is None:
        raise ValueError("introuvable dans la corbeille Cinéma")
    src = root / str(row["trash_relpath"])
    dest = _unique_dest(root / str(row["orig_relpath"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        if not _in_root(root, src):
            raise ValueError("chemin hors dossier Cinéma")
        shutil.move(str(src), str(dest))
    new_rel = dest.relative_to(root).as_posix() if dest.exists() else str(row["orig_relpath"])
    conn.execute(
        "UPDATE cinema_items SET present=1, relpath=? WHERE id=?",
        (new_rel, int(item_id)),
    )
    conn.execute("DELETE FROM cinema_trash WHERE item_id=?", (int(item_id),))
    conn.commit()
    return {"id": int(item_id), "title": str(row["title"] or ""), "restored": True}


def purge_cinema_item(
    conn: sqlite3.Connection,
    cinema_dir: Path,
    cache: Path,
    item_id: int,
) -> dict[str, Any]:
    root = cinema_dir.resolve()
    row = conn.execute(
        """
        SELECT t.trash_relpath, i.title
        FROM cinema_trash t JOIN cinema_items i ON i.id = t.item_id
        WHERE t.item_id=?
        """,
        (int(item_id),),
    ).fetchone()
    if row is None:
        raise ValueError("introuvable dans la corbeille Cinéma")
    src = root / str(row["trash_relpath"])
    if src.exists():
        if not _in_root(root, src):
            raise ValueError("chemin hors dossier Cinéma")
        if src.is_dir():
            shutil.rmtree(src)
        else:
            src.unlink(missing_ok=True)
    cinema_poster_path(cache, int(item_id)).unlink(missing_ok=True)
    conn.execute("DELETE FROM cinema_progress WHERE item_key=?", (f"item:{int(item_id)}",))
    conn.execute("DELETE FROM cinema_trash WHERE item_id=?", (int(item_id),))
    conn.execute("DELETE FROM cinema_items WHERE id=?", (int(item_id),))
    conn.commit()
    return {"id": int(item_id), "title": str(row["title"] or ""), "purged": True}
