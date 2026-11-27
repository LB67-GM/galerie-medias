from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    relpath TEXT NOT NULL UNIQUE,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    kind TEXT NOT NULL,
    year INTEGER,
    place TEXT,
    taken_at TEXT,
    width INTEGER,
    height INTEGER,
    thumb_ok INTEGER NOT NULL DEFAULT 0,
    present INTEGER NOT NULL DEFAULT 1,
    face_scanned INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT,
    dhash TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    place_locked INTEGER NOT NULL DEFAULT 0,
    gps_lat REAL,
    gps_lon REAL,
    gps_scanned INTEGER NOT NULL DEFAULT 0,
    pair_key TEXT,
    scene_scanned INTEGER NOT NULL DEFAULT 0,
    moment TEXT
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS album_media (
    album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    PRIMARY KEY (album_id, media_id)
);

CREATE TABLE IF NOT EXISTS trash (
    media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
    orig_relpath TEXT NOT NULL,
    trash_relpath TEXT NOT NULL,
    trashed_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'deleted',
    restore_id INTEGER
);

CREATE TABLE IF NOT EXISTS place_aliases (
    folder TEXT PRIMARY KEY,
    place TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS place_coords (
    place_key TEXT PRIMARY KEY,
    place TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    cc TEXT
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faces (
    id INTEGER PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    w REAL NOT NULL,
    h REAL NOT NULL,
    score REAL,
    embedding BLOB NOT NULL,
    dim INTEGER NOT NULL,
    engine TEXT NOT NULL,
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    cluster_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_scenes (
    media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    kind TEXT NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (media_id, tag)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    email TEXT NOT NULL DEFAULT '',
    session_epoch INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cinema_items (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL DEFAULT 'file',
    relpath TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'movie',
    year INTEGER,
    season INTEGER,
    episode INTEGER,
    director TEXT NOT NULL DEFAULT '',
    overview TEXT NOT NULL DEFAULT '',
    wikidata_id TEXT NOT NULL DEFAULT '',
    metadata_locked INTEGER NOT NULL DEFAULT 0,
    duration_s REAL,
    width INTEGER,
    height INTEGER,
    size INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    poster_ok INTEGER NOT NULL DEFAULT 0,
    present INTEGER NOT NULL DEFAULT 1,
    indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS cinema_item_categories (
    item_id INTEGER NOT NULL REFERENCES cinema_items(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    PRIMARY KEY (item_id, category)
);

CREATE TABLE IF NOT EXISTS cinema_progress (
    user_key TEXT NOT NULL,
    item_key TEXT NOT NULL,
    title_index INTEGER NOT NULL DEFAULT 0,
    position_s REAL NOT NULL DEFAULT 0,
    duration_s REAL NOT NULL DEFAULT 0,
    audio_idx INTEGER,
    subtitle_idx INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_key, item_key, title_index)
);

CREATE TABLE IF NOT EXISTS cinema_trash (
    item_id INTEGER PRIMARY KEY REFERENCES cinema_items(id) ON DELETE CASCADE,
    orig_relpath TEXT NOT NULL,
    trash_relpath TEXT NOT NULL,
    trashed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_media_year ON media(year);
CREATE INDEX IF NOT EXISTS idx_media_place ON media(place);
CREATE INDEX IF NOT EXISTS idx_media_kind ON media(kind);
CREATE INDEX IF NOT EXISTS idx_media_taken ON media(taken_at);
CREATE INDEX IF NOT EXISTS idx_media_present ON media(present);
CREATE INDEX IF NOT EXISTS idx_faces_media ON faces(media_id);
CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id);
CREATE INDEX IF NOT EXISTS idx_faces_person_media ON faces(person_id, media_id);
CREATE INDEX IF NOT EXISTS idx_faces_cluster ON faces(cluster_id);
CREATE INDEX IF NOT EXISTS idx_album_media_media ON album_media(media_id);
CREATE INDEX IF NOT EXISTS idx_trash_trashed ON trash(trashed_at);
CREATE INDEX IF NOT EXISTS idx_media_scenes_tag ON media_scenes(tag);
CREATE INDEX IF NOT EXISTS idx_media_scenes_kind ON media_scenes(kind);
"""


def db_path(cache: Path) -> Path:
    return cache / "library.sqlite"


def connect(cache: Path) -> sqlite3.Connection:
    cache.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path(cache)), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=8000")
    return conn


def init_schema(conn: sqlite3.Connection, *, refresh_places: bool = True) -> None:
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(media)")}
    if "dhash" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN dhash TEXT")
    if "favorite" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
    if "place_locked" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN place_locked INTEGER NOT NULL DEFAULT 0")
    if "gps_lat" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN gps_lat REAL")
    if "gps_lon" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN gps_lon REAL")
    if "gps_scanned" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN gps_scanned INTEGER NOT NULL DEFAULT 0")
    if "pair_key" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN pair_key TEXT")
    if "scene_scanned" not in cols:
        conn.execute(
            "ALTER TABLE media ADD COLUMN scene_scanned INTEGER NOT NULL DEFAULT 0"
        )
    if "moment" not in cols:
        conn.execute("ALTER TABLE media ADD COLUMN moment TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_moment ON media(moment)")
    from photo_library.paths import pair_key_of

    missing_keys = conn.execute(
        "SELECT id, relpath FROM media WHERE pair_key IS NULL OR pair_key=''"
    ).fetchall()
    if missing_keys:
        conn.executemany(
            "UPDATE media SET pair_key=? WHERE id=?",
            [(pair_key_of(row["relpath"]), int(row["id"])) for row in missing_keys],
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_pair_key ON media(pair_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_dhash ON media(dhash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_favorite ON media(favorite)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_gps ON media(gps_scanned)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS album_media (
            album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
            added_at TEXT NOT NULL,
            PRIMARY KEY (album_id, media_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trash (
            media_id INTEGER PRIMARY KEY REFERENCES media(id) ON DELETE CASCADE,
            orig_relpath TEXT NOT NULL,
            trash_relpath TEXT NOT NULL,
            trashed_at TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT 'deleted',
            restore_id INTEGER
        )
        """
    )
    trash_cols = {row[1] for row in conn.execute("PRAGMA table_info(trash)")}
    if "reason" not in trash_cols:
        conn.execute("ALTER TABLE trash ADD COLUMN reason TEXT NOT NULL DEFAULT 'deleted'")
    if "restore_id" not in trash_cols:
        conn.execute("ALTER TABLE trash ADD COLUMN restore_id INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_album_media_media ON album_media(media_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trash_trashed ON trash(trashed_at)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media_scenes (
            media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            kind TEXT NOT NULL,
            score REAL NOT NULL,
            PRIMARY KEY (media_id, tag)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked INTEGER NOT NULL DEFAULT 0,
            email TEXT NOT NULL DEFAULT '',
            session_epoch INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "failed_attempts" not in user_cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if "locked" not in user_cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN locked INTEGER NOT NULL DEFAULT 0"
        )
    if "email" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
    if "session_epoch" not in user_cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 0"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email "
        "ON users(email) WHERE email != ''"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_resets_hash ON password_resets(token_hash)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_media_scene_scanned ON media(scene_scanned)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_scenes_tag ON media_scenes(tag)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_media_scenes_kind ON media_scenes(kind)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS place_aliases (
            folder TEXT PRIMARY KEY,
            place TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS place_coords (
            place_key TEXT PRIMARY KEY,
            place TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            cc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cinema_items (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL DEFAULT 'file',
            relpath TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            media_type TEXT NOT NULL DEFAULT 'movie',
            year INTEGER,
            season INTEGER,
            episode INTEGER,
            director TEXT NOT NULL DEFAULT '',
            overview TEXT NOT NULL DEFAULT '',
            wikidata_id TEXT NOT NULL DEFAULT '',
            metadata_locked INTEGER NOT NULL DEFAULT 0,
            duration_s REAL,
            width INTEGER,
            height INTEGER,
            size INTEGER NOT NULL DEFAULT 0,
            mtime_ns INTEGER NOT NULL DEFAULT 0,
            poster_ok INTEGER NOT NULL DEFAULT 0,
            present INTEGER NOT NULL DEFAULT 1,
            indexed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cinema_item_categories (
            item_id INTEGER NOT NULL REFERENCES cinema_items(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            PRIMARY KEY (item_id, category)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cinema_progress (
            user_key TEXT NOT NULL,
            item_key TEXT NOT NULL,
            title_index INTEGER NOT NULL DEFAULT 0,
            position_s REAL NOT NULL DEFAULT 0,
            duration_s REAL NOT NULL DEFAULT 0,
            audio_idx INTEGER,
            subtitle_idx INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_key, item_key, title_index)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cinema_items_present ON cinema_items(present)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cinema_items_type ON cinema_items(media_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cinema_items_year ON cinema_items(year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cinema_cat_cat ON cinema_item_categories(category)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cinema_progress_user ON cinema_progress(user_key, updated_at)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cinema_trash (
            item_id INTEGER PRIMARY KEY REFERENCES cinema_items(id) ON DELETE CASCADE,
            orig_relpath TEXT NOT NULL,
            trash_relpath TEXT NOT NULL,
            trashed_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cinema_trash_at ON cinema_trash(trashed_at)")
    conn.commit()
    from photo_library.albums import ensure_favorites_album

    ensure_favorites_album(conn)
    if refresh_places:
        refresh_places_from_paths(conn)


def refresh_places_from_paths(conn: sqlite3.Connection) -> None:
    """Remplit lieux et moments depuis le chemin. N’écrase pas un lieu déjà nommé (sauf enveloppe)."""
    from photo_library.places import complete_moments_from_paths, complete_places_from_paths

    complete_places_from_paths(conn, apply=True, upgrade_generic=True)
    complete_moments_from_paths(conn, apply=True)


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
