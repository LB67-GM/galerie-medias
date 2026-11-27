"""Analyse vidéo (ffprobe / ffmpeg), extraction WebVTT et vignettes Cinéma."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from photo_library.ffmpeg_util import cinema_ffmpeg_bin, ffprobe_bin

TEXT_SUB_CODECS = frozenset(
    {
        "subrip",
        "srt",
        "ass",
        "ssa",
        "webvtt",
        "mov_text",
        "text",
        "ttml",
        "sami",
        "microdvd",
        "mpl2",
    }
)
IMAGE_SUB_CODECS = frozenset(
    {
        "dvd_subtitle",
        "hdmv_pgs_subtitle",
        "pgssub",
        "dvb_subtitle",
        "xsub",
    }
)
POSTER_NAMES = ("poster.jpg", "poster.jpeg", "poster.png", "poster.webp", "folder.jpg", "cover.jpg")
POSTER_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VID_RE = re.compile(r"Stream #\d+:(\d+)[^:]*:\s*Video:\s*([A-Za-z0-9_]+)(.*)")
_AUD_RE = re.compile(r"Stream #\d+:(\d+)(?:\[[^\]]*\])?(?:\(([^)]+)\))?[^:]*:\s*Audio:\s*([A-Za-z0-9_]+)(.*)")
_SUB_RE = re.compile(r"Stream #\d+:(\d+)(?:\[[^\]]*\])?(?:\(([^)]+)\))?[^:]*:\s*Subtitle:\s*([A-Za-z0-9_]+)(.*)")
_DIM_RE = re.compile(r"\b(\d{2,5})x(\d{2,5})\b")
_PIX_RE = re.compile(r"\b(yuv[\w]+|nv12|nv21|rgb\w+|bgr\w+)\b")


@dataclass(frozen=True)
class AudioTrack:
    index: int
    stream_index: int
    codec: str
    language: str = ""
    title: str = ""
    channels: int = 2
    default: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "stream_index": self.stream_index,
            "codec": self.codec,
            "language": self.language,
            "title": self.title,
            "channels": self.channels,
            "default": self.default,
        }


@dataclass(frozen=True)
class SubtitleTrack:
    index: int
    stream_index: int
    codec: str
    language: str = ""
    title: str = ""
    is_text: bool = True
    default: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "stream_index": self.stream_index,
            "codec": self.codec,
            "language": self.language,
            "title": self.title,
            "is_text": self.is_text,
            "default": self.default,
        }


@dataclass(frozen=True)
class ChapterInfo:
    index: int
    start_s: float
    end_s: float
    title: str

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_s": round(self.start_s, 3),
            "end_s": round(self.end_s, 3),
            "title": self.title,
        }


@dataclass(frozen=True)
class MediaProbe:
    readable: bool
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    video_codec: str = ""
    pix_fmt: str = ""
    audio_tracks: tuple[AudioTrack, ...] = field(default_factory=tuple)
    subtitle_tracks: tuple[SubtitleTrack, ...] = field(default_factory=tuple)
    chapters: tuple[ChapterInfo, ...] = field(default_factory=tuple)
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "readable": self.readable,
            "duration_s": round(self.duration_s, 3) if self.duration_s is not None else None,
            "width": self.width,
            "height": self.height,
            "video_codec": self.video_codec,
            "pix_fmt": self.pix_fmt,
            "audio_tracks": [a.to_dict() for a in self.audio_tracks],
            "subtitle_tracks": [s.to_dict() for s in self.subtitle_tracks],
            "chapters": [c.to_dict() for c in self.chapters],
            "tags": dict(self.tags),
        }


def _safe_float(val: object) -> float | None:
    try:
        out = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if out < 0 or out != out:
        return None
    return out


def parse_ffprobe_json(raw: dict) -> MediaProbe:
    if not isinstance(raw, dict):
        return MediaProbe(readable=False)
    fmt = raw.get("format") or {}
    streams = raw.get("streams") or []
    chapters_raw = raw.get("chapters") or []

    duration_s = _safe_float(fmt.get("duration"))
    width: int | None = None
    height: int | None = None
    video_codec = ""
    pix_fmt = ""
    audio_tracks: list[AudioTrack] = []
    subtitle_tracks: list[SubtitleTrack] = []

    for st in streams:
        if not isinstance(st, dict):
            continue
        kind = str(st.get("codec_type") or "").lower()
        codec = str(st.get("codec_name") or "").lower()
        sidx = int(st.get("index") or 0)
        st_tags = st.get("tags") or {}
        lang = str(st_tags.get("language") or st_tags.get("LANGUAGE") or "").strip().lower()
        if lang == "und":
            lang = ""
        title = str(st_tags.get("title") or st_tags.get("TITLE") or "").strip()
        disp = st.get("disposition") or {}
        is_def = bool(disp.get("default"))

        if kind == "video" and not video_codec:
            if disp.get("attached_pic"):
                continue
            video_codec = codec
            pix_fmt = str(st.get("pix_fmt") or "").lower()
            try:
                width = int(st.get("width") or 0) or None
                height = int(st.get("height") or 0) or None
            except (TypeError, ValueError):
                width, height = None, None
            if duration_s is None:
                duration_s = _safe_float(st.get("duration"))
        elif kind == "audio":
            try:
                ch = int(st.get("channels") or 2)
            except (TypeError, ValueError):
                ch = 2
            audio_tracks.append(
                AudioTrack(
                    index=len(audio_tracks),
                    stream_index=sidx,
                    codec=codec,
                    language=lang,
                    title=title,
                    channels=ch,
                    default=is_def,
                )
            )
        elif kind == "subtitle":
            is_text = codec in TEXT_SUB_CODECS or (
                codec not in IMAGE_SUB_CODECS and "pgs" not in codec and "dvd" not in codec
            )
            subtitle_tracks.append(
                SubtitleTrack(
                    index=len(subtitle_tracks),
                    stream_index=sidx,
                    codec=codec,
                    language=lang,
                    title=title,
                    is_text=is_text,
                    default=is_def,
                )
            )

    if not video_codec:
        return MediaProbe(readable=False)

    chapters: list[ChapterInfo] = []
    for i, ch in enumerate(chapters_raw):
        if not isinstance(ch, dict):
            continue
        start = _safe_float(ch.get("start_time")) or 0.0
        end = _safe_float(ch.get("end_time")) or start
        ctags = ch.get("tags") or {}
        ctitle = str(ctags.get("title") or f"Chapitre {i + 1}").strip()
        chapters.append(ChapterInfo(index=i, start_s=start, end_s=end, title=ctitle))

    tags_out: dict[str, str] = {}
    fmt_tags = fmt.get("tags") or {}
    if isinstance(fmt_tags, dict):
        for k, v in fmt_tags.items():
            if isinstance(k, str) and isinstance(v, str) and v.strip():
                tags_out[k.lower()] = v.strip()

    return MediaProbe(
        readable=True,
        duration_s=duration_s,
        width=width,
        height=height,
        video_codec=video_codec,
        pix_fmt=pix_fmt,
        audio_tracks=tuple(audio_tracks),
        subtitle_tracks=tuple(subtitle_tracks),
        chapters=tuple(chapters),
        tags=tags_out,
    )


def parse_ffmpeg_stderr(text: str) -> MediaProbe:
    low = text.lower()
    if "moov atom not found" in low or "invalid data found when processing input" in low:
        return MediaProbe(readable=False)
    duration_s: float | None = None
    dm = _DUR_RE.search(text)
    if dm:
        duration_s = int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3))

    video_codec = ""
    pix_fmt = ""
    width: int | None = None
    height: int | None = None
    audio_tracks: list[AudioTrack] = []
    subtitle_tracks: list[SubtitleTrack] = []

    for line in text.splitlines():
        vm = _VID_RE.search(line)
        if vm and not video_codec:
            rest = vm.group(3)
            if "attached pic" in rest.lower():
                continue
            video_codec = vm.group(2).lower()
            dim = _DIM_RE.search(rest)
            if dim:
                width, height = int(dim.group(1)), int(dim.group(2))
            pm = _PIX_RE.search(rest)
            if pm:
                pix_fmt = pm.group(1).lower()
            continue
        am = _AUD_RE.search(line)
        if am:
            lang = (am.group(2) or "").strip().lower()
            if lang == "und":
                lang = ""
            rest = am.group(4).lower()
            ch = 6 if "5.1" in rest else (1 if "mono" in rest else 2)
            audio_tracks.append(
                AudioTrack(
                    index=len(audio_tracks),
                    stream_index=int(am.group(1)),
                    codec=am.group(3).lower(),
                    language=lang,
                    channels=ch,
                    default=len(audio_tracks) == 0,
                )
            )
            continue
        sm = _SUB_RE.search(line)
        if sm:
            lang = (sm.group(2) or "").strip().lower()
            if lang == "und":
                lang = ""
            codec = sm.group(3).lower()
            is_text = codec in TEXT_SUB_CODECS or codec not in IMAGE_SUB_CODECS
            subtitle_tracks.append(
                SubtitleTrack(
                    index=len(subtitle_tracks),
                    stream_index=int(sm.group(1)),
                    codec=codec,
                    language=lang,
                    is_text=is_text,
                )
            )

    if not video_codec:
        return MediaProbe(readable=False)
    return MediaProbe(
        readable=True,
        duration_s=duration_s,
        width=width,
        height=height,
        video_codec=video_codec,
        pix_fmt=pix_fmt,
        audio_tracks=tuple(audio_tracks),
        subtitle_tracks=tuple(subtitle_tracks),
    )


def probe_media(path: Path, *, timeout: int = 30) -> MediaProbe:
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
            str(path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout.decode("utf-8", "replace"))
                parsed = parse_ffprobe_json(data)
                if parsed.readable:
                    return parsed
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass

    ff = cinema_ffmpeg_bin()
    try:
        proc = subprocess.run(
            [ff, "-hide_banner", "-nostdin", "-i", str(path)],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return parse_ffmpeg_stderr(proc.stderr.decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError):
        return MediaProbe(readable=False)


def extract_subtitle_vtt(src: Path, sub_index: int, dest: Path) -> Path:
    """Extrait une piste de sous-titres texte vers un fichier WebVTT."""
    if dest.is_file() and dest.stat().st_size > 16:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.tmp.vtt")
    cmd = [
        cinema_ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(src),
        "-map",
        f"0:s:{int(sub_index)}",
        "-c:s",
        "webvtt",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 10:
        tmp.unlink(missing_ok=True)
        raise ValueError("sous-titres non extractibles en WebVTT")
    tmp.replace(dest)
    return dest


def find_sibling_poster(src: Path) -> Path | None:
    if src.is_dir():
        for name in POSTER_NAMES:
            cand = src / name
            if cand.is_file():
                return cand
        return None
    for ext in POSTER_SUFFIXES:
        cand = src.with_suffix(ext)
        if cand.is_file():
            return cand
    parent = src.parent
    for name in POSTER_NAMES:
        cand = parent / name
        if cand.is_file():
            return cand
    return None


def make_cinema_poster(src: Path, dest: Path, *, duration_s: float | None = None) -> bool:
    """Copie l’affiche locale si présente, sinon capture une image nette via ffmpeg."""
    if dest.is_file() and dest.stat().st_size > 256:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    sibling = find_sibling_poster(src)
    if sibling is not None:
        try:
            from PIL import Image

            with Image.open(sibling) as img:
                img = img.convert("RGB")
                img.thumbnail((480, 720))
                tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.tmp.jpg")
                img.save(tmp, format="JPEG", quality=84)
                tmp.replace(dest)
                return True
        except Exception:
            try:
                shutil.copy2(sibling, dest)
                return True
            except OSError:
                pass

    if not src.is_file():
        return False

    offsets: list[float] = []
    if duration_s and duration_s > 20:
        offsets.append(min(max(duration_s * 0.15, 5.0), 180.0))
    elif duration_s and duration_s > 2:
        offsets.append(duration_s * 0.25)
    offsets.append(0.5)
    offsets.append(0.0)

    ff = cinema_ffmpeg_bin()
    tmp = dest.with_name(f"{dest.stem}.{os.getpid()}.tmp.jpg")
    for sec in offsets:
        cmd = [
            ff,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-ss",
            f"{sec:.2f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-vf",
            "scale=480:-2:force_original_aspect_ratio=decrease",
            "-q:v",
            "4",
            str(tmp),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=45, check=False)
        except (OSError, subprocess.SubprocessError):
            tmp.unlink(missing_ok=True)
            return False
        if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 256:
            tmp.replace(dest)
            return True
        tmp.unlink(missing_ok=True)
    return False
