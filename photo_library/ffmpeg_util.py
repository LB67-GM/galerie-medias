from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

_ffmpeg: str | None = None


def ffmpeg_bin() -> str:
    global _ffmpeg
    if _ffmpeg:
        return _ffmpeg
    try:
        import imageio_ffmpeg

        _ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        _ffmpeg = "ffmpeg"
    return _ffmpeg


def system_ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def ffprobe_bin() -> str | None:
    return shutil.which("ffprobe")


def cinema_ffmpeg_bin() -> str:
    """Préfère le FFmpeg système (souvent compilé avec dvdvideo/bluray), repli sur imageio-ffmpeg."""
    return system_ffmpeg_bin() or ffmpeg_bin()


@lru_cache(maxsize=1)
def ffmpeg_capabilities() -> dict[str, object]:
    ff = cinema_ffmpeg_bin()
    fp = ffprobe_bin()
    dvdvideo = False
    bluray = False
    if ff:
        try:
            fmt = subprocess.run(
                [ff, "-hide_banner", "-formats"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            dvdvideo = "dvdvideo" in (fmt.stdout or "").lower()
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            proto = subprocess.run(
                [ff, "-hide_banner", "-protocols"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            bluray = "bluray" in (proto.stdout or "").lower()
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "ffmpeg": ff or "",
        "ffprobe": fp or "",
        "dvdvideo": dvdvideo,
        "bluray": bluray,
    }
