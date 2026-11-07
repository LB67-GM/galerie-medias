from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags

EXIF_DT = re.compile(
    r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"
)
ISO_DT = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})"
)


def _norm_dt(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    for rx in (EXIF_DT, ISO_DT):
        m = rx.match(text)
        if m:
            y, mo, d, h, mi, s = (int(x) for x in m.groups())
            try:
                datetime(y, mo, d, h, mi, s)
            except ValueError:
                return None
            return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
    return None


def taken_at_from_image(path: Path) -> str | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                name = ExifTags.TAGS.get(tag_id, "")
                if name in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}:
                    got = _norm_dt(str(value))
                    if got:
                        return got
            try:
                ifd = exif.get_ifd(ExifTags.IFD.Exif)
            except Exception:
                ifd = {}
            for tag_id, value in ifd.items():
                name = ExifTags.TAGS.get(tag_id, "")
                if name in {"DateTimeOriginal", "DateTimeDigitized"}:
                    got = _norm_dt(str(value))
                    if got:
                        return got
    except Exception:
        return None
    return None


def taken_at_from_ffprobe(path: Path) -> str | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_entries",
                "format_tags=creation_time:stream_tags=creation_time",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    tags = (data.get("format") or {}).get("tags") or {}
    got = _norm_dt(tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate"))
    if got:
        return got
    for stream in data.get("streams") or []:
        stags = stream.get("tags") or {}
        got = _norm_dt(stags.get("creation_time"))
        if got:
            return got
    return None


def taken_at_from_mtime(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts).replace(microsecond=0).isoformat()


def taken_at_for(path: Path, kind: str) -> str:
    if kind == "photo":
        got = taken_at_from_image(path)
        if got:
            return got
    else:
        got = taken_at_from_ffprobe(path)
        if got:
            return got
    return taken_at_from_mtime(path)
