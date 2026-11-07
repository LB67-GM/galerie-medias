"""Albums nommés : listes de photos, sans copier les fichiers."""

from __future__ import annotations

from datetime import datetime, timezone


FAVORITES_ALBUM = "Favoris"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_albums(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT a.id, a.name, a.created_at,
               COUNT(m.id) AS count
        FROM albums a
        LEFT JOIN album_media am ON am.album_id = a.id
        LEFT JOIN media m ON m.id = am.media_id AND m.present = 1
        GROUP BY a.id
        ORDER BY a.name COLLATE NOCASE
        """
    ).fetchall()
    out = []
    for row in rows:
        cover = conn.execute(
            """
            SELECT am.media_id FROM album_media am
            JOIN media m ON m.id = am.media_id AND m.present = 1
            WHERE am.album_id=?
            ORDER BY am.added_at DESC, am.media_id DESC
            LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        out.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "created_at": row["created_at"],
                "count": int(row["count"] or 0),
                "cover_id": int(cover["media_id"]) if cover else None,
            }
        )
    return out


def create_album(conn, name: str) -> dict:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("nom vide")
    existing = conn.execute(
        "SELECT id FROM albums WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing:
        raise ValueError("un album porte déjà ce nom")
    cur = conn.execute(
        "INSERT INTO albums (name, created_at) VALUES (?, ?)",
        (name, now_iso()),
    )
    conn.commit()
    return {"id": int(cur.lastrowid), "name": name, "count": 0, "cover_id": None}


def ensure_favorites_album(conn) -> dict:
    """L’ancien filtre Favoris devient un album, visible dans le menu Album."""
    row = conn.execute(
        "SELECT id FROM albums WHERE name = ? COLLATE NOCASE",
        (FAVORITES_ALBUM,),
    ).fetchone()
    if row:
        album_id = int(row["id"])
    else:
        created = create_album(conn, FAVORITES_ALBUM)
        album_id = int(created["id"])
    fav_ids = [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM media WHERE present=1 AND favorite=1"
        ).fetchall()
    ]
    added = 0
    if fav_ids:
        added = int(add_to_album(conn, album_id, fav_ids).get("added") or 0)
    return {"id": album_id, "name": FAVORITES_ALBUM, "migrated": added}


def delete_album(conn, album_id: int) -> dict:
    row = conn.execute("SELECT id FROM albums WHERE id=?", (album_id,)).fetchone()
    if row is None:
        raise ValueError("album introuvable")
    conn.execute("DELETE FROM albums WHERE id=?", (album_id,))
    conn.commit()
    return {"deleted": True, "id": album_id}


def media_album_map(conn, media_ids: list[int]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {int(i): [] for i in media_ids}
    if not media_ids:
        return out
    qmarks = ",".join("?" * len(media_ids))
    rows = conn.execute(
        f"""
        SELECT media_id, album_id FROM album_media
        WHERE media_id IN ({qmarks})
        ORDER BY album_id
        """,
        media_ids,
    ).fetchall()
    for row in rows:
        out[int(row["media_id"])].append(int(row["album_id"]))
    return out


def assign_media_albums(
    conn,
    media_ids: list[int],
    album_ids: list[int],
    *,
    create: str = "",
    replace: bool = False,
) -> dict:
    """Ajoute des photos à un ou plusieurs albums. `replace` : une photo, liste exacte."""
    media_ids = [int(x) for x in media_ids]
    wanted: list[int] = []
    seen: set[int] = set()
    for aid in album_ids:
        aid = int(aid)
        if aid not in seen:
            seen.add(aid)
            wanted.append(aid)
    created = None
    name = " ".join((create or "").split())
    if name:
        created = create_album(conn, name)
        if created["id"] not in seen:
            wanted.append(int(created["id"]))
            seen.add(int(created["id"]))
    for aid in wanted:
        if conn.execute("SELECT id FROM albums WHERE id=?", (aid,)).fetchone() is None:
            raise ValueError("album introuvable")
    if replace and len(media_ids) != 1:
        raise ValueError("une seule photo à la fois")
    if not wanted:
        if not replace:
            raise ValueError("Choisissez un album ou saisissez un nom.")
        current = conn.execute(
            "SELECT 1 FROM album_media WHERE media_id=? LIMIT 1",
            (media_ids[0],),
        ).fetchone()
        if current is None:
            raise ValueError("Choisissez un album ou saisissez un nom.")

    stamp = now_iso()
    added = 0
    removed = 0
    present_ids: list[int] = []
    for media_id in media_ids:
        media = conn.execute(
            "SELECT id FROM media WHERE id=? AND present=1",
            (media_id,),
        ).fetchone()
        if media is None:
            continue
        present_ids.append(media_id)
        current = {
            int(r["album_id"])
            for r in conn.execute(
                "SELECT album_id FROM album_media WHERE media_id=?",
                (media_id,),
            )
        }
        target = set(wanted) if replace else current | set(wanted)
        for aid in target - current:
            conn.execute(
                "INSERT INTO album_media (album_id, media_id, added_at) VALUES (?, ?, ?)",
                (aid, media_id, stamp),
            )
            added += 1
        if replace:
            for aid in current - target:
                conn.execute(
                    "DELETE FROM album_media WHERE album_id=? AND media_id=?",
                    (aid, media_id),
                )
                removed += 1
        if target:
            conn.execute("UPDATE media SET favorite=1 WHERE id=?", (media_id,))
        elif replace:
            conn.execute("UPDATE media SET favorite=0 WHERE id=?", (media_id,))
    conn.commit()
    return {
        "created": created,
        "album_ids": wanted,
        "added": added,
        "removed": removed,
        "favorite": bool(wanted) if replace else True,
        "ids": present_ids,
    }


def add_to_album(conn, album_id: int, ids: list[int]) -> dict:
    row = conn.execute("SELECT id FROM albums WHERE id=?", (album_id,)).fetchone()
    if row is None:
        raise ValueError("album introuvable")
    stamp = now_iso()
    added = 0
    for media_id in ids:
        media = conn.execute(
            "SELECT id FROM media WHERE id=? AND present=1", (media_id,)
        ).fetchone()
        if media is None:
            continue
        before = conn.execute(
            "SELECT 1 FROM album_media WHERE album_id=? AND media_id=?",
            (album_id, media_id),
        ).fetchone()
        if before:
            continue
        conn.execute(
            "INSERT INTO album_media (album_id, media_id, added_at) VALUES (?, ?, ?)",
            (album_id, media_id, stamp),
        )
        added += 1
    conn.commit()
    return {"album_id": album_id, "added": added}


def remove_from_album(conn, album_id: int, ids: list[int]) -> dict:
    out = remove_media_albums(conn, ids, [album_id])
    out["album_id"] = int(album_id)
    return out


def remove_media_albums(conn, media_ids: list[int], album_ids: list[int]) -> dict:
    """Retire des photos d’un ou plusieurs albums (les fichiers restent)."""
    media_ids = [int(x) for x in media_ids]
    wanted: list[int] = []
    seen: set[int] = set()
    for aid in album_ids:
        aid = int(aid)
        if aid not in seen:
            seen.add(aid)
            wanted.append(aid)
    if not wanted:
        raise ValueError("Choisissez un ou plusieurs albums à retirer.")
    removed = 0
    for album_id in wanted:
        for media_id in media_ids:
            cur = conn.execute(
                "DELETE FROM album_media WHERE album_id=? AND media_id=?",
                (album_id, media_id),
            )
            removed += cur.rowcount or 0
    for media_id in media_ids:
        left = conn.execute(
            "SELECT 1 FROM album_media WHERE media_id=? LIMIT 1",
            (media_id,),
        ).fetchone()
        if left is None:
            conn.execute("UPDATE media SET favorite=0 WHERE id=?", (media_id,))
    conn.commit()
    return {"removed": removed, "ids": media_ids, "album_ids": wanted}


def set_favorite(conn, ids: list[int], favorite: bool) -> dict:
    flag = 1 if favorite else 0
    updated = 0
    for media_id in ids:
        cur = conn.execute(
            "UPDATE media SET favorite=? WHERE id=? AND present=1",
            (flag, media_id),
        )
        updated += cur.rowcount or 0
    conn.commit()
    return {"favorite": bool(flag), "updated": updated}
