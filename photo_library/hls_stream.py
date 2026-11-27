"""Gestionnaire de sessions HLS à la volée (remux rapide ou transcodage FFmpeg)."""

from __future__ import annotations

import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from photo_library.cinema_probe import MediaProbe, probe_media
from photo_library.ffmpeg_util import cinema_ffmpeg_bin

HLS_SAFE_VIDEO = frozenset({"h264"})
HLS_SAFE_PIX = frozenset({"", "yuv420p", "yuvj420p", "nv12"})
HLS_SAFE_AUDIO = frozenset({"", "aac", "mp3"})

SEGMENT_SEC = 4
IDLE_TTL_S = 15 * 60
MAX_SESSIONS = 4


@dataclass
class HlsSession:
    sid: str
    item_key: str
    src: Path
    directory: Path
    proc: subprocess.Popen[bytes]
    start_s: float
    duration_s: float | None
    quality: str
    remux: bool
    created_at: float
    last_access: float


def _quality_scale(quality: str) -> str | None:
    if quality == "720p":
        return "scale=-2:'min(720,ih)',format=yuv420p"
    if quality == "1080p":
        return "scale=-2:'min(1080,ih)',format=yuv420p"
    if quality == "480p":
        return "scale=-2:'min(480,ih)',format=yuv420p"
    return "scale=-2:'min(1080,ih)',format=yuv420p"


def can_remux_hls(info: MediaProbe, *, audio_idx: int | None, quality: str) -> bool:
    if quality in {"720p", "480p"}:
        return False
    if not info.readable or info.video_codec not in HLS_SAFE_VIDEO:
        return False
    if info.pix_fmt not in HLS_SAFE_PIX:
        return False
    if info.audio_tracks:
        idx = 0 if audio_idx is None else max(0, min(int(audio_idx), len(info.audio_tracks) - 1))
        if info.audio_tracks[idx].codec not in HLS_SAFE_AUDIO:
            return False
    return True


def build_hls_command(
    src: Path,
    out_dir: Path,
    *,
    info: MediaProbe,
    start_s: float = 0.0,
    audio_idx: int | None = None,
    quality: str = "auto",
    input_args: list[str] | tuple[str, ...] | None = None,
    force_transcode: bool = False,
) -> tuple[list[str], bool]:
    """Construit la commande FFmpeg HLS (remux si compatible, sinon transcodage H.264/AAC)."""
    ff = cinema_ffmpeg_bin()
    playlist = out_dir / "index.m3u8"
    seg_pattern = out_dir / "seg_%05d.ts"
    offset = max(0.0, float(start_s))
    remux = (not force_transcode) and (not input_args) and can_remux_hls(
        info, audio_idx=audio_idx, quality=quality
    )

    cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if offset > 0.5 and not input_args:
        cmd += ["-ss", f"{offset:.3f}"]
    if input_args:
        cmd += list(input_args)
        if offset > 0.5:
            cmd += ["-ss", f"{offset:.3f}"]
    else:
        cmd += ["-i", str(src)]
    cmd += ["-map", "0:v:0"]

    has_audio = bool(info.audio_tracks)
    if has_audio:
        aidx = 0 if audio_idx is None else max(0, min(int(audio_idx), len(info.audio_tracks) - 1))
        cmd += ["-map", f"0:a:{aidx}?"]
    else:
        cmd += ["-an"]

    if remux:
        cmd += ["-c:v", "copy"]
        if has_audio:
            cmd += ["-c:a", "copy"]
    else:
        vf = _quality_scale(quality)
        cmd += [
            "-vf",
            vf or "format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "48",
            "-sc_threshold",
            "0",
        ]
        if has_audio:
            cmd += ["-c:a", "aac", "-ac", "2", "-b:a", "192k", "-ar", "48000"]

    cmd += [
        "-max_muxing_queue_size",
        "1024",
        "-f",
        "hls",
        "-hls_time",
        str(SEGMENT_SEC),
        "-hls_list_size",
        "0",
        "-hls_playlist_type",
        "event",
        "-hls_flags",
        "independent_segments+temp_file",
        "-hls_segment_filename",
        str(seg_pattern),
        str(playlist),
    ]
    return cmd, remux


class HlsSessionManager:
    """Pilote les processus FFmpeg HLS et nettoie les dossiers temporaires."""

    def __init__(self, cache: Path) -> None:
        self._root = cache / "hls"
        self._lock = threading.Lock()
        self._sessions: dict[str, HlsSession] = {}
        self._cleanup_stale_root()

    def _cleanup_stale_root(self) -> None:
        if self._root.is_dir():
            shutil.rmtree(self._root, ignore_errors=True)
        self._root.mkdir(parents=True, exist_ok=True)

    def _terminate(self, session: HlsSession) -> None:
        proc = session.proc
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except (OSError, subprocess.SubprocessError):
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except (OSError, subprocess.SubprocessError):
                    pass
        shutil.rmtree(session.directory, ignore_errors=True)

    def _reap_locked(self, *, make_room: bool = False) -> None:
        now = time.monotonic()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_access > IDLE_TTL_S
        ]
        for sid in expired:
            self._terminate(self._sessions.pop(sid))
        if make_room:
            while len(self._sessions) >= MAX_SESSIONS:
                oldest_sid = min(self._sessions, key=lambda k: self._sessions[k].last_access)
                self._terminate(self._sessions.pop(oldest_sid))

    def start_session(
        self,
        src: Path,
        *,
        item_key: str,
        start_s: float = 0.0,
        audio_idx: int | None = None,
        quality: str = "auto",
        wait_ready_s: float = 12.0,
        input_args: list[str] | tuple[str, ...] | None = None,
        probe: MediaProbe | None = None,
        force_transcode: bool = False,
    ) -> dict:
        info = probe if probe is not None else probe_media(src)
        if not info.readable:
            raise ValueError("vidéo illisible")

        sid = secrets.token_hex(12)
        out_dir = self._root / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd, remux = build_hls_command(
            src,
            out_dir,
            info=info,
            start_s=start_s,
            audio_idx=audio_idx,
            quality=quality,
            input_args=input_args,
            force_transcode=force_transcode,
        )
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        now = time.monotonic()
        session = HlsSession(
            sid=sid,
            item_key=item_key,
            src=src,
            directory=out_dir,
            proc=proc,
            start_s=max(0.0, float(start_s)),
            duration_s=info.duration_s,
            quality=quality,
            remux=remux,
            created_at=now,
            last_access=now,
        )
        with self._lock:
            self._reap_locked(make_room=True)
            self._sessions[sid] = session

        playlist = out_dir / "index.m3u8"
        first_seg = out_dir / "seg_00000.ts"
        deadline = time.monotonic() + wait_ready_s
        while time.monotonic() < deadline:
            if (
                playlist.is_file()
                and playlist.stat().st_size > 32
                and first_seg.is_file()
                and first_seg.stat().st_size > 128
            ):
                break
            if proc.poll() is not None:
                err = ""
                try:
                    err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
                except OSError:
                    pass
                self.stop_session(sid)
                raise ValueError(f"échec lecture HLS : {err.strip()[-200:] or proc.returncode}")
            time.sleep(0.1)

        if not playlist.is_file():
            self.stop_session(sid)
            raise ValueError("démarrage HLS trop lent ou impossible")

        return {
            "session_id": sid,
            "playlist_url": f"/api/cinema/stream/{sid}/index.m3u8",
            "start_s": session.start_s,
            "duration_s": session.duration_s,
            "remux": remux,
            "quality": quality,
        }

    def resolve_file(self, sid: str, filename: str) -> Path | None:
        if not sid or "/" in filename or "\\" in filename or ".." in filename:
            return None
        if not (filename == "index.m3u8" or (filename.startswith("seg_") and filename.endswith(".ts"))):
            return None
        with self._lock:
            self._reap_locked()
            session = self._sessions.get(sid)
            if session is None:
                return None
            session.last_access = time.monotonic()
            path = session.directory / filename
        return path if path.is_file() else None

    def stop_session(self, sid: str) -> bool:
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session is None:
            return False
        self._terminate(session)
        return True

    def stop_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            self._terminate(s)
