#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.db import SCHEMA  # noqa: E402
from photo_library.move_media import move_selected, move_targets  # noqa: E402


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add(conn, relpath: str, kind: str = "photo") -> int:
    cur = conn.execute(
        """
        INSERT INTO media (relpath, size, mtime_ns, kind, year, moment, present, thumb_ok, face_scanned)
        VALUES (?, 4, 1, ?, 2026, 'Croisiere 2026', 1, 0, 0)
        """,
        (relpath, kind),
    )
    return int(cur.lastrowid)


def _library(tmp: Path) -> Path:
    lib = tmp / "photos"
    cruise = lib / "Annee 2026" / "Croisiere 2026"
    wedding = lib / "Annee 2026" / "Mariage de Pauline et Hugo"
    nested = lib / "Annee 2026" / "Janvier 2026" / "Rome"
    other = lib / "Annee 2025" / "Paris"
    trash = lib / "Annee 2026" / ".corbeille"
    photos = lib / "Annee 2026" / "Photos"
    for folder in (cruise, wedding, nested, other, trash, photos):
        folder.mkdir(parents=True)
    return lib


def test_move_photo_and_live_companion(tmp_path: Path) -> None:
    lib = _library(tmp_path)
    cruise = lib / "Annee 2026" / "Croisiere 2026"
    wedding = lib / "Annee 2026" / "Mariage de Pauline et Hugo"
    jpg = cruise / "1ecde77f7f26b82c6d9b2343412d7089.JPG"
    mov = cruise / "1ecde77f7f26b82c6d9b2343412d7089.MOV"
    jpg.write_bytes(b"jpeg")
    mov.write_bytes(b"moov")
    conn = _conn()
    photo_id = _add(conn, "Annee 2026/Croisiere 2026/1ecde77f7f26b82c6d9b2343412d7089.JPG")
    video_id = _add(
        conn,
        "Annee 2026/Croisiere 2026/1ecde77f7f26b82c6d9b2343412d7089.MOV",
        "video",
    )
    targets = move_targets(conn, lib, [photo_id])
    labels = [item["label"] for item in targets["folders"]]
    assert "Mariage de Pauline et Hugo" in labels
    assert "Janvier 2026/Rome" in labels
    assert ".corbeille" not in labels
    assert "Photos" not in labels
    assert targets["year"] == 2026

    result = move_selected(
        conn,
        lib,
        [photo_id],
        "Annee 2026/Mariage de Pauline et Hugo",
    )
    assert result["moved"] == 1
    assert result["ids"] == [photo_id]
    assert not jpg.exists() and not mov.exists()
    assert (wedding / jpg.name).is_file()
    assert (wedding / mov.name).is_file()
    row = conn.execute("SELECT relpath, moment, place_locked FROM media WHERE id=?", (photo_id,)).fetchone()
    assert row["relpath"].endswith("Mariage de Pauline et Hugo/1ecde77f7f26b82c6d9b2343412d7089.JPG")
    assert row["moment"] == "Mariage de Pauline et Hugo"
    assert int(row["place_locked"]) == 0
    video = conn.execute("SELECT relpath FROM media WHERE id=?", (video_id,)).fetchone()
    assert "Mariage de Pauline et Hugo" in video["relpath"]
    conn.close()


def test_move_refuses_other_year_and_missing_folder(tmp_path: Path) -> None:
    lib = _library(tmp_path)
    src = lib / "Annee 2026" / "Croisiere 2026" / "a.JPG"
    src.write_bytes(b"jpeg")
    conn = _conn()
    photo_id = _add(conn, "Annee 2026/Croisiere 2026/a.JPG")
    other = _add(conn, "Annee 2025/Paris/b.JPG")
    (lib / "Annee 2025" / "Paris" / "b.JPG").write_bytes(b"jpeg")
    try:
        move_targets(conn, lib, [photo_id, other])
        raise AssertionError("deux années")
    except ValueError as exc:
        assert "même année" in str(exc)
    try:
        move_selected(conn, lib, [photo_id], "Annee 2026/Dossier inventé")
        raise AssertionError("dossier absent")
    except ValueError as exc:
        assert "n’existe pas" in str(exc)
    try:
        move_selected(conn, lib, [photo_id], "Annee 2025/Paris")
        raise AssertionError("autre année")
    except ValueError as exc:
        assert "même année" in str(exc)
    try:
        move_selected(conn, lib, [photo_id], "Annee 2026/../../ailleurs")
        raise AssertionError("traversal")
    except ValueError as exc:
        assert "refusé" in str(exc)
    assert src.is_file()
    conn.close()


def test_skip_same_folder_and_rename_collision(tmp_path: Path) -> None:
    lib = _library(tmp_path)
    cruise = lib / "Annee 2026" / "Croisiere 2026"
    wedding = lib / "Annee 2026" / "Mariage de Pauline et Hugo"
    src = cruise / "a.JPG"
    src.write_bytes(b"one")
    (wedding / "a.JPG").write_bytes(b"already")
    conn = _conn()
    stay = _add(conn, "Annee 2026/Mariage de Pauline et Hugo/deja.JPG")
    (wedding / "deja.JPG").write_bytes(b"stay")
    conn.execute(
        "UPDATE media SET moment=? WHERE id=?",
        ("Mariage de Pauline et Hugo", stay),
    )
    photo_id = _add(conn, "Annee 2026/Croisiere 2026/a.JPG")
    skipped = move_selected(conn, lib, [stay], "Annee 2026/Mariage de Pauline et Hugo")
    assert skipped["moved"] == 0 and skipped["skipped"] == 1
    moved = move_selected(conn, lib, [photo_id], "Annee 2026/Mariage de Pauline et Hugo")
    assert moved["moved"] == 1 and moved["renamed"] == 1
    assert (wedding / "a_2.JPG").read_bytes() == b"one"
    assert (wedding / "a.JPG").read_bytes() == b"already"
    assert not src.exists()
    conn.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as name:
        test_move_photo_and_live_companion(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_move_refuses_other_year_and_missing_folder(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_skip_same_folder_and_rename_collision(Path(name))
    print("ok")
