#!/usr/bin/env python3
"""Classe les médias par année et lieu GPS (EXIF / QuickTime).

Vrac (pas de dossier Annee) : crée Annee YYYY, et Ville si GPS.
Dossiers année existants : racine de l’année et racine des dossiers mois -> Ville si GPS.
Triage iCloud : --triage. Export Messenger/Facebook : --facebook (dates JSON).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LIBRARY = Path.home() / "Photos"
DEFAULT_TRIAGE = Path("/mnt/nas-triage/icloud")
DEFAULT_FACEBOOK = Path("/mnt/nas-triage/facebook")
YEAR_DIR_RE = re.compile(r"^annee[ _-](\d{4})$", re.IGNORECASE)
EXIF_DT_ASCII_RE = re.compile(rb"^(\d{4}):(\d{2}):(\d{2})")
ISO_DT_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ]"
)
NAME_YEAR_RE = re.compile(
    r"(?:^|[_\-])((?:19|20)\d{2})(?:\d{4})?(?:[_\-.]|$)",
    re.IGNORECASE,
)
NAME_YMD_RE = re.compile(
    r"(?:^|[_\-])((?:19|20)\d{2})(\d{2})(\d{2})(?:[_\-.]|$)",
    re.IGNORECASE,
)
SKIP_WALK_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "@eadir",
    ".trash",
    "thumbs",
    "_syncapp",
    "__macosx",
    ".photo-sort-lieux",
}
ISO6709_RE = re.compile(
    rb"([+-]\d{2,3}(?:\.\d+)?)([+-]\d{3}(?:\.\d+)?)(?:[+-]\d+(?:\.\d+)?)?/"
)
ISO6709_TEXT_RE = re.compile(
    r"([+-]\d{2,3}(?:\.\d+)?)([+-]\d{3}(?:\.\d+)?)(?:[+-]\d+(?:\.\d+)?)?/"
)

MEDIA_SUFFIXES = {
    ".heic",
    ".heif",
    ".hif",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".raf",
    ".orf",
    ".rw2",
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".3gp",
    ".mkv",
    ".webm",
    ".mpg",
    ".mpeg",
    ".mpe",
    ".mts",
    ".m2ts",
    ".wmv",
}
IMAGE_SUFFIXES = {
    ".heic",
    ".heif",
    ".hif",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".raf",
    ".orf",
    ".rw2",
}
VIDEO_SUFFIXES = {
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".3gp",
    ".mkv",
    ".webm",
    ".mpg",
    ".mpeg",
    ".mpe",
    ".mts",
    ".m2ts",
    ".wmv",
}
# iPhone : Live Photo = photo + .MOV du même nom. Les vraies vidéos restent en place.
LIVE_VIDEO_SUFFIXES = {".mov"}

IMAGE_HEAD_BYTES = 2_000_000
VIDEO_HEAD_BYTES = 4_000_000
VIDEO_TAIL_BYTES = 4_000_000

# reverse_geocoder renvoie souvent des noms ASCII ; affichage FR pour le dossier.
NAMES_FR = {
    "montreal": "Montréal",
    "quebec": "Québec",
    "levis": "Lévis",
    "trois-rivieres": "Trois-Rivières",
    "trois rivieres": "Trois-Rivières",
    "saint-jerome": "Saint-Jérôme",
    "st-jerome": "Saint-Jérôme",
    "montreal-est": "Montréal-Est",
    "montreal-nord": "Montréal-Nord",
    "montreal-ouest": "Montréal-Ouest",
    "ile-perrot": "Île-Perrot",
    "l'ile-perrot": "L'Île-Perrot",
    "notre-dame-de-l'ile-perrot": "Notre-Dame-de-l'Île-Perrot",
    "repentigny": "Repentigny",
    "terrebonne": "Terrebonne",
    "brossard": "Brossard",
    "longueuil": "Longueuil",
    "laval": "Laval",
    "gatineau": "Gatineau",
    "sherbrooke": "Sherbrooke",
    "drummondville": "Drummondville",
    "granby": "Granby",
    "saguenay": "Saguenay",
    "rimouski": "Rimouski",
    "rouyn-noranda": "Rouyn-Noranda",
    "val-d'or": "Val-d'Or",
    "saint-hyacinthe": "Saint-Hyacinthe",
    "saint-jean-sur-richelieu": "Saint-Jean-sur-Richelieu",
    "sainte-therese": "Sainte-Thérèse",
    "sainte-julie": "Sainte-Julie",
    "sainte-adele": "Sainte-Adèle",
    "sainte-agathe-des-monts": "Sainte-Agathe-des-Monts",
    "mont-tremblant": "Mont-Tremblant",
    "saint-sauveur": "Saint-Sauveur",
    "blainville": "Blainville",
    "mirabel": "Mirabel",
    "mascouche": "Mascouche",
    "varennes": "Varennes",
    "boucherville": "Boucherville",
    "saint-lambert": "Saint-Lambert",
    "saint-bruno-de-montarville": "Saint-Bruno-de-Montarville",
    "chateauguay": "Châteauguay",
    "candiac": "Candiac",
    "la prairie": "La Prairie",
    "saint-constant": "Saint-Constant",
    "vaucluse": "Vaucluse",
    "joliette": "Joliette",
    "rawdon": "Rawdon",
    "berthierville": "Berthierville",
    "sorel-tracy": "Sorel-Tracy",
    "victoriaville": "Victoriaville",
    "thetford-mines": "Thetford Mines",
    "riviere-du-loup": "Rivière-du-Loup",
    "baie-saint-paul": "Baie-Saint-Paul",
    "la malbaie": "La Malbaie",
    "tadoussac": "Tadoussac",
    "perce": "Percé",
    "gaspe": "Gaspé",
    "carleton-sur-mer": "Carleton-sur-Mer",
    "paris": "Paris",
    "lyon": "Lyon",
    "marseille": "Marseille",
    "nice": "Nice",
    "bordeaux": "Bordeaux",
    "toulouse": "Toulouse",
    "lille": "Lille",
    "strasbourg": "Strasbourg",
    "cannes": "Cannes",
    "aix-en-provence": "Aix-en-Provence",
    "saint-tropez": "Saint-Tropez",
    "washington, d.c.": "Washington",
    "washington, d.c": "Washington",
    "washington": "Washington",
    "new york": "New York",
    "new york city": "New York",
    "boston": "Boston",
    "miami": "Miami",
    "los angeles": "Los Angeles",
    "san francisco": "San Francisco",
    "rome": "Rome",
    "milan": "Milan",
    "florence": "Florence",
    "venice": "Venise",
    "venice italy": "Venise",
    "barcelona": "Barcelone",
    "madrid": "Madrid",
    "lisbon": "Lisbonne",
    "lisboa": "Lisbonne",
    "brussels": "Bruxelles",
    "bruxelles": "Bruxelles",
    "amsterdam": "Amsterdam",
    "london": "Londres",
    "geneva": "Genève",
    "zurich": "Zurich",
    "munich": "Munich",
    "berlin": "Berlin",
    "vienna": "Vienne",
    "prague": "Prague",
    "athens": "Athènes",
    "istanbul": "Istanbul",
    "cancun": "Cancún",
    "mexico city": "Mexico",
    "havana": "La Havane",
    "kingston": "Kingston",
    "montego bay": "Montego Bay",
    "providenciales": "Providenciales",
    "cockburn town": "Cockburn Town",
    "grand turk": "Grand Turk",
}


@dataclass(frozen=True)
class Fingerprint:
    size: int
    mtime_ns: int


@dataclass
class IndexRow:
    relpath: str
    size: int
    mtime_ns: int
    status: str
    lat: float | None
    lon: float | None
    place: str | None
    dest_relpath: str | None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fingerprint(path: Path) -> Fingerprint:
    st = path.stat()
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
    return Fingerprint(size=st.st_size, mtime_ns=int(mtime_ns))


def rel_to(library: Path, path: Path) -> str:
    return str(path.resolve().relative_to(library.resolve()))


def year_dirs(library: Path, year: int | None) -> list[Path]:
    found: list[tuple[int, Path]] = []
    for child in sorted(library.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        match = YEAR_DIR_RE.match(child.name)
        if not match:
            continue
        y = int(match.group(1))
        if year is not None and y != year:
            continue
        found.append((y, child))
    return [p for _, p in sorted(found)]


def root_media_files(year_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not year_dir.is_dir():
        return files
    for child in year_dir.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() in MEDIA_SUFFIXES:
            files.append(child)
    files.sort(key=lambda p: p.name.lower())
    return files


MONTHS_FR = {
    1: "Janvier",
    2: "Fevrier",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Aout",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Decembre",
}
FACEBOOK_MEDIA_KEYS = ("photos", "videos", "gifs", "files")
_MONTH_FOLDER_RE = re.compile(r"^([a-z]+)\s+(\d{4})$")
_MONTH_NAMES = {
    unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    for name in MONTHS_FR.values()
}


def is_month_folder(name: str) -> bool:
    """Dossiers type « Janvier 2006 » / « aout 2008 »."""
    nfkd = unicodedata.normalize("NFKD", name or "")
    folded = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    folded = re.sub(r"\s+", " ", folded)
    match = _MONTH_FOLDER_RE.fullmatch(folded)
    return bool(match and match.group(1) in _MONTH_NAMES)


def month_folder_name(year: int, month: int) -> str:
    return f"{MONTHS_FR[month]} {year}"


def year_month_root_files(year_dir: Path) -> list[Path]:
    """Fichiers à la racine de l’année et à la racine de chaque dossier mois."""
    files = root_media_files(year_dir)
    if not year_dir.is_dir():
        return files
    for child in year_dir.iterdir():
        if child.is_dir() and is_month_folder(child.name):
            files.extend(root_media_files(child))
    files.sort(key=lambda p: str(p).lower())
    return files


def group_key(path: Path) -> str:
    """Regroupe IMG_1234.HEIC avec IMG_1234.MOV et IMG_1234_HEVC.MOV (iCloud)."""
    stem = path.stem.lower()
    if path.suffix.lower() in VIDEO_SUFFIXES and stem.endswith("_hevc"):
        stem = stem[: -len("_hevc")]
    return stem


def group_by_stem(files: list[Path]) -> list[list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        groups[group_key(path)].append(path)
    return [groups[k] for k in sorted(groups)]


def is_icloud_live_video(path: Path) -> bool:
    return path.suffix.lower() in LIVE_VIDEO_SUFFIXES and path.stem.lower().endswith("_hevc")


def split_live_companions(group: list[Path]) -> tuple[list[Path], list[Path]]:
    """Sépare la photo (conservée) du .MOV Live Photo (à supprimer)."""
    has_still = any(p.suffix.lower() in IMAGE_SUFFIXES for p in group)
    live: list[Path] = []
    for path in group:
        if path.suffix.lower() not in LIVE_VIDEO_SUFFIXES:
            continue
        if has_still or is_icloud_live_video(path):
            live.append(path)
    keep = [p for p in group if p not in live]
    return keep, live


def _u(buf: bytes, endian: str, fmt: str, offset: int):
    size = struct.calcsize(endian + fmt)
    if offset < 0 or offset + size > len(buf):
        return None
    return struct.unpack(endian + fmt, buf[offset : offset + size])[0]


def _ifd_entries(buf: bytes, endian: str, offset: int) -> dict[int, tuple[int, int, int]]:
    count = _u(buf, endian, "H", offset)
    if count is None or count > 256:
        return {}
    entries: dict[int, tuple[int, int, int]] = {}
    pos = offset + 2
    for _ in range(count):
        tag = _u(buf, endian, "H", pos)
        typ = _u(buf, endian, "H", pos + 2)
        cnt = _u(buf, endian, "I", pos + 4)
        val_off = pos + 8
        if tag is None or typ is None or cnt is None:
            break
        entries[tag] = (typ, cnt, val_off)
        pos += 12
    return entries


def _entry_bytes(buf: bytes, endian: str, typ: int, count: int, val_off: int) -> bytes | None:
    unit = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}.get(typ)
    if unit is None:
        return None
    nbytes = unit * count
    if nbytes <= 4:
        return buf[val_off : val_off + nbytes]
    ptr = _u(buf, endian, "I", val_off)
    if ptr is None or ptr < 0 or ptr + nbytes > len(buf):
        return None
    return buf[ptr : ptr + nbytes]


def _rationals(buf: bytes, endian: str, data: bytes, signed: bool) -> list[float]:
    fmt = "i" if signed else "I"
    out: list[float] = []
    for i in range(0, len(data) - 7, 8):
        num = struct.unpack(endian + fmt, data[i : i + 4])[0]
        den = struct.unpack(endian + fmt, data[i + 4 : i + 8])[0]
        out.append(float(num) / float(den) if den else 0.0)
    return out


def _ascii(data: bytes) -> str:
    return data.split(b"\x00")[0].decode("ascii", "replace").strip()


def dms_to_deg(values: list[float], ref: str) -> float | None:
    if len(values) < 3:
        return None
    deg = values[0] + values[1] / 60.0 + values[2] / 3600.0
    if ref in {"S", "W"}:
        deg = -deg
    return deg


def gps_from_exif_tiff(blob: bytes) -> tuple[float, float] | None:
    if blob.startswith(b"Exif\x00\x00"):
        blob = blob[6:]
    if blob[:2] == b"II":
        endian = "<"
    elif blob[:2] == b"MM":
        endian = ">"
    else:
        return None
    tiff = blob
    ifd0 = _u(tiff, endian, "I", 4)
    if ifd0 is None:
        return None
    entries = _ifd_entries(tiff, endian, ifd0)
    gps_ptr_entry = entries.get(0x8825)
    if not gps_ptr_entry:
        return None
    typ, count, val_off = gps_ptr_entry
    gps_off = _u(tiff, endian, "I", val_off)
    if gps_off is None:
        return None
    gps = _ifd_entries(tiff, endian, gps_off)

    def gps_vals(tag: int) -> tuple[int, bytes] | None:
        item = gps.get(tag)
        if not item:
            return None
        t, c, off = item
        raw = _entry_bytes(tiff, endian, t, c, off)
        if raw is None:
            return None
        return t, raw

    lat_item = gps_vals(2)
    lon_item = gps_vals(4)
    if not lat_item or not lon_item:
        return None
    lat_ref_item = gps_vals(1)
    lon_ref_item = gps_vals(3)
    lat_ref = _ascii(lat_ref_item[1]) if lat_ref_item else "N"
    lon_ref = _ascii(lon_ref_item[1]) if lon_ref_item else "E"
    lat_t, lat_raw = lat_item
    lon_t, lon_raw = lon_item
    lat_dms = _rationals(tiff, endian, lat_raw, signed=lat_t == 10)
    lon_dms = _rationals(tiff, endian, lon_raw, signed=lon_t == 10)
    lat = dms_to_deg(lat_dms, lat_ref[:1])
    lon = dms_to_deg(lon_dms, lon_ref[:1])
    if lat is None or lon is None:
        return None
    if abs(lat) < 1e-8 and abs(lon) < 1e-8:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def gps_from_image_bytes(data: bytes) -> tuple[float, float] | None:
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 < len(data):
            if data[pos] != 0xFF:
                break
            marker = data[pos + 1]
            if marker in {0xD9, 0xDA}:
                break
            seglen = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            if seglen < 2 or pos + 2 + seglen > len(data):
                break
            payload = data[pos + 4 : pos + 2 + seglen]
            if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
                found = gps_from_exif_tiff(payload)
                if found:
                    return found
            pos += 2 + seglen
        return None
    idx = 0
    while True:
        found_at = data.find(b"Exif\x00\x00", idx)
        if found_at < 0:
            return None
        chunk = data[found_at : found_at + 512_000]
        parsed = gps_from_exif_tiff(chunk)
        if parsed:
            return parsed
        idx = found_at + 4


def gps_from_iso6709(data: bytes) -> tuple[float, float] | None:
    match = ISO6709_RE.search(data)
    if not match:
        return None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if abs(lat) < 1e-8 and abs(lon) < 1e-8:
        return None
    return lat, lon


def read_head_tail(path: Path, head: int, tail: int) -> bytes:
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size <= head + tail:
            return fh.read()
        start = fh.read(head)
        fh.seek(size - tail)
        return start + fh.read(tail)


def gps_from_ffprobe(path: Path) -> tuple[float, float] | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    tags = (payload.get("format") or {}).get("tags") or {}
    for key in (
        "com.apple.quicktime.location.ISO6709",
        "location",
        "location-eng",
        "LOCATION",
    ):
        value = tags.get(key)
        if not value:
            continue
        match = ISO6709_TEXT_RE.search(str(value))
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if abs(lat) < 1e-8 and abs(lon) < 1e-8:
                continue
            return lat, lon
    return None


def extract_gps(path: Path) -> tuple[float, float] | None:
    suffix = path.suffix.lower()
    try:
        if suffix in IMAGE_SUFFIXES:
            data = read_head_tail(path, IMAGE_HEAD_BYTES, 0)
            return gps_from_image_bytes(data)
        if suffix in VIDEO_SUFFIXES:
            data = read_head_tail(path, VIDEO_HEAD_BYTES, VIDEO_TAIL_BYTES)
            found = gps_from_iso6709(data)
            if found:
                return found
            return gps_from_ffprobe(path)
    except OSError:
        return None
    return None


def prefer_gps(group: list[Path], coords: dict[Path, tuple[float, float] | None]) -> tuple[float, float] | None:
    images = [p for p in group if p.suffix.lower() in IMAGE_SUFFIXES]
    videos = [p for p in group if p.suffix.lower() in VIDEO_SUFFIXES]
    for path in images + videos + group:
        value = coords.get(path)
        if value:
            return value
    return None


def safe_dir_name(name: str) -> str:
    name = unicodedata.normalize("NFC", name).strip()
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "-")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name


def place_label(name: str) -> str:
    key = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    key = key.lower().strip()
    mapped = NAMES_FR.get(key) or NAMES_FR.get(name.lower())
    return safe_dir_name(mapped or name)


def _exif_ascii_taken(tiff: bytes, endian: str, entries: dict, tag: int) -> datetime | None:
    item = entries.get(tag)
    if not item:
        return None
    typ, cnt, val_off = item
    raw = _entry_bytes(tiff, endian, typ, cnt, val_off)
    if not raw:
        return None
    match = EXIF_DT_ASCII_RE.match(raw)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    if not (1980 <= year <= 2100 and 1 <= month <= 12):
        return None
    try:
        return datetime(year, month, day)
    except ValueError:
        return datetime(year, month, 1)


def _exif_ascii_year(tiff: bytes, endian: str, entries: dict, tag: int) -> int | None:
    taken = _exif_ascii_taken(tiff, endian, entries, tag)
    return taken.year if taken else None


def taken_from_exif_tiff(blob: bytes) -> datetime | None:
    if blob.startswith(b"Exif\x00\x00"):
        blob = blob[6:]
    if blob[:2] == b"II":
        endian = "<"
    elif blob[:2] == b"MM":
        endian = ">"
    else:
        return None
    tiff = blob
    ifd0 = _u(tiff, endian, "I", 4)
    if ifd0 is None:
        return None
    entries = _ifd_entries(tiff, endian, ifd0)
    taken = None
    exif_ptr = entries.get(0x8769)
    if exif_ptr:
        off = _u(tiff, endian, "I", exif_ptr[2])
        if off is not None:
            exif_entries = _ifd_entries(tiff, endian, off)
            taken = _exif_ascii_taken(tiff, endian, exif_entries, 0x9003) or _exif_ascii_taken(
                tiff, endian, exif_entries, 0x9004
            )
    return taken or _exif_ascii_taken(tiff, endian, entries, 0x0132)


def year_from_exif_tiff(blob: bytes) -> int | None:
    taken = taken_from_exif_tiff(blob)
    return taken.year if taken else None


def taken_from_exif_bytes(data: bytes) -> datetime | None:
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 < len(data):
            if data[pos] != 0xFF:
                break
            marker = data[pos + 1]
            if marker in {0xD9, 0xDA}:
                break
            seglen = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            if seglen < 2 or pos + 2 + seglen > len(data):
                break
            payload = data[pos + 4 : pos + 2 + seglen]
            if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
                found = taken_from_exif_tiff(payload)
                if found:
                    return found
            pos += 2 + seglen
        return None
    idx = 0
    while True:
        found_at = data.find(b"Exif\x00\x00", idx)
        if found_at < 0:
            return None
        parsed = taken_from_exif_tiff(data[found_at : found_at + 512_000])
        if parsed:
            return parsed
        idx = found_at + 4


def year_from_exif_bytes(data: bytes) -> int | None:
    taken = taken_from_exif_bytes(data)
    return taken.year if taken else None


def taken_from_ffprobe(path: Path) -> datetime | None:
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
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    texts: list[str] = []
    tags = (payload.get("format") or {}).get("tags") or {}
    for key in ("creation_time", "com.apple.quicktime.creationdate"):
        if tags.get(key):
            texts.append(str(tags[key]))
    for stream in payload.get("streams") or []:
        stags = stream.get("tags") or {}
        if stags.get("creation_time"):
            texts.append(str(stags["creation_time"]))
    for text in texts:
        match = ISO_DT_RE.match(text.strip())
        if not match:
            continue
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        if 1980 <= year <= 2100 and 1 <= month <= 12:
            try:
                return datetime(year, month, day)
            except ValueError:
                return datetime(year, month, 1)
    return None


def year_from_ffprobe(path: Path) -> int | None:
    taken = taken_from_ffprobe(path)
    return taken.year if taken else None


def taken_from_filename(name: str) -> datetime | None:
    match = NAME_YMD_RE.search(name)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        if 1980 <= year <= 2100 and 1 <= month <= 12:
            try:
                return datetime(year, month, day)
            except ValueError:
                return datetime(year, month, 1)
    year = year_from_filename(name)
    if year is None:
        return None
    return datetime(year, 1, 1)


def year_from_filename(name: str) -> int | None:
    match = NAME_YEAR_RE.search(name)
    if not match:
        return None
    year = int(match.group(1))
    if 1980 <= year <= 2100:
        return year
    return None


def taken_from_media(path: Path) -> datetime:
    """Date de prise : EXIF / ffprobe, sinon YYYYMMDD dans le nom, sinon mtime."""
    suffix = path.suffix.lower()
    try:
        if suffix in IMAGE_SUFFIXES:
            data = read_head_tail(path, IMAGE_HEAD_BYTES, 0)
            found = taken_from_exif_bytes(data)
            if found:
                return found
        elif suffix in VIDEO_SUFFIXES:
            found = taken_from_ffprobe(path)
            if found:
                return found
    except OSError:
        pass
    found = taken_from_filename(path.name)
    if found and (found.month != 1 or found.day != 1 or NAME_YMD_RE.search(path.name)):
        return found
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        mtime = datetime.now()
    if found and found.year == mtime.year:
        return mtime
    if found:
        return found
    return mtime


def year_from_media(path: Path) -> int:
    return taken_from_media(path).year


def skip_walk_dir(name: str) -> bool:
    low = name.lower()
    if name.startswith(".") or low in SKIP_WALK_DIRS:
        return True
    if low.startswith("backup-") or low.startswith("backup=") or low.startswith("backup_"):
        return True
    return False


def collect_loose_media(library: Path, year: int | None) -> dict[int, list[Path]]:
    """Médias qui ne sont pas déjà sous un dossier Annee YYYY.

    Sans aucun dossier année : tout l’arbre (vrac). Avec des années : seulement
    la racine de la bibliothèque, pour ne pas toucher aux dossiers d’événements.
    """
    by_year: dict[int, list[Path]] = defaultdict(list)
    library = library.resolve()
    year_roots = {p.resolve() for p in year_dirs(library, None)}

    def consider(path: Path) -> None:
        if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            return
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(library)
        except (OSError, ValueError):
            return
        if rel.parts and YEAR_DIR_RE.match(rel.parts[0]):
            return
        y = year_from_media(path)
        if year is not None and y != year:
            return
        by_year[y].append(path)

    if year_roots:
        for child in library.iterdir():
            if child.is_file():
                consider(child)
        return dict(by_year)

    for dirpath, dirnames, filenames in os.walk(library):
        dirnames[:] = [name for name in dirnames if not skip_walk_dir(name)]
        for name in filenames:
            consider(Path(dirpath) / name)
    return dict(by_year)


def unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    n = 2
    while True:
        candidate = dest.with_name(f"{dest.stem}-{n}{dest.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


class Index:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = sqlite3.connect(str(self.path), timeout=60)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA busy_timeout=60000")
            try:
                self.conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                self.conn.execute("PRAGMA journal_mode=DELETE")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    relpath TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    lat REAL,
                    lon REAL,
                    place TEXT,
                    dest_relpath TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS geocode (
                    lat_r REAL NOT NULL,
                    lon_r REAL NOT NULL,
                    place TEXT NOT NULL,
                    PRIMARY KEY (lat_r, lon_r)
                )
                """
            )
            self.conn.commit()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            raise SystemExit(
                "Index SQLite verrouillé.\n"
                f"  Fichier : {self.path}\n"
                "Causes fréquentes : un autre sort_lieux.py encore en cours, "
                "ou une base posée sur le NAS (CIFS). "
                "L'index est maintenant local (~/.cache/photo-sort-lieux/)."
            ) from exc

    def close(self) -> None:
        self.conn.close()

    def get(self, relpath: str) -> IndexRow | None:
        row = self.conn.execute(
            "SELECT relpath, size, mtime_ns, status, lat, lon, place, dest_relpath FROM files WHERE relpath = ?",
            (relpath,),
        ).fetchone()
        if row is None:
            return None
        return IndexRow(
            relpath=row["relpath"],
            size=row["size"],
            mtime_ns=row["mtime_ns"],
            status=row["status"],
            lat=row["lat"],
            lon=row["lon"],
            place=row["place"],
            dest_relpath=row["dest_relpath"],
        )

    def upsert(self, row: IndexRow) -> None:
        self.conn.execute(
            """
            INSERT INTO files (relpath, size, mtime_ns, status, lat, lon, place, dest_relpath, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relpath) DO UPDATE SET
                size=excluded.size,
                mtime_ns=excluded.mtime_ns,
                status=excluded.status,
                lat=excluded.lat,
                lon=excluded.lon,
                place=excluded.place,
                dest_relpath=excluded.dest_relpath,
                updated_at=excluded.updated_at
            """,
            (
                row.relpath,
                row.size,
                row.mtime_ns,
                row.status,
                row.lat,
                row.lon,
                row.place,
                row.dest_relpath,
                now_iso(),
            ),
        )

    def commit(self) -> None:
        self.conn.commit()

    def reset_prefix(self, prefix: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM files WHERE relpath = ? OR relpath LIKE ?",
            (prefix, prefix + "/%"),
        )
        self.conn.commit()
        return cur.rowcount

    def geocode_get(self, lat_r: float, lon_r: float) -> str | None:
        row = self.conn.execute(
            "SELECT place FROM geocode WHERE lat_r = ? AND lon_r = ?",
            (lat_r, lon_r),
        ).fetchone()
        return None if row is None else row["place"]

    def geocode_put(self, lat_r: float, lon_r: float, place: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO geocode (lat_r, lon_r, place) VALUES (?, ?, ?)",
            (lat_r, lon_r, place),
        )


def round_coord(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 3), round(lon, 3)


def resolve_index_path(library: Path, explicit: Path | None = None) -> tuple[Path, str]:
    """SQLite sur CIFS/NAS se verrouille : index local par défaut."""
    if explicit is not None:
        path = explicit.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path, "explicite"

    fallback = Path.home() / ".cache" / "photo-sort-lieux"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
        probe = fallback / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return fallback / "state.sqlite", "cache local"
    except OSError:
        local = Path(__file__).resolve().parent / "data"
        local.mkdir(parents=True, exist_ok=True)
        return local / "state.sqlite", "projet"


class Geocoder:
    def __init__(self, index: Index) -> None:
        self.index = index
        self._rg = None

    def _engine(self):
        if self._rg is None:
            import reverse_geocoder as rg

            self._rg = rg
        return self._rg

    def lookup_many(self, coords: list[tuple[float, float]]) -> dict[tuple[float, float], str]:
        needed: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        result: dict[tuple[float, float], str] = {}
        for lat, lon in coords:
            key = round_coord(lat, lon)
            if key in seen:
                continue
            seen.add(key)
            cached = self.index.geocode_get(*key)
            if cached:
                result[key] = cached
            else:
                needed.append(key)
        if needed:
            engine = self._engine()
            hits = engine.search(needed)
            for key, hit in zip(needed, hits):
                place = place_label(str(hit.get("name") or "").strip())
                if not place:
                    continue
                self.index.geocode_put(key[0], key[1], place)
                result[key] = place
            self.index.commit()
        return result

    def place_for(self, lat: float, lon: float, table: dict[tuple[float, float], str]) -> str | None:
        return table.get(round_coord(lat, lon))


def fresh(row: IndexRow | None, fp: Fingerprint) -> bool:
    return row is not None and row.size == fp.size and row.mtime_ns == fp.mtime_ns


def resolve_year_dir(library: Path, year: int, create: bool) -> Path:
    dirs = year_dirs(library, year)
    preferred: Path | None = None
    for folder in dirs:
        if folder.name[:1].isupper():
            return folder
        preferred = preferred or folder
    if preferred:
        return preferred
    dest = library / f"Annee {year}"
    if create:
        dest.mkdir(parents=True, exist_ok=True)
    return dest


def iter_media(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in MEDIA_SUFFIXES:
                yield path


def catalog_library_year(year_dirs_list: list[Path]) -> dict[str, list[tuple[Path, int]]]:
    catalog: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    count = 0
    for year_dir in year_dirs_list:
        if not year_dir.is_dir():
            continue
        for path in iter_media(year_dir):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            catalog[path.name.lower()].append((path, size))
            count += 1
            if count % 1000 == 0:
                print(f"  Index bibliothèque : {count} fichiers...", flush=True)
    print(f"  Index bibliothèque : {count} fichiers", flush=True)
    return catalog


def find_duplicate(catalog: dict[str, list[tuple[Path, int]]], path: Path, size: int) -> Path | None:
    for existing, existing_size in catalog.get(path.name.lower(), []):
        if existing_size == size:
            return existing
    return None


def list_triage_years(triage_root: Path, year: int | None) -> list[int]:
    years: list[int] = []
    if not triage_root.is_dir():
        return years
    for child in sorted(triage_root.iterdir()):
        if not child.is_dir() or not child.name.isdigit() or len(child.name) != 4:
            continue
        value = int(child.name)
        if year is not None and value != year:
            continue
        years.append(value)
    return years


def triage_media(triage_root: Path, year: int) -> list[Path]:
    folder = triage_root / str(year)
    if not folder.is_dir():
        return []
    files = [p for p in iter_media(folder)]
    files.sort(key=lambda p: str(p).lower())
    return files


def ingest_copy(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(dest)
    shutil.copy2(src, dest)
    return dest


def process_triage_year(
    library: Path,
    triage_root: Path,
    year: int,
    geocoder: Geocoder,
    apply: bool,
    limit: int,
    verbose: bool,
    delete_live: bool,
) -> dict:
    stats = {
        "triage": 0,
        "duplicates": 0,
        "copied": 0,
        "would_copy": 0,
        "would_delete_dup": 0,
        "deleted_live": 0,
        "would_delete_live": 0,
        "no_gps": 0,
        "errors": 0,
        "places": 0,
    }
    year_dir = resolve_year_dir(library, year, create=False)
    print(f"  Cible bibliothèque : {year_dir}")
    catalog = catalog_library_year(year_dirs(library, year) or ([year_dir] if year_dir.is_dir() else []))
    files = triage_media(triage_root, year)
    stats["triage"] = len(files)
    print(f"  Médias dans le triage : {len(files)}", flush=True)
    groups = group_by_stem(files)
    if limit > 0:
        groups = groups[:limit]

    live_jobs: list[list[Path]] = []
    keep_groups: list[list[Path]] = []
    for group in groups:
        keep, live = split_live_companions(group) if delete_live else (list(group), [])
        if live:
            live_jobs.append(live)
        if keep:
            keep_groups.append(keep)

    def delete_triage_file(path: Path) -> bool:
        if not apply:
            return True
        try:
            path.unlink()
        except OSError as exc:
            print(f"  ERREUR suppression {path}: {exc}")
            stats["errors"] += 1
            return False
        return True

    for live in live_jobs:
        for path in live:
            if verbose:
                print(f"  Live Photo: {path.name}")
            if delete_triage_file(path):
                if apply:
                    stats["deleted_live"] += 1
                else:
                    stats["would_delete_live"] += 1

    to_locate: list[list[Path]] = []
    dups: list[tuple[Path, Path]] = []
    fps: dict[Path, Fingerprint] = {}
    for group in keep_groups:
        remaining: list[Path] = []
        for path in group:
            try:
                fp = fingerprint(path)
            except OSError:
                stats["errors"] += 1
                continue
            fps[path] = fp
            dup = find_duplicate(catalog, path, fp.size)
            if dup is not None:
                dups.append((path, dup))
            else:
                remaining.append(path)
        if remaining:
            to_locate.append(remaining)

    for path, dup in dups:
        try:
            rel = dup.relative_to(library)
        except ValueError:
            rel = dup
        if verbose:
            print(f"  doublon {path.name} = {rel}")
        if delete_triage_file(path):
            if apply:
                stats["duplicates"] += 1
            else:
                stats["would_delete_dup"] += 1

    pending_coords: list[tuple[float, float]] = []
    located: list[tuple[list[Path], tuple[float, float] | None]] = []
    if to_locate:
        print(f"  Lecture GPS de {len(to_locate)} groupe(s) nouveau(x)...", flush=True)
    for i, group in enumerate(to_locate, start=1):
        if not verbose and len(to_locate) >= 20 and (i % 25 == 0 or i == len(to_locate)):
            print(f"  GPS {i}/{len(to_locate)}", flush=True)
        coords: dict[Path, tuple[float, float] | None] = {}
        for path in group:
            try:
                coords[path] = extract_gps(path)
            except Exception:
                coords[path] = None
                stats["errors"] += 1
        gps = prefer_gps(group, coords)
        located.append((group, gps))
        if gps:
            pending_coords.append(gps)

    places = geocoder.lookup_many(pending_coords) if pending_coords else {}
    place_dirs: set[str] = set()
    per_place: Counter[str] = Counter()

    for group, gps in located:
        place = geocoder.place_for(gps[0], gps[1], places) if gps else None
        if place:
            dest_dir = year_dir / place
            place_dirs.add(place)
        else:
            dest_dir = year_dir
            stats["no_gps"] += len(group)
        per_place[place or "(sans lieu)"] += len(group)
        for path in group:
            dest = dest_dir / path.name
            if verbose:
                try:
                    shown = dest.relative_to(library)
                except ValueError:
                    shown = dest
                print(f"  nouveau {path.name} -> {shown}")
            if apply:
                try:
                    copied = ingest_copy(path, dest)
                    catalog[copied.name.lower()].append((copied, copied.stat().st_size))
                    path.unlink()
                except OSError as exc:
                    print(f"  ERREUR copie {path} -> {dest}: {exc}")
                    stats["errors"] += 1
                    continue
                stats["copied"] += 1
            else:
                stats["would_copy"] += 1

    stats["places"] = len(place_dirs)
    stats["per_place"] = per_place
    return stats


def print_triage_stats(year: int, stats: dict, apply: bool) -> None:
    print()
    print(f"Résumé triage {year}")
    print(f"  Médias dans le triage     : {stats['triage']}")
    print(
        f"  Doublons (supprimer)      : {stats['duplicates'] if apply else stats['would_delete_dup']}"
    )
    print(
        f"  Live Photos (supprimer)   : {stats['deleted_live'] if apply else stats['would_delete_live']}"
    )
    print(f"  Nouveaux (copier)         : {stats['copied'] if apply else stats['would_copy']}")
    print(f"  Sans GPS (racine année)   : {stats['no_gps']}")
    print(f"  Lieux distincts           : {stats['places']}")
    print(f"  Erreurs                   : {stats['errors']}")
    per_place = stats.get("per_place") or {}
    if per_place:
        print("  Nouveaux par lieu :")
        for place, count in per_place.most_common():
            print(f"    {place}: {count}")


@dataclass
class FacebookStamp:
    taken: datetime
    gps: tuple[float, float] | None = None


def datetime_from_facebook(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if n >= 1_000_000_000_000:
        n /= 1000.0
    try:
        return datetime.fromtimestamp(n)
    except (OSError, OverflowError, ValueError):
        return None


def gps_from_facebook_item(item: object) -> tuple[float, float] | None:
    if isinstance(item, dict):
        lat = item.get("latitude", item.get("lat"))
        lon = item.get("longitude", item.get("lon", item.get("lng")))
        if lat is not None and lon is not None:
            try:
                return (float(lat), float(lon))
            except (TypeError, ValueError):
                pass
        for value in item.values():
            found = gps_from_facebook_item(value)
            if found:
                return found
    elif isinstance(item, list):
        for value in item:
            found = gps_from_facebook_item(value)
            if found:
                return found
    return None


def iter_facebook_json(root: Path):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.json")):
        name = path.name.lower()
        if name.startswith("message_") or name in {"inbox.json", "message.json"}:
            yield path


def _load_facebook_json(path: Path) -> dict | list | None:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


def load_facebook_index(root: Path) -> dict[str, FacebookStamp]:
    """Nom de fichier (casse ignorée) -> date Messenger + GPS JSON s’il existe."""
    index: dict[str, FacebookStamp] = {}
    for json_path in iter_facebook_json(root):
        data = _load_facebook_json(json_path)
        if not isinstance(data, dict):
            continue
        messages = data.get("messages")
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_taken = datetime_from_facebook(msg.get("timestamp_ms") or msg.get("timestamp"))
            for key in FACEBOOK_MEDIA_KEYS:
                for item in msg.get(key) or []:
                    item_dict: dict = {}
                    if isinstance(item, str):
                        uri = item
                    elif isinstance(item, dict):
                        item_dict = item
                        uri = str(item.get("uri") or item.get("path") or "")
                    else:
                        continue
                    name = Path(uri.replace("\\", "/")).name.lower()
                    if not name:
                        continue
                    taken = datetime_from_facebook(item_dict.get("creation_timestamp")) or msg_taken
                    if taken is None:
                        continue
                    gps = gps_from_facebook_item(item_dict) if item_dict else None
                    prev = index.get(name)
                    if prev is None or taken < prev.taken:
                        index[name] = FacebookStamp(taken=taken, gps=gps or (prev.gps if prev else None))
                    elif gps and prev.gps is None:
                        index[name] = FacebookStamp(taken=prev.taken, gps=gps)
    return index


def facebook_media_files(root: Path) -> list[Path]:
    files = [path for path in iter_media(root)]
    files.sort(key=lambda p: str(p).lower())
    return files


def process_facebook(
    library: Path,
    facebook_root: Path,
    geocoder: Geocoder,
    apply: bool,
    limit: int,
    verbose: bool,
    year: int | None = None,
) -> dict:
    json_index = load_facebook_index(facebook_root)
    files = facebook_media_files(facebook_root)
    jobs: list[tuple[Path, FacebookStamp]] = []
    no_json: list[Path] = []
    skipped_year = 0
    for path in files:
        stamp = json_index.get(path.name.lower())
        if stamp is None:
            no_json.append(path)
            continue
        if year is not None and stamp.taken.year != year:
            skipped_year += 1
            continue
        jobs.append((path, stamp))
    jobs.sort(key=lambda item: (item[1].taken, item[0].name.lower()))
    if limit > 0:
        jobs = jobs[:limit]

    stats = {
        "json": len(json_index),
        "json_files": sum(1 for _ in iter_facebook_json(facebook_root)),
        "facebook": len(files),
        "matched": len(jobs),
        "no_json": len(no_json),
        "skipped_year": skipped_year,
        "duplicates": 0,
        "copied": 0,
        "would_copy": 0,
        "would_delete_dup": 0,
        "no_gps": 0,
        "errors": 0,
        "places": 0,
        "per_place": Counter(),
        "per_month": Counter(),
    }
    print(f"  JSON Messenger     : {stats['json_files']} fichier(s), {stats['json']} médias datés")
    print(f"  Médias sur disque  : {stats['facebook']}")
    print(f"  Datés par le JSON  : {stats['matched']}")
    if no_json:
        print(f"  Sans entrée JSON   : {len(no_json)} (ignorés)")
        if verbose:
            for path in no_json[:40]:
                print(f"    sans JSON : {path.name}")
            if len(no_json) > 40:
                print(f"    ... {len(no_json) - 40} de plus")
    if skipped_year:
        print(f"  Autre année        : {skipped_year} (filtre --year)")

    catalogs: dict[int, dict[str, list[tuple[Path, int]]]] = {}
    year_dirs_cache: dict[int, Path] = {}

    def catalog_for(y: int) -> dict[str, list[tuple[Path, int]]]:
        if y not in catalogs:
            year_dir = resolve_year_dir(library, y, create=False)
            year_dirs_cache[y] = year_dir
            catalogs[y] = catalog_library_year(
                year_dirs(library, y) or ([year_dir] if year_dir.is_dir() else [])
            )
        return catalogs[y]

    def delete_facebook_file(path: Path) -> bool:
        if not apply:
            return True
        try:
            path.unlink()
        except OSError as exc:
            print(f"  ERREUR suppression {path}: {exc}")
            stats["errors"] += 1
            return False
        return True

    to_locate: list[tuple[Path, FacebookStamp, tuple[float, float] | None]] = []
    dups: list[tuple[Path, Path]] = []
    for path, stamp in jobs:
        try:
            size = path.stat().st_size
        except OSError:
            stats["errors"] += 1
            continue
        catalog = catalog_for(stamp.taken.year)
        dup = find_duplicate(catalog, path, size)
        if dup is not None:
            dups.append((path, dup))
        else:
            to_locate.append((path, stamp, stamp.gps))

    for path, dup in dups:
        try:
            rel = dup.relative_to(library)
        except ValueError:
            rel = dup
        if verbose:
            print(f"  doublon {path.name} = {rel}")
        if delete_facebook_file(path):
            if apply:
                stats["duplicates"] += 1
            else:
                stats["would_delete_dup"] += 1

    pending: list[tuple[Path, FacebookStamp, tuple[float, float] | None]] = []
    pending_coords: list[tuple[float, float]] = []
    if to_locate:
        print(f"  Lecture GPS de {len(to_locate)} fichier(s) nouveau(x)...", flush=True)
    for i, (path, stamp, json_gps) in enumerate(to_locate, start=1):
        if not verbose and len(to_locate) >= 20 and (i % 25 == 0 or i == len(to_locate)):
            print(f"  GPS {i}/{len(to_locate)}", flush=True)
        gps = json_gps
        if gps is None:
            try:
                gps = extract_gps(path)
            except Exception:
                gps = None
                stats["errors"] += 1
        pending.append((path, stamp, gps))
        if gps:
            pending_coords.append(gps)

    places = geocoder.lookup_many(pending_coords) if pending_coords else {}
    place_dirs: set[str] = set()

    for path, stamp, gps in pending:
        year_dir = year_dirs_cache.get(stamp.taken.year) or resolve_year_dir(
            library, stamp.taken.year, create=False
        )
        if apply:
            year_dir = resolve_year_dir(library, stamp.taken.year, create=True)
            year_dirs_cache[stamp.taken.year] = year_dir
        month_dir = year_dir / month_folder_name(stamp.taken.year, stamp.taken.month)
        place = geocoder.place_for(gps[0], gps[1], places) if gps else None
        if place:
            dest_dir = month_dir / place
            place_dirs.add(place)
        else:
            dest_dir = month_dir
            stats["no_gps"] += 1
        stats["per_place"][place or "(sans lieu)"] += 1
        stats["per_month"][
            f"Annee {stamp.taken.year}/{month_folder_name(stamp.taken.year, stamp.taken.month)}"
        ] += 1
        dest = dest_dir / path.name
        if verbose:
            try:
                shown = dest.relative_to(library)
            except ValueError:
                shown = dest
            print(f"  nouveau {path.name} -> {shown}")
        if apply:
            try:
                copied = ingest_copy(path, dest)
                catalogs.setdefault(stamp.taken.year, defaultdict(list))
                catalogs[stamp.taken.year][copied.name.lower()].append(
                    (copied, copied.stat().st_size)
                )
                path.unlink()
            except OSError as exc:
                print(f"  ERREUR copie {path} -> {dest}: {exc}")
                stats["errors"] += 1
                continue
            stats["copied"] += 1
        else:
            stats["would_copy"] += 1

    stats["places"] = len(place_dirs)
    return stats


def print_facebook_stats(stats: dict, apply: bool) -> None:
    print()
    print("Résumé Facebook / Messenger")
    print(f"  Médias dans le dossier    : {stats['facebook']}")
    print(f"  Datés par message_*.json  : {stats['matched']}")
    print(f"  Sans JSON (ignorés)       : {stats['no_json']}")
    print(
        f"  Doublons (supprimer)      : {stats['duplicates'] if apply else stats['would_delete_dup']}"
    )
    print(f"  Nouveaux (copier)         : {stats['copied'] if apply else stats['would_copy']}")
    print(f"  Sans GPS (dossier mois)   : {stats['no_gps']}")
    print(f"  Lieux distincts           : {stats['places']}")
    print(f"  Erreurs                   : {stats['errors']}")
    per_month = stats.get("per_month") or {}
    if per_month:
        print("  Nouveaux par mois :")
        for folder, count in sorted(per_month.items()):
            print(f"    {folder}: {count}")
    per_place = stats.get("per_place") or {}
    if per_place:
        print("  Nouveaux par lieu :")
        for place, count in per_place.most_common():
            print(f"    {place}: {count}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classe les photos/vidéos : vrac -> Annee YYYY/Ville si GPS ; "
            "fichiers déjà à la racine d’une année -> Ville si GPS. "
            "Ou ingère le triage iCloud (--triage) / Facebook Messenger (--facebook)."
        )
    )
    parser.add_argument(
        "-d",
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY,
        help=f"Racine de la bibliothèque (défaut : {DEFAULT_LIBRARY})",
    )
    parser.add_argument(
        "--triage",
        action="store_true",
        help=f"Comparer / copier depuis le triage iCloud (défaut : {DEFAULT_TRIAGE})",
    )
    parser.add_argument(
        "--triage-dir",
        type=Path,
        default=DEFAULT_TRIAGE,
        help=f"Dossier triage (défaut : {DEFAULT_TRIAGE})",
    )
    parser.add_argument(
        "--facebook",
        action="store_true",
        help=f"Ingérer l’export Messenger/Facebook (défaut : {DEFAULT_FACEBOOK})",
    )
    parser.add_argument(
        "--facebook-dir",
        type=Path,
        default=DEFAULT_FACEBOOK,
        help=f"Dossier Facebook (défaut : {DEFAULT_FACEBOOK})",
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--year", type=int, help="Année à traiter (ex. 2024)")
    group.add_argument("--all", action="store_true", help="Toutes les années")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrire réellement (déplacer / copier / supprimer), sinon simulation",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de groupes traités")
    parser.add_argument(
        "--reset-index",
        action="store_true",
        help="Oublier l'index de l'année choisie (ou de toute la bibliothèque avec --all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Lister chaque fichier au lieu d'un résumé par lieu",
    )
    parser.add_argument(
        "--keep-live",
        action="store_true",
        help="Conserver les .MOV des Live Photos (par défaut ils sont supprimés)",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Fichier SQLite d'index (défaut : ~/.cache/photo-sort-lieux/state.sqlite)",
    )
    args = parser.parse_args(argv)
    if args.facebook and args.triage:
        parser.error("--facebook et --triage sont exclusifs")
    if not args.triage and not args.facebook and args.year is None and not args.all:
        parser.error("indiquez --year N, --all, --triage, ou --facebook")
    return args


def process_year(
    library: Path,
    year_dir: Path,
    index: Index,
    geocoder: Geocoder,
    apply: bool,
    limit: int,
    verbose: bool,
    delete_live: bool,
    files: list[Path] | None = None,
    move_no_gps: bool = False,
) -> dict:
    stats = {
        "root": 0,
        "skipped_cached": 0,
        "moved": 0,
        "would_move": 0,
        "no_gps": 0,
        "errors": 0,
        "places": 0,
        "deleted_live": 0,
        "would_delete_live": 0,
    }
    if files is None:
        print("  Lecture de la racine (année + dossiers mois)...", flush=True)
        files = year_month_root_files(year_dir)
        print(f"  {len(files)} médias à ranger (sous-dossiers nommés ignorés)", flush=True)
    else:
        print(f"  {len(files)} médias en vrac (hors dossiers année)", flush=True)
    stats["root"] = len(files)
    groups = group_by_stem(files)
    if limit > 0:
        groups = groups[:limit]

    to_locate: list[tuple[list[Path], dict[Path, Fingerprint]]] = []
    cached_moves: list[tuple[list[Path], str, dict[Path, Fingerprint], tuple[float, float] | None]] = []
    live_jobs: list[tuple[list[Path], dict[Path, Fingerprint]]] = []

    for group in groups:
        fps = {p: fingerprint(p) for p in group}
        keep, live = split_live_companions(group) if delete_live else (list(group), [])
        if live:
            live_jobs.append((live, fps))
        if not keep:
            continue
        rows = {p: index.get(rel_to(library, p)) for p in keep}
        if (
            not move_no_gps
            and all(fresh(rows[p], fps[p]) and rows[p] and rows[p].status == "no_gps" for p in keep)
        ):
            stats["skipped_cached"] += len(keep)
            continue
        cached_place = None
        cached_gps = None
        for path in keep:
            row = rows[path]
            if fresh(row, fps[path]) and row and row.place and row.status in {"located", "moved"}:
                cached_place = place_label(row.place)
                if row.lat is not None and row.lon is not None:
                    cached_gps = (row.lat, row.lon)
                break
        if cached_place:
            cached_moves.append((keep, cached_place, fps, cached_gps))
        else:
            to_locate.append((keep, fps))

    extracted: list[tuple[list[Path], dict[Path, Fingerprint], tuple[float, float] | None]] = []
    pending_coords: list[tuple[float, float]] = []
    total_locate = len(to_locate)
    if total_locate:
        print(f"  Lecture GPS de {total_locate} groupe(s)...", flush=True)
    for i, (group, fps) in enumerate(to_locate, start=1):
        if not verbose and total_locate >= 20 and (i % 25 == 0 or i == total_locate):
            print(f"  GPS {i}/{total_locate}", flush=True)
        coords: dict[Path, tuple[float, float] | None] = {}
        for path in group:
            try:
                coords[path] = extract_gps(path)
            except Exception:
                coords[path] = None
                stats["errors"] += 1
        gps = prefer_gps(group, coords)
        extracted.append((group, fps, gps))
        if gps:
            pending_coords.append(gps)

    places = geocoder.lookup_many(pending_coords) if pending_coords else {}
    place_dirs: set[str] = set()
    per_place: Counter[str] = Counter()

    def handle_delete_live(live: list[Path], fps: dict[Path, Fingerprint]) -> None:
        for path in live:
            rel_src = rel_to(library, path)
            fp = fps[path]
            if apply:
                try:
                    path.unlink()
                except OSError as exc:
                    print(f"  ERREUR suppression Live Photo {path.name}: {exc}")
                    stats["errors"] += 1
                    index.upsert(
                        IndexRow(
                            relpath=rel_src,
                            size=fp.size,
                            mtime_ns=fp.mtime_ns,
                            status="error",
                            lat=None,
                            lon=None,
                            place=None,
                            dest_relpath=None,
                        )
                    )
                    continue
                stats["deleted_live"] += 1
                index.upsert(
                    IndexRow(
                        relpath=rel_src,
                        size=fp.size,
                        mtime_ns=fp.mtime_ns,
                        status="deleted_live",
                        lat=None,
                        lon=None,
                        place=None,
                        dest_relpath=None,
                    )
                )
            else:
                stats["would_delete_live"] += 1
                index.upsert(
                    IndexRow(
                        relpath=rel_src,
                        size=fp.size,
                        mtime_ns=fp.mtime_ns,
                        status="live_pending",
                        lat=None,
                        lon=None,
                        place=None,
                        dest_relpath=None,
                    )
                )
            if verbose:
                print(f"  Live Photo: suppression {path.name}")

    def handle_move(
        group: list[Path],
        fps: dict[Path, Fingerprint],
        place: str,
        gps: tuple[float, float] | None,
    ) -> None:
        place_dirs.add(place)
        per_place[place] += len(group)
        lat = gps[0] if gps else None
        lon = gps[1] if gps else None
        year_resolved = year_dir.resolve()
        for path in group:
            try:
                path.resolve().relative_to(year_resolved)
                dest_dir = path.parent / place
            except (OSError, ValueError):
                dest_dir = year_dir / place
            dest = unique_dest(dest_dir / path.name)
            rel_src = rel_to(library, path)
            fp = fps[path]
            if apply:
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = unique_dest(dest_dir / path.name)
                try:
                    if path.resolve() == dest.resolve():
                        stats["moved"] += 1
                        index.upsert(
                            IndexRow(
                                relpath=rel_src,
                                size=fp.size,
                                mtime_ns=fp.mtime_ns,
                                status="moved",
                                lat=lat,
                                lon=lon,
                                place=place,
                                dest_relpath=rel_to(library, dest),
                            )
                        )
                        continue
                    path.rename(dest)
                except OSError:
                    try:
                        shutil.move(str(path), str(dest))
                    except OSError as exc:
                        print(f"  ERREUR {path.name} -> {dest}: {exc}")
                        stats["errors"] += 1
                        index.upsert(
                            IndexRow(
                                relpath=rel_src,
                                size=fp.size,
                                mtime_ns=fp.mtime_ns,
                                status="error",
                                lat=lat,
                                lon=lon,
                                place=place,
                                dest_relpath=None,
                            )
                        )
                        continue
                stats["moved"] += 1
                index.upsert(
                    IndexRow(
                        relpath=rel_src,
                        size=fp.size,
                        mtime_ns=fp.mtime_ns,
                        status="moved",
                        lat=lat,
                        lon=lon,
                        place=place,
                        dest_relpath=rel_to(library, dest),
                    )
                )
            else:
                stats["would_move"] += 1
                index.upsert(
                    IndexRow(
                        relpath=rel_src,
                        size=fp.size,
                        mtime_ns=fp.mtime_ns,
                        status="located",
                        lat=lat,
                        lon=lon,
                        place=place,
                        dest_relpath=str(dest.relative_to(library)),
                    )
                )
            if verbose:
                print(f"  {place}: {path.name}")

    def handle_no_gps(group: list[Path], fps: dict[Path, Fingerprint], gps: tuple[float, float] | None) -> None:
        lat = gps[0] if gps else None
        lon = gps[1] if gps else None
        for path in group:
            fp = fps[path]
            rel_src = rel_to(library, path)
            dest: Path | None = None
            if move_no_gps:
                dest = unique_dest(year_dir / path.name)
                try:
                    same = path.resolve() == dest.resolve()
                except OSError:
                    same = False
                if not same:
                    if apply:
                        year_dir.mkdir(parents=True, exist_ok=True)
                        dest = unique_dest(year_dir / path.name)
                        try:
                            path.rename(dest)
                        except OSError:
                            try:
                                shutil.move(str(path), str(dest))
                            except OSError as exc:
                                print(f"  ERREUR {path.name} -> {dest}: {exc}")
                                stats["errors"] += 1
                                index.upsert(
                                    IndexRow(
                                        relpath=rel_src,
                                        size=fp.size,
                                        mtime_ns=fp.mtime_ns,
                                        status="error",
                                        lat=lat,
                                        lon=lon,
                                        place=None,
                                        dest_relpath=None,
                                    )
                                )
                                continue
                        stats["moved"] += 1
                    else:
                        stats["would_move"] += 1
            stats["no_gps"] += 1
            index.upsert(
                IndexRow(
                    relpath=rel_src,
                    size=fp.size,
                    mtime_ns=fp.mtime_ns,
                    status="no_gps",
                    lat=lat,
                    lon=lon,
                    place=None,
                    dest_relpath=rel_to(library, dest) if dest and apply and dest.exists() else (
                        str(dest.relative_to(library)) if dest is not None else None
                    ),
                )
            )
            if verbose and dest is not None:
                print(f"  {year_dir.name} (sans GPS): {path.name}")

    for live, fps in live_jobs:
        handle_delete_live(live, fps)

    for group, place, fps, gps in cached_moves:
        handle_move(group, fps, place, gps)

    for group, fps, gps in extracted:
        if gps is None:
            handle_no_gps(group, fps, None)
            continue
        place = geocoder.place_for(gps[0], gps[1], places)
        if not place:
            handle_no_gps(group, fps, gps)
            continue
        handle_move(group, fps, place, gps)

    index.commit()
    stats["places"] = len(place_dirs)
    stats["per_place"] = per_place
    return stats


def print_stats(year_dir: Path, stats: dict, apply: bool) -> None:
    action = "déplacés" if apply else "à déplacer"
    print()
    print(f"Résumé {year_dir.name}")
    print(f"  Médias traités         : {stats['root']}")
    print(f"  Déjà vus, sans lieu    : {stats['skipped_cached']} (index, ignorés)")
    print(f"  {action:<22} : {stats['moved'] if apply else stats['would_move']}")
    live_action = "Live Photos supprimées" if apply else "Live Photos à supprimer"
    print(f"  {live_action:<22} : {stats['deleted_live'] if apply else stats['would_delete_live']}")
    print(f"  Sans GPS               : {stats['no_gps']}")
    print(f"  Lieux distincts        : {stats['places']}")
    print(f"  Erreurs                : {stats['errors']}")
    per_place = stats.get("per_place") or {}
    if per_place:
        print("  Détail par lieu :")
        for place, count in per_place.most_common():
            print(f"    {place}: {count}")


def reexec_venv() -> None:
    script_dir = Path(__file__).resolve().parent
    venv_dir = script_dir / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if not venv_python.is_file():
        venv_python = venv_dir / "Scripts" / "python.exe"
    if not venv_python.is_file():
        return
    if Path(sys.prefix).resolve() == venv_dir.resolve():
        return
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


def _configure_stdio() -> None:
    """Evite UnicodeEncodeError sur la console Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if not callable(reconf):
            continue
        try:
            reconf(encoding="utf-8", errors="replace")
            continue
        except Exception:
            pass
        try:
            reconf(errors="replace")
        except Exception:
            pass


def _install_safe_print() -> None:
    """Dernier filet : un print() ne doit jamais faire planter le classement."""
    import builtins

    current = builtins.print
    if getattr(current, "_galerie_cp1252_safe", False):
        return

    def safe_print(*args, **kwargs):
        try:
            current(*args, **kwargs)
        except UnicodeEncodeError:
            file = kwargs.get("file")
            if file is None:
                file = sys.stdout
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            flush = bool(kwargs.get("flush", False))
            text = sep.join(str(a) for a in args) + end
            encoding = getattr(file, "encoding", None) or "utf-8"
            data = text.encode(encoding, errors="replace")
            buf = getattr(file, "buffer", None)
            if buf is not None:
                buf.write(data)
                if flush:
                    try:
                        buf.flush()
                    except Exception:
                        pass
            else:
                current(
                    data.decode(encoding, errors="replace"),
                    end="",
                    file=file,
                    flush=flush,
                )

    safe_print._galerie_cp1252_safe = True  # type: ignore[attr-defined]
    builtins.print = safe_print  # type: ignore[misc]


_configure_stdio()
_install_safe_print()


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    _install_safe_print()
    if argv is None:
        reexec_venv()
    args = parse_args(argv)
    library = args.library.expanduser()
    if not library.is_dir():
        print(f"Bibliothèque introuvable : {library}", file=sys.stderr)
        return 1

    index_path, index_where = resolve_index_path(library, args.index)
    live_msg = (
        "conservées (--keep-live)"
        if args.keep_live
        else "suppression des .MOV compagnons (la photo reste)"
    )

    if args.facebook:
        facebook_root = args.facebook_dir.expanduser()
        if not facebook_root.is_dir():
            print(f"Dossier Facebook introuvable : {facebook_root}", file=sys.stderr)
            return 1
        print(f"Bibliothèque : {library}")
        print(f"Facebook     : {facebook_root}")
        print(f"Index        : {index_path} ({index_where})")
        print("Mode         : " + ("APPLICATION (copie / suppression)" if args.apply else "simulation (dry-run)"))
        print("Dates        : message_*.json (creation_timestamp / timestamp_ms)")
        print("Cible        : Annee YYYY / Mois YYYY  (Ville si GPS EXIF ou JSON)")
        print()
        index = Index(index_path)
        try:
            geocoder = Geocoder(index)
            print("=== facebook ===")
            stats = process_facebook(
                library=library,
                facebook_root=facebook_root,
                geocoder=geocoder,
                apply=args.apply,
                limit=args.limit,
                verbose=args.verbose,
                year=args.year,
            )
            print_facebook_stats(stats, args.apply)
            print()
        finally:
            index.close()
        if not args.apply:
            print("Aucun fichier copié ni supprimé. Relancer avec --apply pour écrire.")
        return 0

    if args.triage:
        triage_root = args.triage_dir.expanduser()
        if not triage_root.is_dir():
            print(f"Triage introuvable : {triage_root}", file=sys.stderr)
            return 1
        years = list_triage_years(triage_root, None if args.year is None else args.year)
        if not years:
            cible = f"année {args.year}" if args.year is not None else "aucune année"
            print(f"Aucun dossier {cible} dans {triage_root}")
            return 1
        print(f"Bibliothèque : {library}")
        print(f"Triage       : {triage_root}")
        print(f"Index        : {index_path} ({index_where})")
        print("Mode         : " + ("APPLICATION (copie / suppression)" if args.apply else "simulation (dry-run)"))
        print("Live Photos  : " + live_msg)
        print()
        index = Index(index_path)
        try:
            geocoder = Geocoder(index)
            for year in years:
                print(f"=== triage {year} ===")
                stats = process_triage_year(
                    library=library,
                    triage_root=triage_root,
                    year=year,
                    geocoder=geocoder,
                    apply=args.apply,
                    limit=args.limit,
                    verbose=args.verbose,
                    delete_live=not args.keep_live,
                )
                print_triage_stats(year, stats, args.apply)
                print()
        finally:
            index.close()
        if not args.apply:
            print("Aucun fichier copié ni supprimé. Relancer avec --apply pour écrire.")
        return 0

    try:
        dirs = year_dirs(library, None if args.all else args.year)
    except OSError as exc:
        print(f"Impossible de lister {library}: {exc}", file=sys.stderr)
        return 1
    year_filter = None if args.all else args.year
    loose_by_year = collect_loose_media(library, year_filter)
    if not dirs and not loose_by_year:
        cible = "toutes les années" if args.all else f"année {args.year}"
        print(f"Aucun dossier année ni média en vrac pour {cible} dans {library}")
        return 1

    print(f"Bibliothèque : {library}")
    print(f"Index        : {index_path} ({index_where})")
    print("Mode         : " + ("APPLICATION (déplacements)" if args.apply else "simulation (dry-run)"))
    print("Live Photos  : " + live_msg)
    print("Périmètre    : vrac + racine année + dossiers mois (Annee/Mois -> ville si GPS)")
    print()

    index = Index(index_path)
    try:
        if args.reset_index:
            if args.all:
                deleted = index.conn.execute("DELETE FROM files").rowcount
                index.conn.commit()
            else:
                deleted = 0
                for year_dir in dirs:
                    deleted += index.reset_prefix(year_dir.name)
                if year_filter is not None:
                    deleted += index.reset_prefix(f"Annee {year_filter}")
            print(f"Index réinitialisé ({deleted} entrées supprimées).")
            print()

        geocoder = Geocoder(index)
        if args.all:
            year_list = sorted(
                {
                    int(match.group(1))
                    for d in dirs
                    if (match := YEAR_DIR_RE.match(d.name))
                }
                | set(loose_by_year)
            )
        else:
            year_list = [int(args.year)]

        for year in year_list:
            existing = resolve_year_dir(library, year, create=False)
            leftover = root_media_files(existing) if existing.is_dir() else []
            if leftover:
                print(f"=== {existing.name} ===")
                stats = process_year(
                    library=library,
                    year_dir=existing,
                    index=index,
                    geocoder=geocoder,
                    apply=args.apply,
                    limit=args.limit,
                    verbose=args.verbose,
                    delete_live=not args.keep_live,
                )
                print_stats(existing, stats, args.apply)
                print()
            year_dir = resolve_year_dir(library, year, create=args.apply)
            loose = loose_by_year.get(year, [])
            if loose:
                print(f"=== vrac -> Annee {year} ===")
                stats = process_year(
                    library=library,
                    year_dir=year_dir,
                    index=index,
                    geocoder=geocoder,
                    apply=args.apply,
                    limit=args.limit,
                    verbose=args.verbose,
                    delete_live=not args.keep_live,
                    files=loose,
                    move_no_gps=True,
                )
                print_stats(year_dir, stats, args.apply)
                print()
    finally:
        index.close()

    if not args.apply:
        print("Aucun fichier déplacé ni supprimé. Relancer avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
