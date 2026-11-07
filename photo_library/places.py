"""Lieu affiché : SQLite seulement, les dossiers sur le disque ne bougent pas."""

from __future__ import annotations

from photo_library.geo import fold_name, resolve_folder_place
from photo_library.paths import (
    _extra_beyond_place,
    geographic_core,
    is_event_title,
    parent_dir,
    parse_path_labels,
)


def user_alias_map(conn) -> dict[str, str]:
    """Alias utilisateur : clé = dossier parent exact (plié), pas le nom de lieu seul."""
    out: dict[str, str] = {}
    try:
        rows = conn.execute("SELECT folder, place FROM place_aliases").fetchall()
    except Exception:
        return out
    for row in rows:
        folder = str(row["folder"] or "").replace("\\", "/").strip("/")
        place = row["place"] or ""
        if not folder or not place:
            continue
        out[fold_name(folder)] = place
    return out


def user_coord_map(conn) -> dict[str, dict]:
    """Coordonnées choisies dans Lieu : clé = nom de lieu plié."""
    out: dict[str, dict] = {}
    try:
        rows = conn.execute("SELECT place_key, place, lat, lon, cc FROM place_coords").fetchall()
    except Exception:
        return out
    for row in rows:
        key = str(row["place_key"] or "").strip()
        if not key:
            continue
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (TypeError, ValueError):
            continue
        out[key] = {
            "lat": lat,
            "lon": lon,
            "cc": str(row["cc"] or ""),
            "place": row["place"] or "",
        }
    return out


def upsert_place_coords(
    conn,
    place: str,
    lat: float,
    lon: float,
    cc: str = "",
) -> None:
    key = fold_name(place)
    if len(key) < 2:
        return
    conn.execute(
        """
        INSERT INTO place_coords (place_key, place, lat, lon, cc)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(place_key) DO UPDATE SET
            place=excluded.place,
            lat=excluded.lat,
            lon=excluded.lon,
            cc=excluded.cc
        """,
        (key, place, float(lat), float(lon), (cc or "").strip().upper()[:8]),
    )


def place_from_relpath(relpath: str, extra: dict[str, str] | None = None) -> str | None:
    """Lieu d’un fichier : alias du dossier parent exact, sinon géographie du chemin."""
    extra = extra or {}
    parent = parent_dir(relpath)
    if parent:
        folded = fold_name(parent)
        if folded in extra:
            return extra[folded]
    _year, place, _moment = parse_path_labels(relpath)
    if not place:
        return None
    resolved = resolve_folder_place(place)
    return resolved or place


def set_media_places(
    conn,
    ids: list[int],
    place: str,
    *,
    apply_folder: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    cc: str = "",
) -> dict:
    place_val = " ".join((place or "").split()) or None
    if not ids:
        raise ValueError("aucune photo")
    if (lat is None) != (lon is None):
        raise ValueError("latitude et longitude ensemble")
    if lat is not None and lon is not None:
        if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
            raise ValueError("coordonnées invalides")
    qmarks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id, relpath, place FROM media WHERE id IN ({qmarks}) AND present=1",
        [int(x) for x in ids],
    ).fetchall()
    if not rows:
        raise ValueError("média introuvable")
    target: list[int] = []
    dirs: set[str] = set()
    for row in rows:
        target.append(int(row["id"]))
        parent = parent_dir(row["relpath"])
        if parent:
            dirs.add(parent)
    if apply_folder and dirs and place_val:
        for folder in dirs:
            conn.execute(
                """
                INSERT INTO place_aliases (folder, place) VALUES (?, ?)
                ON CONFLICT(folder) DO UPDATE SET place=excluded.place
                """,
                (folder, place_val),
            )
        for row in conn.execute("SELECT id, relpath FROM media WHERE present=1").fetchall():
            if parent_dir(row["relpath"]) in dirs:
                target.append(int(row["id"]))
    seen: set[int] = set()
    unique: list[int] = []
    for media_id in target:
        if media_id not in seen:
            seen.add(media_id)
            unique.append(media_id)
    for media_id in unique:
        conn.execute(
            "UPDATE media SET place=?, place_locked=1 WHERE id=?",
            (place_val, media_id),
        )
    if place_val and lat is not None and lon is not None:
        upsert_place_coords(conn, place_val, float(lat), float(lon), cc)
    conn.commit()
    return {
        "updated": len(unique),
        "place": place_val,
        "apply_folder": bool(apply_folder and dirs and place_val),
        "folders": sorted(dirs),
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "cc": (cc or "").strip().upper()[:8] if lat is not None else "",
    }


def resolved_from_relpath(relpath: str, extra: dict[str, str] | None = None) -> str | None:
    return place_from_relpath(relpath, extra)


def complete_places_from_paths(
    conn,
    *,
    apply: bool = False,
    upgrade_generic: bool = True,
) -> dict:
    """Complète les lieux depuis le chemin. N’écrase jamais un lieu déjà nommé (sauf enveloppe)."""
    aliases = user_alias_map(conn)
    filled = 0
    upgraded = 0
    cleared = 0
    skipped = 0
    locked = 0
    no_guess = 0
    samples_filled: list[str] = []
    samples_upgraded: list[str] = []
    samples_cleared: list[str] = []
    by_place: dict[str, int] = {}
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    has_lock = "place_locked" in cols
    sql = "SELECT id, relpath, place" + (", place_locked" if has_lock else "") + " FROM media WHERE present=1"
    for row in conn.execute(sql):
        guessed = place_from_relpath(row["relpath"], aliases)
        current = (row["place"] or "").strip() or None
        if has_lock and int(row["place_locked"] or 0):
            locked += 1
            continue
        if current:
            core = geographic_core(current)
            pure_geo = bool(
                core
                and not _extra_beyond_place(current, core)
                and not is_event_title(current)
            )
            if pure_geo:
                skipped += 1
                continue
            if not upgrade_generic and guessed and fold_name(guessed) == fold_name(current):
                skipped += 1
                continue
            if guessed and fold_name(guessed) != fold_name(current):
                if apply:
                    conn.execute("UPDATE media SET place=? WHERE id=?", (guessed, row["id"]))
                upgraded += 1
                by_place[guessed] = by_place.get(guessed, 0) + 1
                if len(samples_upgraded) < 12:
                    samples_upgraded.append(f"{row['relpath']}: {current} → {guessed}")
                continue
            if not guessed:
                if apply:
                    conn.execute(
                        "UPDATE media SET place=NULL WHERE id=?", (row["id"],)
                    )
                cleared += 1
                if len(samples_cleared) < 12:
                    samples_cleared.append(f"{row['relpath']}: {current} → (vide)")
                continue
            skipped += 1
            continue
        if not guessed:
            no_guess += 1
            continue
        if apply:
            conn.execute("UPDATE media SET place=? WHERE id=?", (guessed, row["id"]))
        filled += 1
        by_place[guessed] = by_place.get(guessed, 0) + 1
        if len(samples_filled) < 12:
            samples_filled.append(f"{row['relpath']} → {guessed}")
    if apply and (filled or upgraded or cleared):
        conn.commit()
    top = sorted(by_place.items(), key=lambda item: (-item[1], item[0]))[:20]
    return {
        "filled": filled,
        "upgraded": upgraded,
        "cleared": cleared,
        "skipped": skipped,
        "locked": locked,
        "no_guess": no_guess,
        "samples_filled": samples_filled,
        "samples_upgraded": samples_upgraded,
        "samples_cleared": samples_cleared,
        "by_place": dict(top),
        "apply": apply,
    }


def complete_moments_from_paths(conn, *, apply: bool = False) -> dict:
    """Remplit le moment depuis le chemin (SQLite seulement, le disque ne bouge pas)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    if "moment" not in cols:
        return {"filled": 0, "unchanged": 0, "apply": apply}
    filled = 0
    unchanged = 0
    samples: list[str] = []
    for row in conn.execute("SELECT id, relpath, moment FROM media WHERE present=1"):
        _year, _place, moment = parse_path_labels(row["relpath"])
        current = (row["moment"] or "").strip() or None
        if current == moment:
            unchanged += 1
            continue
        if apply:
            conn.execute(
                "UPDATE media SET moment=? WHERE id=?", (moment, row["id"])
            )
        filled += 1
        if len(samples) < 12:
            samples.append(f"{row['relpath']} → {moment or '(aucun)'}")
    if apply and filled:
        conn.commit()
    return {
        "filled": filled,
        "unchanged": unchanged,
        "samples": samples,
        "apply": apply,
    }
