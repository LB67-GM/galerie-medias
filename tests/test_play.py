#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.play import (  # noqa: E402
    browser_safe,
    cached_play_path,
    ensure_play_mp4,
    parse_probe_text,
)


HEVC = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'IMG_0001.MOV':
  Stream #0:0[0x1](und): Video: hevc (Main 10) (hvc1 / 0x31637668), yuv420p10le(tv), 1920x1080, 7999 kb/s, 29.97 fps
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 165 kb/s
"""

H264 = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':
  Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1280x720, 2500 kb/s
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 128 kb/s
"""

MOOV = """
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x1] moov atom not found
IMG_0751.MOV: Invalid data found when processing input
"""


def test_hevc_needs_convert() -> None:
    info = parse_probe_text(HEVC)
    assert info.readable
    assert info.video_codec == "hevc"
    assert info.pix_fmt == "yuv420p10le"
    assert not browser_safe(info)


def test_h264_aac_is_safe() -> None:
    info = parse_probe_text(H264)
    assert info.readable
    assert info.video_codec == "h264"
    assert browser_safe(info)


def test_incomplete_mov() -> None:
    info = parse_probe_text(MOOV)
    assert not info.readable
    assert not browser_safe(info)


def test_pcm_audio_not_safe() -> None:
    text = """
    Stream #0:0: Video: h264 (High), yuv420p, 640x480
    Stream #0:1: Audio: pcm_s16le, 48000 Hz, stereo, s16, 1536 kb/s
    """
    info = parse_probe_text(text)
    assert info.readable
    assert info.audio_codec == "pcm_s16le"
    assert not browser_safe(info)


def test_play_cache_name() -> None:
    path = cached_play_path(Path("/tmp/cache"), 42, 1000, 9)
    assert path.name == "42-1000-9.mp4"
    assert path.parent.name == "play"


def test_transcode_tiny_clip(tmp_path: Path) -> None:
    from photo_library.ffmpeg_util import ffmpeg_bin
    from photo_library.play import probe_video, transcode_to_file

    src = tmp_path / "src.mp4"
    dest = tmp_path / "out.mp4"
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=64x48:d=0.4",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(src),
    ]
    proc = __import__("subprocess").run(cmd, capture_output=True, timeout=30, check=False)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-400:]
    info = probe_video(src)
    assert info.readable
    assert transcode_to_file(src, dest)
    assert dest.is_file() and dest.stat().st_size > 500
    tv = tmp_path / "tv.mp4"
    assert transcode_to_file(src, tv, for_tv=True)
    assert tv.is_file() and tv.stat().st_size > 500
    cached = tmp_path / "cached.mp4"
    out = ensure_play_mp4(src, cached)
    assert out == cached
    assert cached.is_file() and cached.stat().st_size > 500


if __name__ == "__main__":
    import tempfile
    from pathlib import Path as P

    test_hevc_needs_convert()
    test_h264_aac_is_safe()
    test_incomplete_mov()
    test_pcm_audio_not_safe()
    test_play_cache_name()
    with tempfile.TemporaryDirectory() as name:
        test_transcode_tiny_clip(P(name))
    print("ok")
