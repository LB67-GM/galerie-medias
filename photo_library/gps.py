"""GPS EXIF / ISO6709 : lu une fois à l’index, réutilisé par la carte."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from PIL import Image, ExifTags

from photo_library.config import IMAGE_SUFFIXES, VIDEO_SUFFIXES

ISO6709_RE = re.compile(
    rb"([+-]\d{2,3}(?:\.\d+)?)([+-]\d{3}(?:\.\d+)?)(?:[+-]\d+(?:\.\d+)?)?/"
)


def _ratio(value) -> float:
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        den = float(value.denominator or 1)
        return float(value.numerator) / den if den else 0.0
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        den = float(value[1] or 1)
        return float(value[0]) / den if den else 0.0
    return float(value)


def _dms_to_deg(values, ref: str) -> float | None:
    parts = list(values or [])
    if len(parts) < 3:
        return None
    deg = _ratio(parts[0]) + _ratio(parts[1]) / 60.0 + _ratio(parts[2]) / 3600.0
    if (ref or "N")[:1].upper() in {"S", "W"}:
        deg = -deg
    return deg


def _valid(lat: float, lon: float) -> bool:
    if abs(lat) < 1e-8 and abs(lon) < 1e-8:
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def gps_from_image(path: Path) -> tuple[float, float] | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            try:
                gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            except Exception:
                gps = None
            if not gps:
                return None
            lat_ref = str(gps.get(1) or "N")
            lon_ref = str(gps.get(3) or "E")
            lat = _dms_to_deg(gps.get(2), lat_ref)
            lon = _dms_to_deg(gps.get(4), lon_ref)
            if lat is None or lon is None or not _valid(lat, lon):
                return None
            return lat, lon
    except Exception:
        return None


def gps_from_iso6709_file(path: Path) -> tuple[float, float] | None:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size <= 512_000:
                data = fh.read()
            else:
                data = fh.read(256_000)
                fh.seek(max(0, size - 256_000))
                data += fh.read(256_000)
    except OSError:
        return None
    match = ISO6709_RE.search(data)
    if not match:
        return None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if not _valid(lat, lon):
        return None
    return lat, lon


def extract_gps(path: Path) -> tuple[float, float] | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return gps_from_image(path)
    if suffix in VIDEO_SUFFIXES:
        return gps_from_iso6709_file(path)
    return None


def gps_centroids(conn) -> dict[str, dict]:
    """Baricentre GPS des photos d’un lieu (déjà indexé), pas un géocodage de nom."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    if "gps_lat" not in cols:
        return {}
    out: dict[str, dict] = {}
    for row in conn.execute(
        """
        SELECT place, AVG(gps_lat) AS lat, AVG(gps_lon) AS lon, COUNT(*) AS n
        FROM media
        WHERE present=1 AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL
          AND place IS NOT NULL AND TRIM(place) != ''
        GROUP BY place
        """
    ):
        place = row["place"]
        if not place:
            continue
        out[place] = {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "cc": "",
            "n": int(row["n"] or 0),
        }
    return out


def import_sort_lieux_gps(conn, sort_db: Path | None = None) -> int:
    """Recopie lat/lon déjà lus par sort_lieux, sans relire les fichiers."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    if "gps_lat" not in cols:
        return 0
    path = sort_db or (Path.home() / ".cache" / "photo-sort-lieux" / "state.sqlite")
    if not path.is_file():
        return 0
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    src.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "files" not in tables:
            return 0
        by_rel: dict[str, tuple[float, float]] = {}
        for row in src.execute(
            "SELECT relpath, dest_relpath, lat, lon FROM files WHERE lat IS NOT NULL AND lon IS NOT NULL"
        ):
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (TypeError, ValueError):
                continue
            if not _valid(lat, lon):
                continue
            for key in (row["dest_relpath"], row["relpath"]):
                rel = str(key or "").replace("\\", "/").strip("/")
                if rel:
                    by_rel[rel] = (lat, lon)
    except sqlite3.Error:
        return 0
    finally:
        src.close()
    if not by_rel:
        return 0
    updated = 0
    for row in conn.execute(
        """
        SELECT id, relpath FROM media
        WHERE present=1 AND (gps_scanned IS NULL OR gps_scanned=0
              OR gps_lat IS NULL OR gps_lon IS NULL)
        """
    ):
        gps = by_rel.get(str(row["relpath"] or "").replace("\\", "/"))
        if not gps:
            continue
        conn.execute(
            "UPDATE media SET gps_lat=?, gps_lon=?, gps_scanned=1 WHERE id=?",
            (gps[0], gps[1], row["id"]),
        )
        updated += 1
    if updated:
        conn.commit()
    return updated


def scan_media_gps(
    conn,
    library: Path,
    *,
    year: int | None = None,
    limit: int | None = None,
    progress=None,
) -> dict:
    """Lit l’EXIF des fichiers pas encore scannés. Ne touche pas aux miniatures."""
    library = library.resolve()
    imported = import_sort_lieux_gps(conn)
    sql = """
        SELECT id, relpath FROM media
        WHERE present=1 AND (gps_scanned IS NULL OR gps_scanned=0)
    """
    params: list = []
    if year is not None:
        sql += " AND year=?"
        params.append(year)
    rows = list(conn.execute(sql, params))
    if limit is not None:
        rows = rows[: int(limit)]
    total = len(rows)
    found = 0
    missing = 0
    absent = 0
    for i, row in enumerate(rows, start=1):
        path = library / str(row["relpath"])
        if not path.is_file():
            conn.execute("UPDATE media SET gps_scanned=1 WHERE id=?", (row["id"],))
            absent += 1
            continue
        gps = extract_gps(path)
        if gps:
            conn.execute(
                "UPDATE media SET gps_lat=?, gps_lon=?, gps_scanned=1 WHERE id=?",
                (gps[0], gps[1], row["id"]),
            )
            found += 1
        else:
            conn.execute(
                "UPDATE media SET gps_lat=NULL, gps_lon=NULL, gps_scanned=1 WHERE id=?",
                (row["id"],),
            )
            missing += 1
        if i % 25 == 0:
            conn.commit()
            if progress:
                progress(i, total, row["relpath"])
    conn.commit()
    if progress:
        progress(total, total, "GPS terminé")
    return {
        "imported": imported,
        "scanned": total,
        "with_gps": found,
        "without_gps": missing,
        "missing_file": absent,
    }
