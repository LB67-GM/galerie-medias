"""Pivoter / rogner une photo : l’original est copié dans `.corbeille/`, le fichier en place est remplacé."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from photo_library.config import JPEG_QUALITY
from photo_library.delete_media import CORBEILLE, _unique_path, path_in_library
from photo_library.paths import pair_key_of
from photo_library.thumbs import (
    dhash_from_image,
    ensure_heif,
    face_thumb_file,
    make_preview,
    make_thumb,
    preview_file,
    thumb_file,
)

EDITABLE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
    ".hif",
    ".tif",
    ".tiff",
    ".bmp",
    ".gif",
}

_JPEG_SUFFIXES = {".jpg", ".jpeg"}
_CW = {
    90: Image.Transpose.ROTATE_270,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clamp_crop(crop: dict | None) -> tuple[float, float, float, float] | None:
    if not crop:
        return None
    try:
        x = float(crop.get("x", 0))
        y = float(crop.get("y", 0))
        w = float(crop.get("w", 1))
        h = float(crop.get("h", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("recadrage invalide") from exc
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w))
    h = max(0.0, min(1.0 - y, h))
    if w < 0.02 or h < 0.02:
        raise ValueError("zone trop petite")
    if x <= 0.002 and y <= 0.002 and x + w >= 0.998 and y + h >= 0.998:
        return None
    return x, y, w, h


def _exif_bytes(src: Image.Image) -> bytes | None:
    try:
        exif = src.getexif()
    except Exception:
        return None
    if not exif:
        return None
    try:
        exif[0x0112] = 1
        return exif.tobytes()
    except Exception:
        return None


def _backup_original(library: Path, src: Path) -> Path:
    rel = src.resolve().relative_to(library.resolve())
    dest = _unique_path(library / CORBEILLE / rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _register_edit_backup(
    conn,
    library: Path,
    cache: Path,
    live_id: int,
    orig_rel: str,
    backup: Path,
    src_row,
) -> int:
    library = library.resolve()
    rel = str(backup.resolve().relative_to(library))
    st = backup.stat()
    cur = conn.execute(
        """
        INSERT INTO media (
            relpath, size, mtime_ns, kind, year, place, taken_at, width, height,
            thumb_ok, present, face_scanned, pair_key, place_locked,
            gps_lat, gps_lon, gps_scanned, dhash, moment
        ) VALUES (?, ?, ?, 'photo', ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rel,
            st.st_size,
            getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
            src_row["year"],
            src_row["place"],
            src_row["taken_at"],
            src_row["width"],
            src_row["height"],
            pair_key_of(orig_rel),
            int(src_row["place_locked"] or 0) if "place_locked" in src_row.keys() else 0,
            src_row["gps_lat"] if "gps_lat" in src_row.keys() else None,
            src_row["gps_lon"] if "gps_lon" in src_row.keys() else None,
            int(src_row["gps_scanned"] or 0) if "gps_scanned" in src_row.keys() else 0,
            src_row["dhash"] if "dhash" in src_row.keys() else None,
            src_row["moment"] if "moment" in src_row.keys() else None,
        ),
    )
    backup_id = int(cur.lastrowid)
    try:
        thumb = thumb_file(cache, backup_id)
        preview = preview_file(cache, backup_id)
        make_thumb(backup, thumb, "photo")
        make_preview(backup, preview, "photo")
        digest = dhash_from_image(thumb)
        conn.execute(
            "UPDATE media SET thumb_ok=1, dhash=? WHERE id=?",
            (digest, backup_id),
        )
    except Exception:
        pass
    conn.execute(
        """
        INSERT INTO trash (media_id, orig_relpath, trash_relpath, trashed_at, reason, restore_id)
        VALUES (?, ?, ?, ?, 'edit', ?)
        """,
        (backup_id, orig_rel, rel, _now_iso(), live_id),
    )
    return backup_id


def apply_photo_edit(
    conn,
    library: Path,
    cache: Path,
    media_id: int,
    *,
    rotate: int = 0,
    crop: dict | None = None,
) -> dict:
    library = library.resolve()
    rotate = int(rotate) % 360
    if rotate not in {0, 90, 180, 270}:
        raise ValueError("rotation : 0, 90, 180 ou 270")
    box = _clamp_crop(crop)
    if rotate == 0 and box is None:
        raise ValueError("choisissez une rotation ou un recadrage")

    row = conn.execute(
        "SELECT * FROM media WHERE id=? AND present=1", (media_id,)
    ).fetchone()
    if row is None:
        raise FileNotFoundError("photo introuvable")
    if row["kind"] != "photo":
        raise ValueError("uniquement les photos")

    src = (library / row["relpath"]).resolve()
    if not src.is_file() or not path_in_library(library, src):
        raise FileNotFoundError("fichier absent du NAS")
    suffix = src.suffix.lower()
    if suffix not in EDITABLE_SUFFIXES:
        raise ValueError("ce format ne peut pas être modifié ici")

    ensure_heif()
    with Image.open(src) as raw:
        exif = _exif_bytes(raw)
        img = ImageOps.exif_transpose(raw)
        if img.mode not in {"RGB", "L"}:
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")
        if rotate in _CW:
            img = img.transpose(_CW[rotate])
        if box is not None:
            x, y, w, h = box
            left = int(round(x * img.width))
            top = int(round(y * img.height))
            right = int(round((x + w) * img.width))
            bottom = int(round((y + h) * img.height))
            left = max(0, min(img.width - 1, left))
            top = max(0, min(img.height - 1, top))
            right = max(left + 1, min(img.width, right))
            bottom = max(top + 1, min(img.height, bottom))
            img = img.crop((left, top, right, bottom))
        edited = img.copy()

    dest = src if suffix in _JPEG_SUFFIXES else src.with_suffix(".jpg")
    if dest != src and dest.exists():
        raise FileExistsError(f"un fichier existe déjà : {dest.name}")

    orig_rel = row["relpath"]
    backup = _backup_original(library, src)
    tmp = dest.with_name(f".{dest.stem}.edit-{media_id}.jpg")
    save_kw: dict = {"quality": max(JPEG_QUALITY, 90), "optimize": True}
    if exif:
        save_kw["exif"] = exif
    try:
        edited.save(tmp, "JPEG", **save_kw)
        tmp.replace(dest)
        if dest != src:
            src.unlink(missing_ok=True)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    _register_edit_backup(conn, library, cache, media_id, orig_rel, backup, row)

    st = dest.stat()
    rel = str(dest.relative_to(library))
    thumb = thumb_file(cache, media_id)
    preview = preview_file(cache, media_id)
    thumb.unlink(missing_ok=True)
    preview.unlink(missing_ok=True)
    make_thumb(dest, thumb, "photo")
    make_preview(dest, preview, "photo")
    digest = dhash_from_image(thumb)

    face_ids = [
        int(r["id"])
        for r in conn.execute("SELECT id FROM faces WHERE media_id=?", (media_id,))
    ]
    for face_id in face_ids:
        face_thumb_file(cache, face_id).unlink(missing_ok=True)
    conn.execute("DELETE FROM faces WHERE media_id=?", (media_id,))
    conn.execute(
        """
        UPDATE media SET
            relpath=?, size=?, mtime_ns=?, thumb_ok=1, face_scanned=0,
            dhash=?, pair_key=?, indexed_at=?, width=?, height=?
        WHERE id=?
        """,
        (
            rel,
            st.st_size,
            getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
            digest,
            pair_key_of(rel),
            _now_iso(),
            edited.width,
            edited.height,
            media_id,
        ),
    )
    conn.commit()
    return {
        "id": media_id,
        "relpath": rel,
        "name": dest.name,
        "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        "size": st.st_size,
        "width": edited.width,
        "height": edited.height,
    }
