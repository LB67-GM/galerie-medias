#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.db import SCHEMA  # noqa: E402
from photo_library.delete_media import CORBEILLE, delete_selected, path_in_library  # noqa: E402
from photo_library.locate import locate_library_file  # noqa: E402


def test_path_in_library(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    lib.mkdir()
    inside = lib / "Annee 2020" / "a.jpg"
    inside.parent.mkdir()
    inside.write_bytes(b"x")
    assert path_in_library(lib, inside)
    other = tmp_path / "elsewhere.jpg"
    other.write_bytes(b"y")
    assert not path_in_library(lib, other)


def test_locate_rejects_escape(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    folder = lib / "2020"
    folder.mkdir(parents=True)
    photo = folder / "a.jpg"
    photo.write_bytes(b"photo")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    link = folder / "link.jpg"
    link.symlink_to(secret)
    assert locate_library_file(lib, "2020/a.jpg") == photo
    assert locate_library_file(lib, "../secret.txt") is None
    assert locate_library_file(lib, "2020/../../secret.txt") is None
    assert locate_library_file(lib, str(secret)) is None
    assert locate_library_file(lib, "2020/link.jpg") is None


def _get(app, path: str) -> tuple[int, bytes]:
    import asyncio

    status = {"code": 0}
    chunks: list[bytes] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body") or b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }
    asyncio.run(app(scope, receive, send))
    return status["code"], b"".join(chunks)


def test_http_hides_escaped_file(tmp_path: Path) -> None:
    from photo_library.app import create_app
    from photo_library.db import connect

    lib = tmp_path / "photos"
    (lib / "2020").mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET-MARKER", encoding="utf-8")
    (lib / "2020" / "link.jpg").symlink_to(secret)
    cache = tmp_path / "cache"
    app = create_app(lib, cache)
    conn = connect(cache)
    cur = conn.execute(
        """
        INSERT INTO media (relpath, size, mtime_ns, kind, present, thumb_ok, face_scanned)
        VALUES ('2020/link.jpg', 13, 0, 'photo', 1, 0, 0)
        """
    )
    media_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    code, body = _get(app, f"/api/media/{media_id}/file")
    assert code == 404
    assert b"SECRET-MARKER" not in body
    _code, preview = _get(app, f"/api/media/{media_id}/preview")
    assert b"SECRET-MARKER" not in preview


def test_delete_goes_to_trash(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    pic = lib / "shot.jpg"
    pic.write_bytes(b"hello")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.execute(
        """
        INSERT INTO media (relpath, size, mtime_ns, kind, present, thumb_ok, face_scanned)
        VALUES ('shot.jpg', 5, 0, 'photo', 1, 0, 0)
        """
    )
    media_id = int(cur.lastrowid)
    result = delete_selected(conn, lib, cache, [media_id])
    assert result["trashed"] == 1
    assert not pic.exists()
    assert (lib / CORBEILLE / "shot.jpg").is_file()
    assert conn.execute("SELECT present FROM media WHERE id=?", (media_id,)).fetchone()[0] == 0
    conn.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as name:
        test_path_in_library(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_locate_rejects_escape(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_http_hides_escaped_file(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_delete_goes_to_trash(Path(name))
    print("ok")
