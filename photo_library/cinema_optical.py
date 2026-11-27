"""Support DVD (VIDEO_TS / ISO), Blu-ray (BDMV / ISO) et lecteur optique natif optionnel."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from photo_library.cinema_probe import (
    MediaProbe,
    parse_ffmpeg_stderr,
    parse_ffprobe_json,
    probe_media,
)
from photo_library.ffmpeg_util import cinema_ffmpeg_bin, ffmpeg_capabilities, ffprobe_bin

_ENCRYPT_MARKERS = (
    "aacs",
    "bd+",
    "libdvdcss",
    "encrypted",
    "scrambled",
    "css",
    "copy protection",
    "media key",
    "vuk",
)
_VOB_MAIN_RE = re.compile(r"^vts_(\d{2})_([1-9])\.vob$", re.IGNORECASE)
_MPLS_RE = re.compile(r"^(\d{5})\.mpls$", re.IGNORECASE)


@dataclass(frozen=True)
class OpticalTitle:
    index: int
    label: str
    duration_s: float | None
    input_args: tuple[str, ...]
    probe: MediaProbe | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "label": self.label,
            "duration_s": round(self.duration_s, 3) if self.duration_s is not None else None,
            "audio_tracks": [a.to_dict() for a in (self.probe.audio_tracks if self.probe else ())],
            "subtitle_tracks": [s.to_dict() for s in (self.probe.subtitle_tracks if self.probe else ())],
            "chapters": [c.to_dict() for c in (self.probe.chapters if self.probe else ())],
        }


def _looks_encrypted(stderr_text: str) -> bool:
    low = (stderr_text or "").lower()
    return any(marker in low for marker in _ENCRYPT_MARKERS)


def _probe_with_args(input_args: list[str], *, timeout: int = 20) -> tuple[MediaProbe, str]:
    fp = ffprobe_bin()
    if fp:
        cmd = [
            fp,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            *input_args,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
            err = proc.stderr.decode("utf-8", "replace")
            if proc.returncode == 0 and proc.stdout:
                parsed = parse_ffprobe_json(json.loads(proc.stdout.decode("utf-8", "replace")))
                if parsed.readable:
                    return parsed, err
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass

    ff = cinema_ffmpeg_bin()
    try:
        proc = subprocess.run(
            [ff, "-hide_banner", "-nostdin", *input_args],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        err = proc.stderr.decode("utf-8", "replace")
        return parse_ffmpeg_stderr(err), err
    except (OSError, subprocess.SubprocessError) as exc:
        return MediaProbe(readable=False), str(exc)


def _dvd_root(path: Path) -> Path:
    if path.is_dir() and path.name.lower() == "video_ts":
        return path.parent
    return path


def _bluray_root(path: Path) -> Path:
    if path.is_dir() and path.name.lower() == "bdmv":
        return path.parent
    return path


def _vob_fallback_titles(root: Path) -> list[OpticalTitle]:
    vts_dir = root / "VIDEO_TS"
    if not vts_dir.is_dir():
        for child in root.iterdir() if root.is_dir() else ():
            if child.is_dir() and child.name.lower() == "video_ts":
                vts_dir = child
                break
    if not vts_dir.is_dir():
        return []

    groups: dict[str, list[Path]] = {}
    for p in sorted(vts_dir.iterdir()):
        if not p.is_file():
            continue
        m = _VOB_MAIN_RE.match(p.name)
        if m:
            groups.setdefault(m.group(1), []).append(p)

    titles: list[OpticalTitle] = []
    for tnum, files in sorted(groups.items()):
        concat_arg = "concat:" + "|".join(str(f) for f in files) if len(files) > 1 else str(files[0])
        probe = probe_media(files[0], timeout=15)
        if not probe.readable:
            continue
        est_dur = probe.duration_s
        if est_dur and len(files) > 1:
            total_bytes = sum(f.stat().st_size for f in files)
            first_bytes = max(1, files[0].stat().st_size)
            est_dur = est_dur * (total_bytes / first_bytes)
        titles.append(
            OpticalTitle(
                index=int(tnum),
                label=f"Titre {int(tnum)}",
                duration_s=est_dur,
                input_args=("-i", concat_arg),
                probe=probe,
            )
        )
    return titles


def inspect_dvd(path: Path, *, max_titles: int = 8) -> dict[str, Any]:
    """Liste les titres d’un DVD (VIDEO_TS, ISO ou lecteur physique) via FFmpeg dvdvideo ou VOB."""
    root = _dvd_root(path)
    caps = ffmpeg_capabilities()
    titles: list[OpticalTitle] = []
    encrypted = False

    if caps.get("dvdvideo"):
        misses = 0
        for idx in range(1, max_titles + 1):
            in_args = ["-f", "dvdvideo", "-title", str(idx), "-i", str(root)]
            probe, err = _probe_with_args(in_args, timeout=15)
            if _looks_encrypted(err):
                encrypted = True
            if probe.readable:
                misses = 0
                titles.append(
                    OpticalTitle(
                        index=idx,
                        label=f"Titre {idx}",
                        duration_s=probe.duration_s,
                        input_args=tuple(in_args),
                        probe=probe,
                    )
                )
            else:
                misses += 1
                if misses >= 2 and titles:
                    break
                if idx == 1 and encrypted:
                    break

    if not titles and root.is_dir():
        titles = _vob_fallback_titles(root)

    default_idx = titles[0].index if titles else 1
    if titles:
        best = max(titles, key=lambda t: t.duration_s or 0.0)
        default_idx = best.index

    return {
        "kind": "dvd",
        "path": str(root),
        "readable": bool(titles),
        "encrypted": encrypted and not titles,
        "encryption_hint": (
            "Disque DVD protégé (CSS). Installez la bibliothèque système optionnelle libdvdcss si autorisé dans votre pays."
            if (encrypted and not titles)
            else ""
        ),
        "default_title": default_idx,
        "titles": titles,
    }


def _m2ts_fallback_titles(root: Path) -> list[OpticalTitle]:
    bdmv = root / "BDMV"
    stream_dir = bdmv / "STREAM"
    if not stream_dir.is_dir():
        return []
    m2ts_files = sorted(
        (p for p in stream_dir.iterdir() if p.is_file() and p.suffix.lower() == ".m2ts"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )[:6]
    titles: list[OpticalTitle] = []
    for idx, fpath in enumerate(m2ts_files, start=1):
        probe = probe_media(fpath, timeout=15)
        if not probe.readable:
            continue
        titles.append(
            OpticalTitle(
                index=idx,
                label=f"Flux {fpath.stem}",
                duration_s=probe.duration_s,
                input_args=("-i", str(fpath)),
                probe=probe,
            )
        )
    return titles


def inspect_bluray(path: Path, *, max_titles: int = 8) -> dict[str, Any]:
    """Liste les titres/playlists d’un Blu-ray (BDMV, ISO ou lecteur physique)."""
    root = _bluray_root(path)
    caps = ffmpeg_capabilities()
    titles: list[OpticalTitle] = []
    encrypted = False

    if caps.get("bluray"):
        playlist_ids: list[int] = []
        pl_dir = root / "BDMV" / "PLAYLIST"
        if pl_dir.is_dir():
            for p in sorted(pl_dir.iterdir()):
                m = _MPLS_RE.match(p.name)
                if m:
                    playlist_ids.append(int(m.group(1)))
        if not playlist_ids:
            playlist_ids = list(range(0, min(max_titles, 5)))
        else:
            playlist_ids = playlist_ids[:max_titles]

        for pl in playlist_ids:
            in_args = ["-playlist", str(pl), "-i", f"bluray:{root}"]
            probe, err = _probe_with_args(in_args, timeout=15)
            if _looks_encrypted(err):
                encrypted = True
            if probe.readable:
                titles.append(
                    OpticalTitle(
                        index=pl,
                        label=f"Playlist {pl:05d}",
                        duration_s=probe.duration_s,
                        input_args=tuple(in_args),
                        probe=probe,
                    )
                )
            elif encrypted and not titles:
                break

    if not titles and root.is_dir():
        titles = _m2ts_fallback_titles(root)

    default_idx = titles[0].index if titles else 0
    if titles:
        best = max(titles, key=lambda t: t.duration_s or 0.0)
        default_idx = best.index

    return {
        "kind": "bluray",
        "path": str(root),
        "readable": bool(titles),
        "encrypted": encrypted and not titles,
        "encryption_hint": (
            "Disque Blu-ray protégé (AACS/BD+). Installez les bibliothèques système optionnelles libbluray/libaacs si nécessaire."
            if (encrypted and not titles)
            else ""
        ),
        "default_title": default_idx,
        "titles": titles,
    }


def detect_optical_kind(path: Path) -> str:
    """Identifie bluray, dvd, data ou missing pour un chemin ou périphérique optique."""
    try:
        if not path.exists():
            return "missing"
    except OSError:
        return "missing"

    if path.is_dir():
        try:
            children = {c.name.lower() for c in path.iterdir()}
        except OSError:
            return "missing"
        if "bdmv" in children or path.name.lower() == "bdmv":
            return "bluray"
        if "video_ts" in children or path.name.lower() == "video_ts":
            return "dvd"
        return "data"

    if path.suffix.lower() == ".iso":
        # Heuristique rapide UDF Blu-ray vs DVD sur les premiers secteurs
        try:
            with path.open("rb") as fh:
                head = fh.read(512 * 1024)
            if b"BDMV" in head or b"HDMV" in head:
                return "bluray"
        except OSError:
            pass
        return "dvd"

    # Périphérique bloc (ex. /dev/sr0 sous Linux)
    if os.path.exists(path):
        return "dvd"
    return "missing"


def inspect_optical_source(path: Path, *, hint_kind: str | None = None) -> dict[str, Any]:
    kind = hint_kind if hint_kind in {"dvd", "bluray"} else detect_optical_kind(path)
    if kind == "bluray":
        info = inspect_bluray(path)
        if not info["readable"] and hint_kind is None:
            alt = inspect_dvd(path)
            if alt["readable"]:
                return alt
        return info
    if kind == "dvd":
        info = inspect_dvd(path)
        if not info["readable"] and hint_kind is None and not path.is_dir():
            alt = inspect_bluray(path)
            if alt["readable"]:
                return alt
        return info
    if kind == "data":
        from photo_library.cinema_scan import CINEMA_VIDEO_SUFFIXES

        files = sorted(
            p
            for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in CINEMA_VIDEO_SUFFIXES
        )[:30]
        titles: list[OpticalTitle] = []
        for idx, fpath in enumerate(files, start=1):
            probe = probe_media(fpath, timeout=10)
            if probe.readable:
                titles.append(
                    OpticalTitle(
                        index=idx,
                        label=fpath.name,
                        duration_s=probe.duration_s,
                        input_args=("-i", str(fpath)),
                        probe=probe,
                    )
                )
        return {
            "kind": "data",
            "path": str(path),
            "readable": bool(titles),
            "encrypted": False,
            "encryption_hint": "",
            "default_title": titles[0].index if titles else 1,
            "titles": titles,
        }
    return {
        "kind": "missing",
        "path": str(path),
        "readable": False,
        "encrypted": False,
        "encryption_hint": "",
        "default_title": 0,
        "titles": [],
    }


def resolve_optical_title(
    path: Path,
    *,
    hint_kind: str | None = None,
    title_index: int | None = None,
) -> tuple[OpticalTitle, dict[str, Any]]:
    info = inspect_optical_source(path, hint_kind=hint_kind)
    titles: list[OpticalTitle] = info["titles"]
    if not titles:
        msg = info.get("encryption_hint") or f"Aucun titre vidéo lisible dans {path}"
        raise ValueError(msg)
    if title_index is not None:
        for t in titles:
            if t.index == int(title_index):
                return t, info
    for t in titles:
        if t.index == info["default_title"]:
            return t, info
    return titles[0], info


def inspect_configured_disc(optical_device: str) -> dict[str, Any]:
    """Vérifie le lecteur optique configuré ; ne touche aucun matériel si le champ est vide."""
    raw = str(optical_device or "").strip()
    if not raw:
        return {
            "configured": False,
            "present": False,
            "device": "",
            "kind": "none",
            "readable": False,
            "encrypted": False,
            "encryption_hint": "",
            "default_title": 0,
            "titles": [],
        }
    path = Path(raw).expanduser()
    if not path.exists():
        return {
            "configured": True,
            "present": False,
            "device": str(path),
            "kind": "missing",
            "readable": False,
            "encrypted": False,
            "encryption_hint": "",
            "default_title": 0,
            "titles": [],
        }
    info = inspect_optical_source(path)
    return {
        "configured": True,
        "present": info["kind"] != "missing",
        "device": str(path),
        "kind": info["kind"],
        "readable": info["readable"],
        "encrypted": info["encrypted"],
        "encryption_hint": info["encryption_hint"],
        "default_title": info["default_title"],
        "titles": [t.to_dict() for t in info["titles"]],
    }
