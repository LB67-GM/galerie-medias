#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.copies import pick_keep, pick_live_media, unique_faces  # noqa: E402


def test_same_media() -> None:
    rows = [
        {"id": 1, "media_id": 10, "score": 1, "size": 100, "taken_at": "2020-01-01", "dhash": None},
        {"id": 2, "media_id": 10, "score": 0.9, "size": 100, "taken_at": "2020-01-01", "dhash": None},
    ]
    out, hidden = unique_faces(rows)
    assert len(out) == 1
    assert hidden == 1


def test_same_size_taken_different_names() -> None:
    rows = [
        {"id": 1, "media_id": 10, "score": 1, "size": 12345, "taken_at": "2017-11-18T13:27:14", "dhash": None},
        {"id": 2, "media_id": 11, "score": 0.9, "size": 12345, "taken_at": "2017-11-18T13:27:14", "dhash": None},
    ]
    out, hidden = unique_faces(rows)
    assert [r["media_id"] for r in out] == [10]
    assert hidden == 1


def test_near_dhash() -> None:
    a = "0" * 16
    b = "0000000000000001"
    rows = [
        {"id": 1, "media_id": 10, "score": 1, "size": 1, "taken_at": "a", "dhash": a},
        {"id": 2, "media_id": 11, "score": 0.9, "size": 2, "taken_at": "b", "dhash": b},
    ]
    out, hidden = unique_faces(rows)
    assert len(out) == 1
    assert hidden == 1


def test_distinct() -> None:
    rows = [
        {"id": 1, "media_id": 10, "score": 1, "size": 10, "taken_at": "a", "dhash": "0" * 16},
        {"id": 2, "media_id": 11, "score": 0.9, "size": 20, "taken_at": "b", "dhash": "f" * 16},
    ]
    out, hidden = unique_faces(rows)
    assert len(out) == 2
    assert hidden == 0


def test_pick_live_media_present() -> None:
    assert (
        pick_live_media(
            media_id=10,
            present=1,
            relpath="Annee 2026/Montréal/IMG_1.HEIC",
            size=100,
            year=2026,
            candidates=[],
        )
        == 10
    )


def test_pick_live_media_moved_same_year() -> None:
    assert (
        pick_live_media(
            media_id=10,
            present=0,
            relpath="Annee 2026/IMG_1.HEIC",
            size=100,
            year=2026,
            candidates=[
                {"id": 20, "relpath": "Annee 2026/Montréal/IMG_1.HEIC", "year": 2026, "size": 100},
                {"id": 21, "relpath": "Annee 2023/IMG_1.HEIC", "year": 2023, "size": 100},
            ],
        )
        == 20
    )


def test_pick_live_media_gone() -> None:
    assert (
        pick_live_media(
            media_id=10,
            present=0,
            relpath="Annee 2026/IMG_1.MOV",
            size=50,
            year=2026,
            candidates=[],
        )
        is None
    )


def test_pick_live_media_skips_corbeille() -> None:
    assert (
        pick_live_media(
            media_id=10,
            present=0,
            relpath="Annee 2007/PICT0865.JPG",
            size=80,
            year=2007,
            candidates=[
                {"id": 30, "relpath": ".corbeille/annee 2007/PICT0865.JPG", "year": 2007, "size": 80},
            ],
        )
        is None
    )


def test_pick_keep_prefers_photo() -> None:
    rows = [
        {"id": 1, "relpath": "Screenshot 1.png"},
        {"id": 2, "relpath": "Annee 2018/IMG_1.jpg"},
    ]
    assert pick_keep(rows) == 2


if __name__ == "__main__":
    test_same_media()
    test_same_size_taken_different_names()
    test_near_dhash()
    test_distinct()
    test_pick_keep_prefers_photo()
    test_pick_live_media_present()
    test_pick_live_media_moved_same_year()
    test_pick_live_media_gone()
    test_pick_live_media_skips_corbeille()
    print("ok")
