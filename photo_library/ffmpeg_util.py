from __future__ import annotations

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
