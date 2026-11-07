#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.albums import (  # noqa: E402
    add_to_album,
    assign_media_albums,
    create_album,
    list_albums,
    remove_media_albums,
    set_favorite,
)
from photo_library.copies import (  # noqa: E402
    copy_groups,
    extra_copy_ids,
    looks_like_screenshot,
    pick_keep,
    trash_extra_copies,
)
from photo_library.db import SCHEMA, init_schema  # noqa: E402
from photo_library.delete_media import (  # noqa: E402
    CORBEILLE,
    KEEP_DAYS,
    delete_selected,
    list_trash,
    list_trash_ids,
    purge_expired,
    purge_selected,
    restore_selected,
    trash_selected,
)
from photo_library.faces import match_unlabeled, merge_people, name_cluster, people_for_filters  # noqa: E402
from photo_library.geo import (  # noqa: E402
    apply_folder_aliases,
    fold_name,
    geocode_place,
    map_places,
    resolve_folder_place,
    search_places,
)
from photo_library.paths import pair_key_of, parse_path_labels, parse_relpath  # noqa: E402
from photo_library.place_groups import cluster_places  # noqa: E402
from photo_library.places import (  # noqa: E402
    complete_moments_from_paths,
    complete_places_from_paths,
    set_media_places,
)
from photo_library.app import media_from_where  # noqa: E402
from photo_library.scan import index_missing_files, kind_of  # noqa: E402


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


def _insert_media(conn, relpath: str, **kwargs) -> int:
    cur = conn.execute(
        """
        INSERT INTO media (relpath, size, mtime_ns, kind, year, present, thumb_ok, face_scanned,
                           taken_at, dhash, place, pair_key)
        VALUES (?, ?, 0, ?, ?, 1, 0, 0, ?, ?, ?, ?)
        """,
        (
            relpath,
            kwargs.get("size", 10),
            kwargs.get("kind", "photo"),
            kwargs.get("year"),
            kwargs.get("taken_at"),
            kwargs.get("dhash"),
            kwargs.get("place"),
            kwargs.get("pair_key") or pair_key_of(relpath),
        ),
    )
    return int(cur.lastrowid)


def test_init_schema_adds_pair_key_on_existing_db() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY,
            relpath TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            kind TEXT NOT NULL,
            year INTEGER,
            place TEXT,
            taken_at TEXT,
            thumb_ok INTEGER NOT NULL DEFAULT 0,
            present INTEGER NOT NULL DEFAULT 1,
            face_scanned INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "INSERT INTO media (relpath, size, mtime_ns, kind) VALUES ('Annee 2024/X/IMG_1.HEIC', 1, 0, 'photo')"
    )
    init_schema(conn, refresh_places=False)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    assert "pair_key" in cols
    assert "moment" in cols
    key = conn.execute("SELECT pair_key FROM media").fetchone()[0]
    conn.close()
    assert key == pair_key_of("Annee 2024/X/IMG_1.HEIC")


def test_trash_restore_purge(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    pic = lib / "shot.jpg"
    pic.write_bytes(b"hello")
    conn = _conn()
    media_id = _insert_media(conn, "shot.jpg", size=5)
    result = delete_selected(conn, lib, cache, [media_id])
    assert result["trashed"] == 1
    assert not pic.exists()
    dumped = lib / CORBEILLE / "shot.jpg"
    assert dumped.is_file()
    assert conn.execute("SELECT present FROM media WHERE id=?", (media_id,)).fetchone()[0] == 0
    restored = restore_selected(conn, lib, [media_id])
    assert restored["restored"] == 1
    assert pic.is_file()
    result = delete_selected(conn, lib, cache, [media_id])
    purged = purge_selected(conn, lib, cache, [media_id])
    assert purged["deleted"] == 1
    assert not dumped.exists()
    assert not pic.exists()
    assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0
    conn.close()


def test_list_trash_page(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    conn = _conn()
    ids = []
    for i in range(5):
        (lib / f"p{i}.jpg").write_bytes(b"x")
        ids.append(_insert_media(conn, f"p{i}.jpg", size=1))
    trash_selected(conn, lib, cache, ids)
    all_items = list_trash(conn)
    assert len(all_items) == 5
    page = list_trash(conn, offset=0, limit=2)
    assert len(page) == 2
    page2 = list_trash(conn, offset=2, limit=2)
    assert len(page2) == 2
    assert {it["id"] for it in page}.isdisjoint({it["id"] for it in page2})
    assert list_trash_ids(conn) == [it["id"] for it in all_items]
    conn.close()


def test_purge_expired_keeps_recent(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    old = lib / "old.jpg"
    new = lib / "new.jpg"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    conn = _conn()
    old_id = _insert_media(conn, "old.jpg", size=3)
    new_id = _insert_media(conn, "new.jpg", size=3)
    trash_selected(conn, lib, cache, [old_id, new_id])
    old_stamp = (
        datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS + 1)
    ).replace(microsecond=0).isoformat()
    conn.execute("UPDATE trash SET trashed_at=? WHERE media_id=?", (old_stamp, old_id))
    conn.commit()
    result = purge_expired(conn, lib, cache)
    assert result["deleted"] == 1
    left = list_trash(conn)
    assert len(left) == 1
    assert left[0]["id"] == new_id
    assert not (lib / CORBEILLE / "old.jpg").exists()
    assert (lib / CORBEILLE / "new.jpg").is_file()
    conn.close()


def test_albums_and_favorite() -> None:
    conn = _conn()
    a = _insert_media(conn, "a.jpg")
    b = _insert_media(conn, "b.jpg")
    album = create_album(conn, "Canada")
    added = add_to_album(conn, album["id"], [a, b])
    assert added["added"] == 2
    listed = list_albums(conn)
    assert listed[0]["name"] == "Canada"
    assert listed[0]["count"] == 2
    fav = set_favorite(conn, [a], True)
    assert fav["updated"] == 1
    other = create_album(conn, "Mariage")
    assigned = assign_media_albums(conn, [a], [album["id"], other["id"]], replace=True)
    assert assigned["added"] == 1
    listed = list_albums(conn)
    by_name = {row["name"]: row["count"] for row in listed}
    assert by_name["Canada"] == 2
    assert by_name["Mariage"] == 1
    created = assign_media_albums(conn, [b], [], create="À imprimer")
    assert created["created"]["name"] == "À imprimer"
    assert created["added"] == 1
    gone = remove_media_albums(conn, [a], [album["id"], other["id"]])
    assert gone["removed"] == 2
    left = conn.execute(
        "SELECT COUNT(*) FROM album_media WHERE media_id=?", (a,)
    ).fetchone()[0]
    assert left == 0
    assert conn.execute("SELECT favorite FROM media WHERE id=?", (a,)).fetchone()[0] == 0
    conn.close()


def test_copy_keep() -> None:
    assert looks_like_screenshot("Annee 2020/Screenshot 2020-01-01.png")
    rows = [
        {"id": 1, "relpath": "Annee 2020/Screenshot 1.png"},
        {"id": 2, "relpath": "Annee 2020/Montreal/IMG_1.jpg"},
    ]
    assert pick_keep(rows) == 2
    conn = _conn()
    _insert_media(conn, "a.jpg", size=100, taken_at="2020-01-01")
    _insert_media(conn, "b.jpg", size=100, taken_at="2020-01-01")
    _insert_media(conn, "c.jpg", size=50, taken_at="2020-01-02")
    data = copy_groups(conn, limit=10)
    assert data["group_count"] == 1
    assert data["groups"][0]["count"] == 2
    assert data["extra_count"] == 1
    conn.close()


def test_trash_extra_copies(tmp_path: Path) -> None:
    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    lib.mkdir()
    (lib / "Annee 2020").mkdir()
    cache.mkdir()
    keep = lib / "keep.jpg"
    extra = lib / "Annee 2020" / "copy.jpg"
    keep.write_bytes(b"keep")
    extra.write_bytes(b"copy")
    conn = _conn()
    keep_id = _insert_media(conn, "keep.jpg", size=100, taken_at="2020-01-01")
    extra_id = _insert_media(conn, "Annee 2020/copy.jpg", size=100, taken_at="2020-01-01")
    assert extra_copy_ids(conn) == [extra_id]
    result = trash_extra_copies(conn, lib, cache)
    assert result["trashed"] == 1
    assert keep.is_file()
    assert not extra.exists()
    assert (lib / CORBEILLE / "Annee 2020" / "copy.jpg").is_file()
    assert conn.execute("SELECT present FROM media WHERE id=?", (keep_id,)).fetchone()[0] == 1
    assert conn.execute("SELECT present FROM media WHERE id=?", (extra_id,)).fetchone()[0] == 0
    conn.close()


def test_merge_people() -> None:
    conn = _conn()
    mid = _insert_media(conn, "face.jpg")
    keep = conn.execute(
        "INSERT INTO people (name, created_at) VALUES ('Papa', 't')"
    ).lastrowid
    absorb = conn.execute(
        "INSERT INTO people (name, created_at) VALUES ('papa', 't')"
    ).lastrowid
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', ?, 't')
        """,
        (mid, b"abcd", absorb),
    )
    conn.commit()
    out = merge_people(conn, int(keep), int(absorb))
    assert out["merged"] is True
    assert out["moved"] == 1
    assert conn.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 1
    conn.close()


def test_fold_name() -> None:
    assert fold_name("Montréal") == "montreal"
    assert fold_name("Saint-Jean-sur-Richelieu") == "saint jean sur richelieu"
    assert fold_name("Marseiile") == "marseiile"
    assert resolve_folder_place("Marseiile") == "Marseille"
    assert fold_name("Marseile") == "marseile"
    assert resolve_folder_place("Marseile") == "Marseille"
    assert fold_name("Marsielle") == "marsielle"
    assert resolve_folder_place("Marsielle") == "Marseille"


def test_map_aliases() -> None:
    jardin = geocode_place("Fete jardin")
    terrasse = geocode_place("Soiree terrasse")
    rome = geocode_place("Rome")
    floride = geocode_place("Floride 2017")
    assert jardin is not None and jardin["cc"] == "FR"
    assert terrasse is not None and abs(terrasse["lat"] - 48.86) < 0.05
    assert rome is not None and rome["cc"] == "IT" and rome["lat"] > 40
    assert floride is not None and floride["cc"] == "US" and floride["lon"] < -80
    typo = geocode_place("Marseiile")
    assert typo is not None and typo["cc"] == "FR"
    short = geocode_place("Marseile")
    assert short is not None and short["cc"] == "FR"
    mapping = apply_folder_aliases(
        {"Fete jardin": "Fete jardin", "Soiree terrasse": "Soiree terrasse", "Paris": "Paris"},
        ["Fete jardin", "Soiree terrasse", "Paris"],
        {"Paris": 100, "Fete jardin": 2, "Soiree terrasse": 7},
    )
    assert mapping["Fete jardin"] == "Paris"
    assert mapping["Soiree terrasse"] == "Paris"
    remapped = apply_folder_aliases(
        {"Lyon": "Lyon", "Paris": "Paris"},
        ["Lyon", "Paris"],
        {"Lyon": 4, "Paris": 2},
        extra={"lyon": "Paris"},
        skip_keys={"lyon"},
    )
    assert remapped["Lyon"] == "Lyon"
    remapped_bare = apply_folder_aliases(
        {"Lyon": "Lyon", "Paris": "Paris"},
        ["Lyon", "Paris"],
        {"Lyon": 4, "Paris": 2},
        extra={"lyon": "Paris"},
    )
    assert remapped_bare["Lyon"] == "Lyon"
    assert resolve_folder_place("Lyon", {"lyon": "Paris"}) == "Lyon"
    assert (
        resolve_folder_place(
            "Annee 2011/Decembre 2011/Noel en famille",
            {"annee 2011/decembre 2011/noel en famille": "Montréal"},
        )
        == "Montréal"
    )
    assert resolve_folder_place("Fete jardin") == "Paris"
    ny = geocode_place("New-York")
    manhattan = geocode_place("Manhattan")
    assert ny is not None and ny["lon"] < -73 and ny["lon"] > -75
    assert manhattan is not None and abs(manhattan["lat"] - ny["lat"]) < 0.05
    hits = search_places("Manhattan")
    assert hits and hits[0]["lon"] < -73 and hits[0]["lon"] > -75
    ks = geocode_place("Manhattan Kansas")
    assert ks is not None and ks["lon"] < -90
    pt = geocode_place("Portugal")
    assert pt is not None and pt["cc"] == "PT" and -10 < pt["lon"] < -6
    lis = geocode_place("Lisbonne")
    assert lis is not None and lis["cc"] == "PT" and lis["lon"] < -8


def test_portugal_map_pin_not_in_sahara() -> None:
    conn = _conn()
    _insert_media(conn, "Annee 2016/Juillet 2016/Vacances/Portugal/a.jpg", year=2016, place="Portugal")
    conn.execute(
        """
        INSERT INTO place_coords (place_key, place, lat, lon, cc)
        VALUES ('portugal', 'Portugal', 24.84656534821976, 0.0, '')
        """
    )
    conn.commit()
    data = map_places(conn)
    pins = [p for p in data["pins"] if fold_name(p["place"]) == "portugal"]
    assert pins, data
    pin = pins[0]
    assert pin["cc"] == "PT"
    assert pin["lon"] < -6
    assert pin["lat"] > 36
    conn.close()


def test_map_prefers_photo_gps_over_folder_name() -> None:
    conn = _conn()
    mid = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Vacances/Portugal/Lisbonne/a.jpg",
        year=2016,
        place="Portugal",
    )
    conn.execute(
        "UPDATE media SET gps_lat=?, gps_lon=?, gps_scanned=1 WHERE id=?",
        (38.71667, -9.13333, mid),
    )
    conn.commit()
    named = geocode_place("Portugal")
    assert named is not None and named["lon"] > -9
    data = map_places(conn)
    pins = [p for p in data["pins"] if fold_name(p["place"]) == "portugal"]
    assert pins
    pin = pins[0]
    assert abs(pin["lat"] - 38.71667) < 0.02
    assert abs(pin["lon"] + 9.13333) < 0.02
    conn.close()


def test_stale_new_york_coords_do_not_stay_in_kansas() -> None:
    conn = _conn()
    mid = _insert_media(conn, "Annee 2018/Manhattan/a.jpg", year=2018, place="Manhattan")
    set_media_places(conn, [mid], "New York", lat=39.1, lon=-94.6, cc="US")
    data = map_places(conn)
    assert data["pins"]
    pin = data["pins"][0]
    assert pin["lon"] < -73 and pin["lon"] > -75
    conn.close()


def test_san_jose_california_not_spain() -> None:
    cal = geocode_place("San Jose Californie")
    usa = geocode_place("San Jose USA")
    assert cal is not None and cal["cc"] == "US" and cal["lon"] < -100
    assert usa is not None and usa["cc"] == "US"
    clustered = cluster_places(["San Jose", "San Jose Californie"])
    assert clustered["San Jose Californie"] != clustered["San Jose"]
    hits = search_places("San Jose Californie")
    assert hits and hits[0]["cc"] == "US"
    named = search_places("San Jose")
    assert any(h["cc"] == "US" and h["lon"] < -100 for h in named)


def test_map_uses_picked_coordinates() -> None:
    conn = _conn()
    spain = _insert_media(conn, "Annee 2018/San Jose/a.jpg", year=2018, place="San Jose")
    ca = _insert_media(conn, "Annee 2019/San Jose/b.jpg", year=2019, place="San Jose")
    conn.commit()
    set_media_places(
        conn,
        [ca],
        "San Jose Californie",
        lat=37.3382,
        lon=-121.8863,
        cc="US",
    )
    data = map_places(conn)
    pins = data["pins"]
    west = [p for p in pins if p["lon"] < -100]
    east = [p for p in pins if p["lon"] > -20]
    assert west and west[0]["cc"] == "US"
    assert any("Californie" in (p["place"] or "") or p["cc"] == "US" for p in west)
    assert conn.execute("SELECT place FROM media WHERE id=?", (spain,)).fetchone()[0] == "San Jose"
    conn.close()


def test_kind_of_camcorder_videos() -> None:
    assert kind_of(Path("cam.mpg")) == "video"
    assert kind_of(Path("tape.MTS")) == "video"
    assert kind_of(Path("clip.wmv")) == "video"
    assert kind_of(Path("clip.mpeg")) == "video"


def _gallery_ids(conn, **kwargs):
    from_sql, clause, params = media_from_where(
        year=kwargs.get("year"),
        month=kwargs.get("month"),
        place=kwargs.get("place"),
        moment=kwargs.get("moment"),
        kind=kwargs.get("kind"),
        person_id=kwargs.get("person_id"),
        q=kwargs.get("q"),
        place_aliases=kwargs.get("place_aliases"),
    )
    return {
        int(row["id"])
        for row in conn.execute(
            f"SELECT m.id FROM {from_sql} WHERE {clause}", params
        )
    }


def _add_named_face(conn, media_id: int, person_id: int) -> None:
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', ?, 't')
        """,
        (media_id, b"abcd", person_id),
    )


def test_filters_combine_year_place_person() -> None:
    """Année, lieu et visage se combinent en ET (intersection)."""
    conn = _conn()
    lea = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Lea', 't')"
        ).lastrowid
    )
    other = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Noa', 't')"
        ).lastrowid
    )
    a = _insert_media(
        conn, "Annee 2024/Montreal/a.jpg", year=2024, place="Montréal",
        taken_at="2024-06-01T12:00:00",
    )
    b = _insert_media(
        conn, "Annee 2024/Paris/b.jpg", year=2024, place="Paris",
        taken_at="2024-07-01T12:00:00",
    )
    c = _insert_media(
        conn, "Annee 2025/Montreal/c.jpg", year=2025, place="Montréal",
        taken_at="2025-06-01T12:00:00",
    )
    d = _insert_media(
        conn, "Annee 2024/Montreal/d.jpg", year=2024, place="Montréal",
        taken_at="2024-08-01T12:00:00",
    )
    e = _insert_media(
        conn, "Annee 2024/Montreal/e.jpg", year=2024, place="Montréal",
        taken_at="2024-09-01T12:00:00",
    )
    _add_named_face(conn, a, lea)
    _add_named_face(conn, b, lea)
    _add_named_face(conn, c, lea)
    _add_named_face(conn, e, other)
    conn.commit()

    assert _gallery_ids(conn, year=2024, person_id=lea) == {a, b}
    assert _gallery_ids(conn, place_aliases=["Montréal"], person_id=lea) == {a, c}
    assert _gallery_ids(
        conn, year=2024, place_aliases=["Montréal"], person_id=lea
    ) == {a}
    assert d not in _gallery_ids(conn, year=2024, person_id=lea)
    conn.close()


def test_filters_combine_place_and_moment() -> None:
    conn = _conn()
    london = _insert_media(
        conn,
        "Annee 2026/Vacances Portugal/Lisbonne/a.jpg",
        year=2026,
        place="Lisbonne",
    )
    tunis = _insert_media(
        conn,
        "Annee 2026/Croisiere 2026/Tunis/b.jpg",
        year=2026,
        place="Tunis",
    )
    rome = _insert_media(conn, "Annee 2024/Rome/c.jpg", year=2024, place="Rome")
    conn.execute(
        "UPDATE media SET moment=? WHERE id=?", ("Vacances Portugal", london)
    )
    conn.execute(
        "UPDATE media SET moment=? WHERE id=?", ("Croisiere 2026", tunis)
    )
    conn.commit()
    assert _gallery_ids(conn, moment="Vacances Portugal") == {london}
    assert _gallery_ids(conn, place_aliases=["Lisbonne"], moment="Vacances Portugal") == {
        london
    }
    assert _gallery_ids(conn, moment="Croisiere 2026") == {tunis}
    assert _gallery_ids(conn, moment="__none__") == {rome}
    assert tunis not in _gallery_ids(conn, moment="Vacances Portugal")
    conn.close()


def test_pair_key_live_photo() -> None:
    assert pair_key_of("Annee 2024/Jamaique/IMG_1234.HEIC") == pair_key_of(
        "Annee 2024/Jamaique/IMG_1234.MOV"
    )
    assert pair_key_of("Annee 2024/Jamaique/IMG_1234_hevc.MOV") == pair_key_of(
        "Annee 2024/Jamaique/IMG_1234.HEIC"
    )
    assert pair_key_of("Annee 2024/A/IMG_1.HEIC") != pair_key_of(
        "Annee 2024/B/IMG_1.MOV"
    )


def test_person_filter_includes_live_photo_video() -> None:
    conn = _conn()
    lea = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Lea', 't')"
        ).lastrowid
    )
    photo = _insert_media(
        conn,
        "Annee 2024/Jamaique/IMG_1000.HEIC",
        year=2024,
        place="Jamaique",
        taken_at="2024-06-01T12:00:00",
    )
    video = _insert_media(
        conn,
        "Annee 2024/Jamaique/IMG_1000.MOV",
        year=2024,
        place="Jamaique",
        kind="video",
        taken_at="2024-06-01T12:00:00",
    )
    other = _insert_media(
        conn,
        "Annee 2024/Jamaique/IMG_9999.MOV",
        year=2024,
        place="Jamaique",
        kind="video",
        taken_at="2024-06-01T12:00:00",
    )
    _add_named_face(conn, photo, lea)
    conn.commit()
    ids = _gallery_ids(conn, year=2024, person_id=lea)
    conn.close()
    assert photo in ids
    assert video in ids
    assert other not in ids


def test_match_unlabeled_attaches_similar_face() -> None:
    import numpy as np

    conn = _conn()
    person = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Lea', 't')"
        ).lastrowid
    )
    named = _insert_media(conn, "named.jpg", year=2024)
    unlabeled = _insert_media(conn, "maybe.jpg", year=2024)
    vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    close = np.array([0.99, 0.1, 0.0, 0.0], dtype=np.float32)
    close = close / float(np.linalg.norm(close))
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', ?, 't')
        """,
        (named, vec.tobytes(), person),
    )
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', NULL, 't')
        """,
        (unlabeled, close.tobytes()),
    )
    conn.commit()
    attached = match_unlabeled(conn, 0.5)
    got = conn.execute(
        "SELECT person_id FROM faces WHERE media_id=?", (unlabeled,)
    ).fetchone()[0]
    conn.close()
    assert attached == 1
    assert int(got) == person


def test_name_cluster_creates_new_person_without_matching_others() -> None:
    import numpy as np

    conn = _conn()
    named_media = _insert_media(conn, "cluster.jpg")
    other_media = _insert_media(conn, "other.jpg")
    vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    close = np.array([0.99, 0.1, 0.0, 0.0], dtype=np.float32)
    close = close / float(np.linalg.norm(close))
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, cluster_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', NULL, 7, 't')
        """,
        (named_media, vec.tobytes()),
    )
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, cluster_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', NULL, 8, 't')
        """,
        (other_media, close.tobytes()),
    )
    conn.commit()
    out = name_cluster(conn, 7, "Papa")
    people = [
        row["name"]
        for row in conn.execute("SELECT name FROM people ORDER BY id")
    ]
    other = conn.execute(
        "SELECT person_id, cluster_id FROM faces WHERE media_id=?", (other_media,)
    ).fetchone()
    named = conn.execute(
        "SELECT person_id, cluster_id FROM faces WHERE media_id=?", (named_media,)
    ).fetchone()
    conn.close()
    assert out["name"] == "Papa"
    assert out["matched"] == 0
    assert people == ["Papa"]
    assert int(named["person_id"]) == out["person_id"]
    assert named["cluster_id"] is None
    assert other["person_id"] is None
    assert int(other["cluster_id"]) == 8


def test_name_faces_many_only_checked_ids() -> None:
    conn = _conn()
    a = _insert_media(conn, "a.jpg")
    b = _insert_media(conn, "b.jpg")
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, cluster_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', NULL, 3, 't')
        """,
        (a, b"abcd"),
    )
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, cluster_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', NULL, 3, 't')
        """,
        (b, b"efgh"),
    )
    conn.commit()
    keep = int(
        conn.execute("SELECT id FROM faces WHERE media_id=?", (a,)).fetchone()[0]
    )
    skip = int(
        conn.execute("SELECT id FROM faces WHERE media_id=?", (b,)).fetchone()[0]
    )
    from photo_library.faces import name_faces_many, unname_faces_many, person_faces_payload

    out = name_faces_many(conn, [keep], "Nicolas")
    named = conn.execute(
        "SELECT person_id FROM faces WHERE id=?", (keep,)
    ).fetchone()[0]
    other = conn.execute(
        "SELECT person_id, cluster_id FROM faces WHERE id=?", (skip,)
    ).fetchone()
    review = person_faces_payload(conn, out["person_id"])
    unname_faces_many(conn, [keep])
    gone = conn.execute(
        "SELECT person_id FROM faces WHERE id=?", (keep,)
    ).fetchone()[0]
    people_left = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    conn.close()
    assert out["named"] == 1
    assert int(named) == out["person_id"]
    assert other["person_id"] is None
    assert int(other["cluster_id"]) == 3
    assert review["name"] == "Nicolas"
    assert review["total"] == 1
    assert gone is None
    assert people_left == 0


def test_people_for_filters_includes_named_years() -> None:
    conn = _conn()
    kid = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Léa', 't')"
        ).lastrowid
    )
    missing = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Hayu', 't')"
        ).lastrowid
    )
    photo = _insert_media(conn, "Annee 2008/a.jpg", year=2008)
    gone = _insert_media(conn, "Annee 2008/gone.jpg", year=2008)
    conn.execute("UPDATE media SET present=0 WHERE id=?", (gone,))
    _add_named_face(conn, photo, kid)
    _add_named_face(conn, gone, missing)
    conn.commit()
    people = people_for_filters(conn)
    conn.close()
    names = {p["name"]: p for p in people}
    assert "Léa" in names
    assert names["Léa"]["year_min"] == 2008
    assert names["Léa"]["year_max"] == 2008
    assert "Hayu" not in names


def test_year_filter_includes_exif_in_other_folder() -> None:
    conn = _conn()
    in_folder = _insert_media(
        conn, "Annee 2024/Montreal/a.jpg", year=2024, taken_at="2024-06-01T12:00:00"
    )
    in_other_folder = _insert_media(
        conn, "Annee 2025/Montreal/b.jpg", year=2025, taken_at="2024-12-20T12:00:00"
    )
    later = _insert_media(
        conn, "Annee 2025/Montreal/c.jpg", year=2025, taken_at="2025-02-01T12:00:00"
    )
    from_sql, clause, params = media_from_where(
        year=2024, place=None, kind=None, person_id=None, q=None
    )
    ids = {
        int(row["id"])
        for row in conn.execute(
            f"SELECT m.id FROM {from_sql} WHERE {clause}", params
        )
    }
    conn.close()
    assert in_folder in ids
    assert in_other_folder in ids
    assert later not in ids


def test_month_filter_exif_or_folder() -> None:
    conn = _conn()
    june_exif = _insert_media(
        conn,
        "Annee 2024/Montreal/a.jpg",
        year=2024,
        taken_at="2024-06-15T12:00:00",
        place="Montréal",
    )
    july_exif = _insert_media(
        conn,
        "Annee 2024/Montreal/b.jpg",
        year=2024,
        taken_at="2024-07-01T12:00:00",
        place="Montréal",
    )
    june_folder = _insert_media(
        conn,
        "Annee 2024/Juin 2024/c.jpg",
        year=2024,
        taken_at="2024-01-02T12:00:00",
        place="Montréal",
    )
    june_win = _insert_media(
        conn,
        r"Annee 2024\Juin 2024\d.jpg",
        year=2024,
        taken_at="2023-12-01T12:00:00",
        place="Montréal",
    )
    ids = _gallery_ids(conn, year=2024, month=6)
    conn.close()
    assert june_exif in ids
    assert june_folder in ids
    assert june_win in ids
    assert july_exif not in ids


def test_search_place_and_person_not_just_filename() -> None:
    conn = _conn()
    kayla = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Léa', 't')"
        ).lastrowid
    )
    named = _insert_media(
        conn, "Annee 2008/Paris/IMG_1.jpg", year=2008, place="Paris"
    )
    other = _insert_media(
        conn, "Annee 2008/Lyon/IMG_2.jpg", year=2008, place="Lyon"
    )
    conn.execute(
        """
        INSERT INTO faces (media_id, x, y, w, h, embedding, dim, engine, person_id, created_at)
        VALUES (?, 0, 0, 1, 1, ?, 4, 'test', ?, 't')
        """,
        (named, b"abcd", kayla),
    )
    conn.commit()
    by_place = _gallery_ids(conn, q="Paris")
    by_person = _gallery_ids(conn, q="Léa")
    by_file = _gallery_ids(conn, q="IMG_2")
    conn.close()
    assert named in by_place
    assert other not in by_place
    assert named in by_person
    assert other not in by_person
    assert other in by_file
    assert named not in by_file


def test_search_rome_is_whole_word() -> None:
    conn = _conn()
    marome = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Maromé', 't')"
        ).lastrowid
    )
    marome_ascii = int(
        conn.execute(
            "INSERT INTO people (name, created_at) VALUES ('Marome', 't')"
        ).lastrowid
    )
    rome = _insert_media(
        conn, "Annee 2019/Rome/colisee.jpg", year=2019, place="Rome"
    )
    andromede = _insert_media(
        conn, "Annee 2020/Andromede/quai.jpg", year=2020, place="Andromède"
    )
    wedding = _insert_media(
        conn,
        "Annee 2017/Mariage Octobre 2017/Marseille/dance.jpg",
        year=2017,
        place="Marseille",
    )
    _add_named_face(conn, wedding, marome)
    montreal = _insert_media(
        conn, "Annee 2016/Montreal/fete.jpg", year=2016, place="Montréal"
    )
    _add_named_face(conn, montreal, marome_ascii)
    conn.commit()
    rome_ids = _gallery_ids(conn, q="Rome")
    rome_lower = _gallery_ids(conn, q="rome")
    marome_ids = _gallery_ids(conn, q="Maromé")
    andromede_ids = _gallery_ids(conn, q="Andromède")
    conn.close()
    assert rome in rome_ids
    assert rome_ids == rome_lower
    assert andromede not in rome_ids
    assert wedding not in rome_ids
    assert montreal not in rome_ids
    assert wedding in marome_ids
    assert montreal in marome_ids
    assert rome not in marome_ids
    assert andromede in andromede_ids
    assert rome not in andromede_ids


def test_year_month_script_present() -> None:
    from photo_library.sort_job import year_month_script

    assert year_month_script().is_file()


def test_gallery_recent_year_first() -> None:
    from photo_library.app import GALLERY_ORDER_SQL

    conn = _conn()
    old = _insert_media(
        conn, "annee 2007/photo-ancienne.jpg", year=2007, taken_at="2007-10-20T12:00:00"
    )
    new = _insert_media(
        conn, "Annee 2026/Lyon/photo.jpg", year=2026, taken_at="2026-06-01T12:00:00"
    )
    ids = [
        int(row["id"])
        for row in conn.execute(
            f"SELECT id FROM media AS m WHERE m.present=1 ORDER BY {GALLERY_ORDER_SQL}"
        )
    ]
    assert ids == [new, old]
    conn.close()


def test_lyon_stays_out_of_paris() -> None:
    conn = _conn()
    for i in range(3):
        _insert_media(
            conn,
            f"Annee 2020/Lyon/a{i}.jpg",
            year=2020,
            place="Lyon",
        )
    _insert_media(conn, "Annee 2020/Paris/b.jpg", year=2020, place="Paris")
    conn.execute(
        "INSERT INTO place_aliases (folder, place) VALUES (?, ?)",
        ("Lyon", "Paris"),
    )
    conn.execute(
        """
        INSERT INTO place_coords (place_key, place, lat, lon, cc)
        VALUES ('lyon', 'Lyon', 45.7640, 4.8357, 'FR')
        """
    )
    conn.commit()
    data = map_places(conn)
    pins = [
        p
        for p in data["pins"]
        if "lyon" in fold_name(p["place"])
        or "lyon" in fold_name(p.get("filter_place") or "")
    ]
    assert pins, data["pins"]
    pin = pins[0]
    assert pin["count"] == 3
    assert fold_name(pin.get("filter_place") or pin["place"]) == "lyon"
    assert abs(pin["lat"] - 45.7640) < 0.01
    from photo_library.places import user_alias_map, user_coord_map

    mapping = apply_folder_aliases(
        cluster_places(
            ["Lyon", "Paris"],
            {"Lyon": 3, "Paris": 1},
        ),
        ["Lyon", "Paris"],
        {"Lyon": 3, "Paris": 1},
        extra=user_alias_map(conn),
        skip_keys=set(user_coord_map(conn).keys()),
    )
    assert mapping["Lyon"] == "Lyon"
    conn.close()


def test_set_place() -> None:
    assert resolve_folder_place("Fete jardin") == "Paris"
    conn = _conn()
    mid = _insert_media(conn, "Annee 2020/Fete jardin/x.jpg", year=2020, place="Fete jardin")
    extra = _insert_media(conn, "Annee 2020/Fete jardin/y.jpg", year=2020, place="Fete jardin")
    other_year = _insert_media(conn, "Annee 2021/Fete jardin/z.jpg", year=2021, place="Fete jardin")
    nested = _insert_media(
        conn, "Annee 2020/Fete jardin/soirée/w.jpg", year=2020, place="Fete jardin"
    )
    root = _insert_media(conn, "Annee 2020/loose.jpg", year=2020, place=None)
    sub = _insert_media(conn, "Annee 2020/Lyon/a.jpg", year=2020, place="Lyon")
    out = set_media_places(conn, [mid], "Paris", apply_folder=True)
    assert out["updated"] == 2
    assert out["folders"] == ["Annee 2020/Fete jardin"]
    assert conn.execute("SELECT place FROM media WHERE id=?", (extra,)).fetchone()[0] == "Paris"
    assert conn.execute("SELECT place FROM media WHERE id=?", (other_year,)).fetchone()[0] == "Fete jardin"
    assert conn.execute("SELECT place FROM media WHERE id=?", (nested,)).fetchone()[0] == "Fete jardin"
    root_out = set_media_places(conn, [root], "Montréal", apply_folder=True)
    assert root_out["updated"] == 1
    assert conn.execute("SELECT place FROM media WHERE id=?", (sub,)).fetchone()[0] == "Lyon"
    conn.close()


def test_cli_library_flag_optional() -> None:
    from photo_library.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["serve"])
    assert args.library is None
    assert not hasattr(args, "http")
    try:
        parser.parse_args(["serve", "--http"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("serve --http")
    args = parser.parse_args(["-d", "/tmp/photos-test", "serve"])
    assert args.library == Path("/tmp/photos-test")


def test_parse_relpath_skips_month_and_vacances() -> None:
    assert parse_relpath("Annee 2016/Juillet 2016/Vacances/Portugal/Lisbonne/x.jpg") == (
        2016,
        "Portugal",
    )
    assert parse_relpath("Annee 2016/Juillet 2016/Vacances/Marseille/Party/x.jpg") == (
        2016,
        "Marseille",
    )
    assert parse_relpath("Annee 2016/Juillet 2016/Vacances/x.jpg") == (2016, None)
    assert parse_relpath("Annee 2016/Juillet 2016/Piscine Party/x.jpg") == (
        2016,
        None,
    )
    assert parse_relpath("Annee 2024/Rome/x.jpg") == (2024, "Rome")
    assert parse_relpath("Annee 2016/IMG.jpg") == (2016, None)
    assert parse_relpath("Annee 2016/Janvier 2016/IMG.jpg") == (2016, None)
    assert parse_relpath("Annee 2026/Vacances Portugal/Lisbonne/x.jpg") == (
        2026,
        "Lisbonne",
    )
    assert parse_relpath("Annee 2026/Vacances Portugal/x.jpg") == (2026, None)
    assert parse_path_labels("Annee 2026/Vacances Portugal/Lisbonne/x.jpg") == (
        2026,
        "Lisbonne",
        "Vacances Portugal",
    )
    assert parse_path_labels("Annee 2026/Vacances Portugal/x.jpg") == (
        2026,
        None,
        "Vacances Portugal",
    )
    assert parse_path_labels("Annee 2026/Croisiere 2026/Tunis/x.jpg") == (
        2026,
        "Tunis",
        "Croisiere 2026",
    )
    assert parse_path_labels("Annee 2016/Juillet 2016/Vacances/Portugal/x.jpg") == (
        2016,
        "Portugal",
        "Vacances",
    )
    assert parse_path_labels("Annee 2024/Rome/x.jpg") == (2024, "Rome", None)
    assert parse_path_labels("Annee 2024/Photos/Paris/x.jpg") == (2024, "Paris", None)
    assert parse_path_labels("Annee 2024/DCIM/x.jpg") == (2024, None, None)
    assert parse_path_labels("Annee 2016/Juillet 2016/Piscine Party/x.jpg") == (
        2016,
        None,
        "Piscine Party",
    )
    assert parse_path_labels("Annee 2020/Fete jardin/x.jpg") == (2020, "Paris", "Fete jardin")
    assert parse_path_labels("Annee 2015/Juin 2015/Floride 2015/Animal Kingdom/x.jpg") == (
        2015,
        "Floride",
        "Floride 2015",
    )
    assert parse_path_labels("Annee 2011/Mai 2011/Soiree a Lisbonne/x.jpg") == (
        2011,
        "Lisbonne",
        "Soiree a Lisbonne",
    )
    assert parse_path_labels("Annee 2011/Novembre 2011/Anniversaire amis/Paris/x.jpg") == (
        2011,
        "Paris",
        "Anniversaire amis",
    )
    assert parse_path_labels("Annee 2024/Anniversaire 2024/Invites/x.jpg") == (
        2024,
        None,
        "Anniversaire 2024",
    )
    assert parse_path_labels("Annee 2023/Bapteme 2023/Photos/x.jpg") == (
        2023,
        None,
        "Bapteme 2023",
    )
    assert parse_relpath("Annee 2026/Croisiere 2026/Tunis/x.jpg") == (
        2026,
        "Tunis",
    )
    assert parse_relpath("Annee 2026/Voyage 2026/Rome/x.jpg") == (2026, "Rome")


def test_complete_places_skips_existing_and_fills_empty() -> None:
    conn = _conn()
    empty = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Vacances/Portugal/a.jpg",
        year=2016,
        place=None,
    )
    vac = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Vacances/Marseille/b.jpg",
        year=2016,
        place="Vacances",
    )
    rome = _insert_media(conn, "Annee 2024/Rome/c.jpg", year=2024, place="Rome")
    locked = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Vacances/Briancon/d.jpg",
        year=2016,
        place="Vacances",
    )
    conn.execute("UPDATE media SET place_locked=1 WHERE id=?", (locked,))
    conn.commit()
    dry = complete_places_from_paths(conn, apply=False)
    assert dry["filled"] == 1
    assert dry["upgraded"] == 1
    assert conn.execute("SELECT place FROM media WHERE id=?", (empty,)).fetchone()[0] is None
    assert conn.execute("SELECT place FROM media WHERE id=?", (vac,)).fetchone()[0] == "Vacances"
    complete_places_from_paths(conn, apply=True)
    assert (
        conn.execute("SELECT place FROM media WHERE id=?", (empty,)).fetchone()[0] == "Portugal"
    )
    assert (
        conn.execute("SELECT place FROM media WHERE id=?", (vac,)).fetchone()[0] == "Marseille"
    )
    assert conn.execute("SELECT place FROM media WHERE id=?", (rome,)).fetchone()[0] == "Rome"
    assert (
        conn.execute("SELECT place FROM media WHERE id=?", (locked,)).fetchone()[0] == "Vacances"
    )
    trip = _insert_media(
        conn,
        "Annee 2026/Vacances Portugal/Lisbonne/e.jpg",
        year=2026,
        place="Vacances Portugal",
    )
    complete_places_from_paths(conn, apply=True)
    assert (
        conn.execute("SELECT place FROM media WHERE id=?", (trip,)).fetchone()[0]
        == "Lisbonne"
    )
    root = _insert_media(
        conn,
        "Annee 2026/Vacances Portugal/f.jpg",
        year=2026,
        place="Vacances Portugal",
    )
    party = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Piscine Party/g.jpg",
        year=2016,
        place="Piscine Party",
    )
    floride = _insert_media(
        conn,
        "Annee 2015/Juin 2015/Floride 2015/h.jpg",
        year=2015,
        place="Floride 2015",
    )
    complete_places_from_paths(conn, apply=True)
    assert conn.execute("SELECT place FROM media WHERE id=?", (root,)).fetchone()[0] is None
    assert conn.execute("SELECT place FROM media WHERE id=?", (party,)).fetchone()[0] is None
    assert conn.execute("SELECT place FROM media WHERE id=?", (floride,)).fetchone()[0] == "Floride"
    conn.close()


def test_complete_moments_from_paths() -> None:
    conn = _conn()
    london = _insert_media(
        conn,
        "Annee 2026/Vacances Portugal/Lisbonne/a.jpg",
        year=2026,
        place="Lisbonne",
    )
    root = _insert_media(
        conn,
        "Annee 2026/Vacances Portugal/b.jpg",
        year=2026,
        place=None,
    )
    rome = _insert_media(conn, "Annee 2024/Rome/c.jpg", year=2024, place="Rome")
    portugal = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Vacances/Portugal/d.jpg",
        year=2016,
        place="Portugal",
    )
    photos = _insert_media(
        conn, "Annee 2024/Photos/Paris/e.jpg", year=2024, place="Paris"
    )
    party = _insert_media(
        conn,
        "Annee 2016/Juillet 2016/Piscine Party/f.jpg",
        year=2016,
        place=None,
    )
    complete_moments_from_paths(conn, apply=True)
    assert (
        conn.execute("SELECT moment FROM media WHERE id=?", (london,)).fetchone()[0]
        == "Vacances Portugal"
    )
    assert (
        conn.execute("SELECT moment FROM media WHERE id=?", (root,)).fetchone()[0]
        == "Vacances Portugal"
    )
    assert conn.execute("SELECT moment FROM media WHERE id=?", (rome,)).fetchone()[0] is None
    assert (
        conn.execute("SELECT moment FROM media WHERE id=?", (portugal,)).fetchone()[0]
        == "Vacances"
    )
    assert (
        conn.execute("SELECT moment FROM media WHERE id=?", (photos,)).fetchone()[0]
        is None
    )
    assert (
        conn.execute("SELECT moment FROM media WHERE id=?", (party,)).fetchone()[0]
        == "Piscine Party"
    )
    conn.close()


def test_index_missing_files(tmp_path: Path) -> None:
    from photo_library.db import connect, init_schema

    lib = tmp_path / "photos"
    cache = tmp_path / "cache"
    dest = lib / "Annee 2016" / "Juillet 2016" / "Vacances" / "Portugal"
    dest.mkdir(parents=True)
    (dest / "x.jpg").write_bytes(b"not-a-real-jpeg")
    conn = connect(cache)
    init_schema(conn, refresh_places=False)
    dry = index_missing_files(conn, lib, cache, apply=False)
    assert dry["missing"] == 1
    assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0
    applied = index_missing_files(conn, lib, cache, apply=True)
    assert applied["indexed"] == 1
    row = conn.execute("SELECT relpath, place, moment FROM media").fetchone()
    assert row["place"] == "Portugal"
    assert row["moment"] == "Vacances"
    conn.close()


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as name:
        test_trash_restore_purge(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_list_trash_page(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_purge_expired_keeps_recent(Path(name))
    with tempfile.TemporaryDirectory() as name:
        test_trash_extra_copies(Path(name))
    test_albums_and_favorite()
    test_init_schema_adds_pair_key_on_existing_db()
    test_copy_keep()
    test_merge_people()
    test_fold_name()
    test_map_aliases()
    test_portugal_map_pin_not_in_sahara()
    test_map_prefers_photo_gps_over_folder_name()
    test_stale_new_york_coords_do_not_stay_in_kansas()
    test_san_jose_california_not_spain()
    test_map_uses_picked_coordinates()
    test_lyon_stays_out_of_paris()
    test_set_place()
    test_kind_of_camcorder_videos()
    test_filters_combine_year_place_person()
    test_filters_combine_place_and_moment()
    test_pair_key_live_photo()
    test_person_filter_includes_live_photo_video()
    test_match_unlabeled_attaches_similar_face()
    test_name_cluster_creates_new_person_without_matching_others()
    test_name_faces_many_only_checked_ids()
    test_people_for_filters_includes_named_years()
    test_year_filter_includes_exif_in_other_folder()
    test_gallery_recent_year_first()
    test_search_place_and_person_not_just_filename()
    test_search_rome_is_whole_word()
    test_cli_library_flag_optional()
    test_parse_relpath_skips_month_and_vacances()
    test_complete_places_skips_existing_and_fills_empty()
    test_complete_moments_from_paths()
    with tempfile.TemporaryDirectory() as name:
        test_index_missing_files(Path(name))
    print("ok")
