from __future__ import annotations

from pathlib import Path

DEFAULT_LIBRARY = Path.home() / "Photos"
DEFAULT_CACHE = Path.home() / ".cache" / "photo-library"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
CAST_HTTP_PORT = 8766

THUMB_MAX_SIDE = 360
PREVIEW_MAX_SIDE = 1600
FACE_THUMB_SIZE = 160
JPEG_QUALITY = 82

IMAGE_SUFFIXES = {
    ".heic",
    ".heif",
    ".hif",
    ".jpg",
    ".jpeg",
    ".png",
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
    ".webp",
    ".bmp",
    ".gif",
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
MEDIA_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES

SKIP_DIR_NAMES = {
    "_syncapp",
    "__macosx",
    ".trash",
    ".corbeille",
    "corbeille",
    "@eadir",
    ".photo-sort-lieux",
}

YEAR_DIR_RE = r"^annee[ _-](\d{4})$"
