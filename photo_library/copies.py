"""Regroupe les fichiers qui sont la même photo (autre nom / autre dossier)."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from photo_library.jobs import emit
from photo_library.thumbs import dhash_from_image, thumb_file

Progress = Callable[[int, int | None, str], None]

# Distance de Hamming max entre dHash (64 bits) pour « même image recompressée ».
NEAR = 6
_SHOT_RE = re.compile(
    r"(screen\s*shot|screenshot|capture\s*d|copie\s*d.?écran|copie\s*d.?ecran|"
    r"^copy[-_ ]|img[-_ ]?copy)",
    re.I,
)


def looks_like_screenshot(relpath: str) -> bool:
    name = Path(relpath or "").name
    return bool(_SHOT_RE.search(name))


def pick_keep(rows: list) -> int:
    """Fichier à garder : pas une capture, chemin le plus court."""
    ranked = []
    for row in rows:
        rel = row["relpath"] or ""
        ranked.append((1 if looks_like_screenshot(rel) else 0, len(rel), int(row["id"])))
    ranked.sort()
    return ranked[0][2]


def _find(parent: dict[int, int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict[int, int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def relpath_basename(relpath: str) -> str:
    return Path(str(relpath or "").replace("\\", "/")).name.lower()


def is_library_trash_relpath(relpath: str) -> bool:
    parts = Path(str(relpath or "").replace("\\", "/")).parts
    return any(p.lower() in {".corbeille", "corbeille"} for p in parts)


def pick_live_media(
    *,
    media_id: int,
    present: int,
    relpath: str,
    size: int,
    year: int | None,
    candidates: list[dict],
) -> int | None:
    """Choisit un media_id encore présent. Candidats : id, relpath, year, size."""
    if int(present or 0) == 1 and not is_library_trash_relpath(relpath):
        return int(media_id)
    name = relpath_basename(relpath)
    if not name or int(size or 0) <= 0:
        return None
    hits: list[dict] = []
    for row in candidates:
        rid = int(row["id"])
        if rid == int(media_id):
            continue
        rpath = str(row.get("relpath") or "")
        if is_library_trash_relpath(rpath):
            continue
        if relpath_basename(rpath) != name:
            continue
        rsize = int(row.get("size") or 0)
        if rsize and rsize != int(size):
            continue
        hits.append(row)
    if not hits:
        return None
    if year is not None:
        same = [r for r in hits if r.get("year") == year]
        if same:
            hits = same
    years = {r.get("year") for r in hits}
    if year is None and len(years) > 1:
        return None
    hits.sort(key=lambda r: (len(str(r.get("relpath") or "")), int(r["id"])))
    return int(hits[0]["id"])


def live_media_id_for_face(conn, row: dict) -> int | None:
    """media_id à ouvrir : inchangé si présent, sinon même nom+taille (même année)."""
    media_id = int(row["media_id"])
    present = int(row.get("present") or 0)
    relpath = str(row.get("relpath") or "")
    size = int(row.get("size") or 0)
    year = row.get("year")
    if present == 1 and not is_library_trash_relpath(relpath):
        return media_id
    if size <= 0:
        return None
    candidates = [
        dict(r)
        for r in conn.execute(
            """
            SELECT id, relpath, year, size FROM media
            WHERE present=1 AND size=? AND id!=?
            """,
            (size, media_id),
        ).fetchall()
    ]
    return pick_live_media(
        media_id=media_id,
        present=present,
        relpath=relpath,
        size=size,
        year=year if year is None else int(year),
        candidates=candidates,
    )


def unique_faces(rows: list[dict]) -> tuple[list[dict], int]:
    """Une entrée par photo distincte (copies masquées). `rows` déjà triés par score."""
    by_media: list[dict] = []
    seen_media: set[int] = set()
    hidden = 0
    for row in rows:
        mid = int(row["media_id"])
        if mid in seen_media:
            hidden += 1
            continue
        seen_media.add(mid)
        by_media.append(row)
    if len(by_media) <= 1:
        return by_media, hidden

    parent = {int(r["media_id"]): int(r["media_id"]) for r in by_media}
    by_st: dict[tuple[int, str], int] = {}
    hashed: list[tuple[int, int]] = []
    for row in by_media:
        mid = int(row["media_id"])
        size = int(row["size"] or 0)
        taken = row["taken_at"]
        if size > 0 and taken:
            key = (size, str(taken))
            prev = by_st.get(key)
            if prev is None:
                by_st[key] = mid
            else:
                _union(parent, prev, mid)
        dh = row.get("dhash")
        if dh:
            hashed.append((mid, int(dh, 16)))
    for i, (a, ha) in enumerate(hashed):
        for b, hb in hashed[i + 1 :]:
            if (ha ^ hb).bit_count() <= NEAR:
                _union(parent, a, b)

    seen_root: set[int] = set()
    out: list[dict] = []
    for row in by_media:
        root = _find(parent, int(row["media_id"]))
        if root in seen_root:
            hidden += 1
            continue
        seen_root.add(root)
        out.append(row)
    return out, hidden


def fill_dhashes(conn, cache: Path, progress: Progress | None = None) -> dict:
    rows = conn.execute(
        """
        SELECT id FROM media
        WHERE present=1 AND thumb_ok=1 AND (dhash IS NULL OR dhash='')
        """
    ).fetchall()
    total = len(rows)
    done = 0
    failed = 0

    def report(i: int, msg: str) -> None:
        if progress:
            progress(i, total, msg)

    for i, row in enumerate(rows, start=1):
        media_id = int(row["id"])
        path = thumb_file(cache, media_id)
        digest = dhash_from_image(path) if path.is_file() else None
        if digest:
            conn.execute("UPDATE media SET dhash=? WHERE id=?", (digest, media_id))
            done += 1
        else:
            failed += 1
        if i % 200 == 0:
            conn.commit()
            report(i, "empreintes visuelles")
    conn.commit()
    report(total, f"Empreintes : {done} calculées")
    return {"hashed": done, "failed": failed, "total": total}


def _copy_buckets(conn) -> list[list]:
    rows = conn.execute(
        """
        SELECT id, relpath, size, taken_at, dhash, kind, year, place, thumb_ok
        FROM media
        WHERE present=1 AND size > 0
        """
    ).fetchall()
    if not rows:
        return []

    parent = {int(r["id"]): int(r["id"]) for r in rows}
    by_st: dict[tuple[int, str], int] = {}
    by_hash: dict[str, int] = {}
    for row in rows:
        mid = int(row["id"])
        size = int(row["size"] or 0)
        taken = row["taken_at"]
        if size > 0 and taken:
            key = (size, str(taken))
            prev = by_st.get(key)
            if prev is None:
                by_st[key] = mid
            else:
                _union(parent, prev, mid)
        dh = row["dhash"]
        if dh:
            prev = by_hash.get(dh)
            if prev is None:
                by_hash[dh] = mid
            else:
                _union(parent, prev, mid)

    buckets: dict[int, list] = defaultdict(list)
    for row in rows:
        buckets[_find(parent, int(row["id"]))].append(row)
    big = [grp for grp in buckets.values() if len(grp) > 1]
    big.sort(key=lambda g: (-len(g), min((r["relpath"] or "") for r in g)))
    return big


def extra_copy_ids(conn) -> list[int]:
    """Fichiers en trop : tout sauf le fichier suggéré « garder » de chaque série."""
    ids: list[int] = []
    for grp in _copy_buckets(conn):
        keep_id = pick_keep(grp)
        for row in grp:
            mid = int(row["id"])
            if mid != keep_id:
                ids.append(mid)
    return ids


def trash_extra_copies(conn, library: Path, cache: Path, progress: Progress | None = None) -> dict:
    from photo_library.delete_media import KEEP_DAYS, trash_selected

    ids = extra_copy_ids(conn)
    total = len(ids)
    if progress:
        emit(progress, 0, total, "prog.extras", f"{total} fichier(s) en trop", n=total)
    if not ids:
        return {
            "trashed": 0,
            "extra_count": 0,
            "errors": [],
            "error_count": 0,
            "keep_days": KEEP_DAYS,
        }
    result = trash_selected(conn, library, cache, ids, progress=progress)
    errors = result.get("errors") or []
    if progress:
        if errors:
            emit(
                progress,
                result["trashed"],
                total,
                "prog.extrasDoneErr",
                f"{result['trashed']} envoyé(s) à la corbeille · {len(errors)} erreur(s)",
                n=result["trashed"],
                errors=len(errors),
            )
        else:
            emit(
                progress,
                result["trashed"],
                total,
                "prog.extrasDone",
                f"{result['trashed']} envoyé(s) à la corbeille",
                n=result["trashed"],
            )
    return {
        "trashed": result["trashed"],
        "extra_count": total,
        "errors": errors[:40],
        "error_count": len(errors),
        "keep_days": result["keep_days"],
    }


def copy_groups(conn, limit: int = 20, offset: int = 0) -> dict:
    big = _copy_buckets(conn)
    if not big:
        return {
            "groups": [],
            "group_count": 0,
            "file_count": 0,
            "extra_count": 0,
            "offset": offset,
            "limit": limit,
        }
    groups = []
    for grp in big[offset : offset + limit]:
        keep_id = pick_keep(grp)
        items = []
        for row in sorted(grp, key=lambda r: (int(r["id"]) != keep_id, (r["relpath"] or "").lower())):
            rel = row["relpath"] or ""
            items.append(
                {
                    "id": int(row["id"]),
                    "relpath": rel,
                    "name": Path(rel).name,
                    "size": int(row["size"] or 0),
                    "taken_at": row["taken_at"],
                    "kind": row["kind"],
                    "year": row["year"],
                    "place": row["place"],
                    "keep": int(row["id"]) == keep_id,
                    "screenshot": looks_like_screenshot(rel),
                }
            )
        groups.append({"count": len(items), "keep_id": keep_id, "items": items})
    extra = sum(max(0, len(g) - 1) for g in big)
    return {
        "groups": groups,
        "group_count": len(big),
        "file_count": sum(len(g) for g in big),
        "extra_count": extra,
        "offset": offset,
        "limit": limit,
    }
