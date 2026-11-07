from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from photo_library.config import JPEG_QUALITY, PREVIEW_MAX_SIDE, THUMB_MAX_SIDE
from photo_library.ffmpeg_util import ffmpeg_bin

_heif_ready = False


def ensure_heif() -> None:
    global _heif_ready
    if _heif_ready:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        pass
    _heif_ready = True


def thumb_file(cache: Path, media_id: int) -> Path:
    shard = f"{media_id % 100:02d}"
    return cache / "thumbs" / shard / f"{media_id}.jpg"


def preview_file(cache: Path, media_id: int) -> Path:
    shard = f"{media_id % 100:02d}"
    return cache / "previews" / shard / f"{media_id}.jpg"


def face_thumb_file(cache: Path, face_id: int) -> Path:
    shard = f"{face_id % 100:02d}"
    return cache / "faces" / shard / f"{face_id}.jpg"


def _save_resized(img: Image.Image, dest: Path, max_side: int, quality: int) -> tuple[int, int]:
    img = ImageOps.exif_transpose(img)
    if img.mode not in {"RGB", "L"}:
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    img.save(tmp, "JPEG", quality=quality, optimize=True)
    tmp.replace(dest)
    return img.size


def jpeg_from_image(src: Path, dest: Path, max_side: int, quality: int = JPEG_QUALITY) -> tuple[int, int]:
    ensure_heif()
    with Image.open(src) as img:
        return _save_resized(img, dest, max_side, quality)


def jpeg_from_video(src: Path, dest: Path, max_side: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        "0.4",
        "-i",
        str(src),
        "-an",
        "-frames:v",
        "1",
        "-update",
        "1",
        "-vf",
        f"scale='min({max_side},iw)':-2",
        "-q:v",
        "4",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 32:
        cmd[cmd.index("-ss") + 1] = "0"
        proc = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    if not tmp.is_file() or tmp.stat().st_size < 32:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-400:])
    tmp.replace(dest)


def make_thumb(src: Path, dest: Path, kind: str) -> None:
    if kind == "video":
        jpeg_from_video(src, dest, THUMB_MAX_SIDE)
    else:
        jpeg_from_image(src, dest, THUMB_MAX_SIDE)


def make_preview(src: Path, dest: Path, kind: str) -> None:
    if kind == "video":
        jpeg_from_video(src, dest, PREVIEW_MAX_SIDE)
    else:
        jpeg_from_image(src, dest, PREVIEW_MAX_SIDE)


def dhash_from_image(path: Path) -> str | None:
    """Empreinte visuelle 64 bits (dHash) d’une miniature JPEG déjà générée."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
    except OSError:
        return None
    bits = 0
    for row in range(8):
        base = row * 9
        for col in range(8):
            bits = (bits << 1) | (1 if pixels[base + col] > pixels[base + col + 1] else 0)
    return f"{bits:016x}"
