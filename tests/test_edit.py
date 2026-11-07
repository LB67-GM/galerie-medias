#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.db import SCHEMA, init_schema  # noqa: E402
from photo_library.delete_media import CORBEILLE, list_trash, purge_selected, restore_selected  # noqa: E402
from photo_library.edit import apply_photo_edit, _clamp_crop  # noqa: E402
from photo_library.paths import pair_key_of  # noqa: E402


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn, refresh_places=False)
    return conn


def _jpeg(path: Path, w: int, h: int, color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), color).save(path, "JPEG", quality=90)


def _insert(conn, relpath: str, size: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO media (relpath, size, mtime_ns, kind, year, present, thumb_ok, face_scanned, pair_key)
        VALUES (?, ?, 0, 'photo', 2024, 1, 1, 0, ?)
        """,
        (relpath, size, pair_key_of(relpath)),
    )
    return int(cur.lastrowid)


def test_clamp_full_is_none() -> None:
    assert _clamp_crop(None) is None
    assert _clamp_crop({"x": 0, "y": 0, "w": 1, "h": 1}) is None
    box = _clamp_crop({"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.4})
    assert box == (0.1, 0.2, 0.5, 0.4)


def test_rotate_and_crop(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    cache.mkdir()
    src = lib / "Annee 2024" / "test.jpg"
    _jpeg(src, 40, 20, "red")
    conn = _conn()
    media_id = _insert(conn, "Annee 2024/test.jpg", src.stat().st_size)
    result = apply_photo_edit(conn, lib, cache, media_id, rotate=90)
    with Image.open(lib / "Annee 2024" / "test.jpg") as img:
        assert img.size == (20, 40)
    backup = list((lib / CORBEILLE / "Annee 2024").glob("test.jpg"))
    assert backup and backup[0].is_file()
    assert result["width"] == 20 and result["height"] == 40
    row = conn.execute("SELECT face_scanned, thumb_ok FROM media WHERE id=?", (media_id,)).fetchone()
    assert row["face_scanned"] == 0
    assert row["thumb_ok"] == 1

    apply_photo_edit(
        conn, lib, cache, media_id, rotate=0, crop={"x": 0, "y": 0, "w": 1, "h": 0.5}
    )
    with Image.open(lib / "Annee 2024" / "test.jpg") as img:
        assert img.size == (20, 20)
    items = list_trash(conn)
    assert len(items) == 2
    assert all(it["reason"] == "edit" for it in items)
    assert conn.execute("SELECT present FROM media WHERE id=?", (media_id,)).fetchone()[0] == 1
    conn.close()


def test_png_becomes_jpeg(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    cache.mkdir()
    src = lib / "shot.png"
    src.parent.mkdir()
    Image.new("RGB", (12, 8), "blue").save(src, "PNG")
    conn = _conn()
    media_id = _insert(conn, "shot.png", src.stat().st_size)
    result = apply_photo_edit(conn, lib, cache, media_id, rotate=180)
    assert result["name"] == "shot.jpg"
    assert (lib / "shot.jpg").is_file()
    assert not src.exists()
    assert (lib / CORBEILLE / "shot.png").is_file()
    conn.close()


def test_restore_undoes_edit(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    cache.mkdir()
    src = lib / "Annee 2024" / "test.jpg"
    _jpeg(src, 40, 20, "red")
    conn = _conn()
    media_id = _insert(conn, "Annee 2024/test.jpg", src.stat().st_size)
    apply_photo_edit(conn, lib, cache, media_id, rotate=90)
    with Image.open(src) as img:
        assert img.size == (20, 40)
    items = list_trash(conn)
    assert len(items) == 1
    restored = restore_selected(conn, lib, [items[0]["id"]], cache)
    assert restored["restored"] == 1
    with Image.open(src) as img:
        assert img.size == (40, 20)
    assert list_trash(conn) == []
    assert conn.execute("SELECT present FROM media WHERE id=?", (media_id,)).fetchone()[0] == 1
    conn.close()


def test_restore_png_after_jpeg_edit(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    cache.mkdir()
    src = lib / "shot.png"
    src.parent.mkdir()
    Image.new("RGB", (12, 8), "blue").save(src, "PNG")
    conn = _conn()
    media_id = _insert(conn, "shot.png", src.stat().st_size)
    apply_photo_edit(conn, lib, cache, media_id, rotate=180)
    assert (lib / "shot.jpg").is_file()
    assert not src.exists()
    items = list_trash(conn)
    restore_selected(conn, lib, [items[0]["id"]], cache)
    assert src.is_file()
    assert not (lib / "shot.jpg").exists()
    rel = conn.execute("SELECT relpath FROM media WHERE id=?", (media_id,)).fetchone()[0]
    assert rel == "shot.png"
    conn.close()


def test_purge_edit_backup_keeps_photo(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    cache.mkdir()
    src = lib / "keep.jpg"
    _jpeg(src, 10, 8, "green")
    conn = _conn()
    media_id = _insert(conn, "keep.jpg", src.stat().st_size)
    apply_photo_edit(conn, lib, cache, media_id, rotate=180)
    items = list_trash(conn)
    purged = purge_selected(conn, lib, cache, [items[0]["id"]])
    assert purged["deleted"] == 1
    assert src.is_file()
    assert conn.execute("SELECT present FROM media WHERE id=?", (media_id,)).fetchone()[0] == 1
    assert list_trash(conn) == []
    conn.close()


if __name__ == "__main__":
    import tempfile

    test_clamp_full_is_none()
    with tempfile.TemporaryDirectory() as name:
        test_rotate_and_crop(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_png_becomes_jpeg(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_restore_undoes_edit(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_restore_png_after_jpeg_edit(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_purge_edit_backup_keeps_photo(Path(name))
    print("ok")
