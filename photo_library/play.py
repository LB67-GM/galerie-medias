"""Lecture navigateur : H.264 tel quel, sinon conversion ffmpeg (pas VLC)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from photo_library.ffmpeg_util import ffmpeg_bin

_VIDEO_RE = re.compile(r"Video:\s*([A-Za-z0-9_]+)")
_AUDIO_RE = re.compile(r"Audio:\s*([A-Za-z0-9_]+)")
_PIX_RE = re.compile(r"Video:.*?(yuv[\w]+|nv12|nv21)", re.DOTALL)

SAFE_VIDEO = {"h264"}
SAFE_PIX = {"", "yuv420p", "yuvj420p", "nv12"}
SAFE_AUDIO = {"", "aac", "mp3", "opus"}


@dataclass(frozen=True)
class Probe:
    readable: bool
    video_codec: str = ""
    pix_fmt: str = ""
    audio_codec: str = ""


def parse_probe_text(text: str) -> Probe:
    low = text.lower()
    if "moov atom not found" in low or "invalid data found when processing input" in low:
        return Probe(readable=False)
    video = _VIDEO_RE.search(text)
    if video is None:
        return Probe(readable=False)
    pix_m = _PIX_RE.search(text)
    audio = _AUDIO_RE.search(text)
    return Probe(
        readable=True,
        video_codec=video.group(1).lower(),
        pix_fmt=(pix_m.group(1).lower() if pix_m else ""),
        audio_codec=(audio.group(1).lower() if audio else ""),
    )


def probe_video(path: Path) -> Probe:
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return parse_probe_text(proc.stderr.decode("utf-8", "replace"))


def browser_safe(info: Probe) -> bool:
    if not info.readable or info.video_codec not in SAFE_VIDEO:
        return False
    if info.pix_fmt not in SAFE_PIX:
        return False
    if info.audio_codec not in SAFE_AUDIO:
        return False
    return True


def cached_play_path(cache: Path, media_id: int, size: int, mtime_ns: int) -> Path:
    return cache / "play" / f"{int(media_id)}-{int(size)}-{int(mtime_ns)}.mp4"


def cinema_tv_path(cache: Path, item_id: int, size: int, mtime_ns: int) -> Path:
    """MP4 préparé pour la télé. Le suffixe change si le format TV change, pour ne pas réutiliser un ancien fichier."""
    return cache / "cinema_cast" / f"{int(item_id)}-{int(size)}-{int(mtime_ns)}-tv720.mp4"


def _scale_vf() -> str:
    return "scale=-2:'min(720,ih)',format=yuv420p"


def _tv_scale_vf() -> str:
    """1280x720, H.264 Main : le profil DLNA que lisent les télés LG et Samsung."""
    return (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
        "format=yuv420p"
    )


def remux_copy_mp4(src: Path, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.remux.mp4")
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(src),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 64:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def ensure_play_mp4(
    src: Path, dest: Path, *, preset: str = "veryfast", for_tv: bool = False
) -> Path:
    """MP4 H.264/AAC dans le cache (navigateur et TV DLNA). HEVC iPhone inclus.

    for_tv convertit toujours : la copie telle quelle garde un profil (4K, High, niveau élevé)
    que la télévision refuse avec « format non pris en charge ».
    """
    if dest.is_file() and dest.stat().st_size > 512:
        return dest
    info = probe_video(src)
    if not info.readable:
        raise ValueError("vidéo illisible")
    if not for_tv and browser_safe(info):
        if src.suffix.lower() in {".mp4", ".m4v"}:
            if remux_copy_mp4(src, dest) and dest.is_file() and dest.stat().st_size > 512:
                return dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if dest.is_file() and dest.stat().st_size > 512:
                return dest
        if remux_copy_mp4(src, dest) and dest.is_file() and dest.stat().st_size > 512:
            return dest
    if transcode_to_file(src, dest, preset=preset, for_tv=for_tv) and dest.is_file() and dest.stat().st_size > 512:
        return dest
    raise ValueError("conversion impossible")


def transcode_to_file(src: Path, dest: Path, *, preset: str = "veryfast", for_tv: bool = False) -> bool:
    """H.264 + AAC, 720p max, MP4 faststart — lisible dans Chrome/Firefox/Safari."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.tmp.mp4")
    try:
        for with_audio in (True, False):
            cmd = [
                ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(src),
                "-map",
                "0:v:0",
            ]
            if with_audio:
                cmd += ["-map", "0:a:0?"]
            else:
                cmd += ["-an"]
            if for_tv:
                cmd += [
                    "-vf",
                    _tv_scale_vf(),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "superfast",
                    "-crf",
                    "23",
                    "-profile:v",
                    "main",
                    "-level:v",
                    "4.0",
                    "-pix_fmt",
                    "yuv420p",
                    "-tag:v",
                    "avc1",
                ]
            else:
                cmd += [
                    "-vf",
                    _scale_vf(),
                    "-c:v",
                    "libx264",
                    "-preset",
                    preset,
                    "-crf",
                    "23",
                    "-profile:v",
                    "high",
                    "-pix_fmt",
                    "yuv420p",
                ]
            if with_audio:
                cmd += ["-c:a", "aac", "-ac", "2", "-b:a", "128k"]
                if for_tv:
                    cmd += ["-profile:a", "aac_low", "-ar", "48000"]
                else:
                    cmd += ["-ar", "44100"]
            cmd += [
                "-max_muxing_queue_size",
                "1024",
                "-movflags",
                "+faststart",
                str(tmp),
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=1800, check=False)
            if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 512:
                tmp.replace(dest)
                return True
            tmp.unlink(missing_ok=True)
        return False
    finally:
        tmp.unlink(missing_ok=True)
