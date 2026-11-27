#!/usr/bin/env python3
"""Tests Phase 1 Cinéma : migration, métadonnées Wikidata, scan, HLS et droits API."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library import user_config as uc  # noqa: E402
from photo_library.auth import create_user  # noqa: E402
from photo_library.cinema_meta import (  # noqa: E402
    fetch_wikidata_metadata,
    parse_local_metadata,
)
from photo_library.cinema_probe import parse_ffprobe_json, probe_media  # noqa: E402
from photo_library.cinema_scan import (  # noqa: E402
    cinema_filters,
    continue_watching,
    discover_cinema_entries,
    enrich_cinema_library,
    get_cinema_item,
    list_cinema_items,
    save_cinema_progress,
    scan_cinema_library,
    update_cinema_metadata,
)
from photo_library.db import connect, init_schema  # noqa: E402
from photo_library.ffmpeg_util import cinema_ffmpeg_bin  # noqa: E402
from photo_library.hls_stream import HlsSessionManager  # noqa: E402


def _make_tiny_mp4(dest: Path, *, duration: float = 2.0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        cinema_ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=160x120:rate=24:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-400:]
    return dest


def _asgi_call(
    app,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    cookie: str = "",
) -> tuple[int, bytes, dict[str, str]]:
    body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
    headers: list[tuple[bytes, bytes]] = []
    if json_body is not None:
        headers.append((b"content-type", b"application/json"))
    if cookie:
        headers.append((b"cookie", cookie.encode("latin-1")))
    qs = b""
    raw_path = path
    if "?" in path:
        raw_path, qs_s = path.split("?", 1)
        qs = qs_s.encode("ascii")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": raw_path,
        "raw_path": raw_path.encode("utf-8"),
        "query_string": qs,
        "headers": headers,
        "client": ("192.168.1.50", 54321),
        "server": ("127.0.0.1", 8765),
    }
    sent = False
    status = 500
    resp_headers: dict[str, str] = {}
    chunks: list[bytes] = []

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(msg):
        nonlocal status
        if msg["type"] == "http.response.start":
            status = int(msg["status"])
            for k, v in msg.get("headers") or []:
                resp_headers[k.decode("latin-1").lower()] = v.decode("latin-1")
        elif msg["type"] == "http.response.body":
            chunks.append(msg.get("body") or b"")

    asyncio.run(app(scope, receive, send))
    return status, b"".join(chunks), resp_headers


def test_parse_local_metadata_real_patterns() -> None:
    p1 = parse_local_metadata("1960 - Psychose.avi")
    assert p1["title"] == "Psychose"
    assert p1["year"] == 1960
    assert p1["media_type"] == "movie"

    p2 = parse_local_metadata("Home - 2009.avi")
    assert p2["title"] == "Home"
    assert p2["year"] == 2009

    p3 = parse_local_metadata("1946.-.Frank.Capra.-.La.Vie.Est.Belle.(It's.A.Wonderful.Life).avi")
    assert p3["year"] == 1946
    assert p3["director"] == "Frank Capra"
    assert p3["title"] == "La Vie Est Belle"

    p4 = parse_local_metadata("Hugo.Cabret.FRENCH.DVDRip.REPACK.1CD.XviD-PIKE17.avi")
    assert p4["title"] == "Hugo Cabret"

    p5 = parse_local_metadata("Series/Breaking.Bad.S01E02.720p.mkv")
    assert p5["title"] == "Breaking Bad"
    assert p5["media_type"] == "series"
    assert p5["season"] == 1
    assert p5["episode"] == 2

    p6 = parse_local_metadata("AC-DC - Hells Bells.m4v", duration_s=312.0)
    assert p6["media_type"] == "clip"
    assert "clip" in p6["categories"]


def test_wikidata_enrichment_mocked() -> None:
    def fake_fetcher(url: str) -> dict:
        if "action=wbsearchentities" in url:
            return {"search": [{"id": "Q163038"}]}
        if "ids=Q163038" in url:
            return {
                "entities": {
                    "Q163038": {
                        "labels": {"fr": {"value": "Psychose"}},
                        "descriptions": {"fr": {"value": "film d'Alfred Hitchcock"}},
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q11424"}}}}],
                            "P577": [{"mainsnak": {"datavalue": {"value": {"time": "+1960-06-16T00:00:00Z"}}}}],
                            "P136": [
                                {"mainsnak": {"datavalue": {"value": {"id": "Q2484376"}}}},
                                {"mainsnak": {"datavalue": {"value": {"id": "Q200092"}}}},
                            ],
                            "P57": [{"mainsnak": {"datavalue": {"value": {"id": "Q7374"}}}}],
                        },
                        "sitelinks": {"frwiki": {"site": "frwiki", "title": "Psychose (film)"}},
                    }
                }
            }
        if "ids=Q7374" in url:
            return {"entities": {"Q7374": {"labels": {"fr": {"value": "Alfred Hitchcock"}}}}}
        if "wikipedia.org/api/rest_v1/page/summary" in url:
            return {"extract": "Psychose est un film américain réalisé par Alfred Hitchcock en 1960."}
        return {}

    meta = fetch_wikidata_metadata("Psychose", year=1960, lang="fr", fetcher=fake_fetcher)
    assert meta is not None
    assert meta["wikidata_id"] == "Q163038"
    assert meta["title"] == "Psychose"
    assert meta["year"] == 1960
    assert meta["media_type"] == "movie"
    assert meta["director"] == "Alfred Hitchcock"
    assert "thriller" in meta["categories"]
    assert "horreur" in meta["categories"]
    assert "Alfred Hitchcock" in meta["overview"]


def test_ffprobe_json_parsing() -> None:
    probe = parse_ffprobe_json(
        {
            "format": {"duration": "5400.5", "tags": {"title": "Test", "date": "2010"}},
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1920, "height": 1080},
                {"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2, "tags": {"language": "fre"}},
                {"index": 2, "codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "fre"}},
                {"index": 3, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle", "tags": {"language": "eng"}},
            ],
            "chapters": [{"start_time": "0.0", "end_time": "600.0", "tags": {"title": "Intro"}}],
        }
    )
    assert probe.readable
    assert probe.width == 1920 and probe.height == 1080
    assert len(probe.audio_tracks) == 1
    assert probe.audio_tracks[0].language == "fre"
    assert len(probe.subtitle_tracks) == 2
    assert probe.subtitle_tracks[0].is_text is True
    assert probe.subtitle_tracks[1].is_text is False
    assert len(probe.chapters) == 1


def test_discover_dvd_and_bluray_structures(tmp_path: Path) -> None:
    (tmp_path / "MonFilmDVD" / "VIDEO_TS").mkdir(parents=True)
    (tmp_path / "MonFilmDVD" / "VIDEO_TS" / "VIDEO_TS.IFO").write_bytes(b"IFO")
    (tmp_path / "MonFilmDVD" / "VIDEO_TS" / "VTS_01_1.VOB").write_bytes(b"VOB")

    (tmp_path / "MonBluray" / "BDMV").mkdir(parents=True)
    (tmp_path / "MonBluray" / "BDMV" / "index.bdmv").write_bytes(b"BDMV")
    (tmp_path / "MonBluray" / "BDMV" / "STREAM").mkdir()
    (tmp_path / "MonBluray" / "BDMV" / "STREAM" / "00001.m2ts").write_bytes(b"M2TS")

    (tmp_path / "Inception (2010).mp4").write_bytes(b"MP4")
    (tmp_path / "Thumbs.db").write_bytes(b"NO")

    found = discover_cinema_entries(tmp_path)
    by_rel = {rel: stype for stype, _p, rel in found}
    assert by_rel == {
        "Inception (2010).mp4": "file",
        "MonBluray": "bluray",
        "MonFilmDVD": "dvd",
    }


def test_settings_migration_and_cinema_dir_status(tmp_path: Path, monkeypatch) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr(uc, "data_dir", lambda: cfg_dir)
    # Simule une config 3.0 sans cinema_dir ni optical_device
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"library_src": "/tmp/photos"}), encoding="utf-8")
    loaded = uc.load_settings()
    assert loaded["library_src"] == "/tmp/photos"
    assert loaded["cinema_dir"] == ""
    assert loaded["optical_device"] == ""

    assert uc.cinema_dir_status("")["status"] == "unconfigured"
    local_dir = tmp_path / "my-cinema"
    assert uc.cinema_dir_status(str(local_dir), create_local=False)["status"] == "missing"
    assert uc.cinema_dir_status(str(local_dir), create_local=True)["status"] == "ready"
    assert local_dir.is_dir()

    missing_mnt = uc.cinema_dir_status("/mnt/definitely-not-mounted-xyz", create_local=True)
    assert missing_mnt["status"] == "missing_mount"


def test_scan_hls_stream_and_api_rbac(tmp_path: Path, monkeypatch) -> None:
    from photo_library.app import create_app

    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr(uc, "data_dir", lambda: cfg_dir)

    lib_dir = tmp_path / "photos"
    lib_dir.mkdir()
    cinema_dir = tmp_path / "cinema"
    cinema_dir.mkdir()
    cache_dir = tmp_path / "cache"

    movie_path = _make_tiny_mp4(cinema_dir / "1960 - Psychose.mp4", duration=2.5)
    assert probe_media(movie_path).readable

    uc.save_settings({"cinema_dir": str(cinema_dir), "optical_device": ""})

    # Scan + enrichissement + verrouillage
    conn = connect(cache_dir)
    init_schema(conn, refresh_places=False)
    res = scan_cinema_library(conn, cinema_dir, cache_dir)
    assert res["total"] == 1 and res["added"] == 1

    items = list_cinema_items(conn)["items"]
    assert len(items) == 1
    item_id = items[0]["id"]
    assert items[0]["title"] == "Psychose"
    assert items[0]["year"] == 1960
    assert items[0]["poster_ok"] is True

    updated = update_cinema_metadata(
        conn,
        item_id,
        title="Psychose (Chef-d'oeuvre)",
        media_type="movie",
        year=1960,
        director="Alfred Hitchcock",
        categories=["thriller", "policier"],
        metadata_locked=True,
    )
    assert updated is not None and updated["metadata_locked"] is True
    assert set(updated["categories"]) == {"thriller", "policier"}

    # Enrichissement ne touche pas aux fiches verrouillées
    enr = enrich_cinema_library(conn, fetcher=lambda _u: {})
    assert enr["total"] == 0

    flt = cinema_filters(conn)
    assert flt["total"] == 1
    assert any(c["value"] == "policier" for c in flt["categories"])

    # Reprise de lecture
    save_cinema_progress(conn, user_key="user:2", item_key=f"item:{item_id}", position_s=45.0, duration_s=180.0)
    cw = continue_watching(conn, "user:2")
    assert len(cw) == 1 and cw[0]["id"] == item_id

    # Comptes admin + viewer pour tester les droits API
    create_user(conn, "admin1", "secret123", "admin", email="admin@example.com")
    create_user(conn, "viewer1", "secret123", "viewer", email="viewer@example.com")
    conn.close()

    # Test HLS réel via HlsSessionManager
    mgr = HlsSessionManager(cache_dir)
    try:
        sess = mgr.start_session(movie_path, item_key=f"item:{item_id}", quality="auto")
        sid = sess["session_id"]
        m3u8 = mgr.resolve_file(sid, "index.m3u8")
        assert m3u8 is not None and "#EXTM3U" in m3u8.read_text(encoding="utf-8")
        seg0 = mgr.resolve_file(sid, "seg_00000.ts")
        assert seg0 is not None and seg0.stat().st_size > 128
        assert mgr.stop_session(sid) is True
        assert mgr.resolve_file(sid, "index.m3u8") is None
    finally:
        mgr.stop_all()

    # Test API FastAPI + RBAC
    app = create_app(lib_dir, cache_dir)
    try:
        st, _b, hdrs = _asgi_call(
            app, "POST", "/api/auth/login", json_body={"username": "viewer1", "password": "secret123"}
        )
        assert st == 200
        viewer_cookie = hdrs["set-cookie"].split(";", 1)[0]

        st, body, _h = _asgi_call(app, "GET", "/api/cinema/items?category=policier", cookie=viewer_cookie)
        assert st == 200
        assert json.loads(body)["total"] == 1

        st, body, _h = _asgi_call(app, "GET", f"/api/cinema/items/{item_id}/info", cookie=viewer_cookie)
        assert st == 200
        assert json.loads(body)["probe"]["readable"] is True

        st, body, _h = _asgi_call(
            app, "POST", "/api/cinema/stream/start", json_body={"item_id": item_id}, cookie=viewer_cookie
        )
        assert st == 200
        sid = json.loads(body)["session_id"]

        st, body, _h = _asgi_call(app, "GET", f"/api/cinema/stream/{sid}/index.m3u8", cookie=viewer_cookie)
        assert st == 200 and b"#EXTM3U" in body

        st, _b, _h = _asgi_call(app, "POST", f"/api/cinema/stream/{sid}/stop", cookie=viewer_cookie)
        assert st == 200

        st, _b, _h = _asgi_call(
            app,
            "POST",
            "/api/cinema/progress",
            json_body={"item_id": item_id, "position_s": 30.0, "duration_s": 120.0},
            cookie=viewer_cookie,
        )
        assert st == 200

        st, body, _h = _asgi_call(
            app,
            "POST",
            "/api/cinema/progress/clear",
            json_body={"item_id": item_id},
            cookie=viewer_cookie,
        )
        assert st == 200 and json.loads(body)["cleared"] == 1
        st, body, _h = _asgi_call(app, "GET", "/api/cinema/continue", cookie=viewer_cookie)
        assert st == 200 and json.loads(body)["items"] == []

        # Le viewer ne peut ni scanner, ni enrichir, ni modifier la fiche, ni supprimer
        st, _b, _h = _asgi_call(app, "POST", "/api/cinema/scan", json_body={}, cookie=viewer_cookie)
        assert st == 403
        st, _b, _h = _asgi_call(
            app, "POST", f"/api/cinema/items/{item_id}/metadata", json_body={"title": "Hack"}, cookie=viewer_cookie
        )
        assert st == 403
        st, _b, _h = _asgi_call(app, "POST", f"/api/cinema/items/{item_id}/trash", cookie=viewer_cookie)
        assert st == 403

        # Admin : corbeille Cinéma (mise à la corbeille -> restauration -> purge)
        st, _b, hdrs = _asgi_call(
            app, "POST", "/api/auth/login", json_body={"username": "admin1", "password": "secret123"}
        )
        assert st == 200
        admin_cookie = hdrs["set-cookie"].split(";", 1)[0]

        st, body, _h = _asgi_call(app, "POST", f"/api/cinema/items/{item_id}/trash", cookie=admin_cookie)
        assert st == 200 and not movie_path.exists()
        st, body, _h = _asgi_call(app, "GET", "/api/cinema/trash", cookie=admin_cookie)
        assert st == 200 and json.loads(body)["count"] == 1
        st, body, _h = _asgi_call(app, "GET", "/api/status", cookie=admin_cookie)
        assert st == 200 and json.loads(body)["trash"] == 1

        st, body, _h = _asgi_call(app, "POST", f"/api/cinema/trash/{item_id}/restore", cookie=admin_cookie)
        assert st == 200 and movie_path.exists()
        st, body, _h = _asgi_call(app, "GET", "/api/cinema/trash", cookie=admin_cookie)
        assert st == 200 and json.loads(body)["count"] == 0

        st, _b, _h = _asgi_call(app, "POST", f"/api/cinema/items/{item_id}/trash", cookie=admin_cookie)
        assert st == 200
        st, _b, _h = _asgi_call(app, "POST", f"/api/cinema/trash/{item_id}/purge", cookie=admin_cookie)
        assert st == 200 and not movie_path.exists()
        st, body, _h = _asgi_call(app, "GET", "/api/cinema/items", cookie=admin_cookie)
        assert st == 200 and json.loads(body)["total"] == 0
    finally:
        app.state.hls.stop_all()


def test_optical_dvd_bluray_and_disc_fallback(tmp_path: Path) -> None:
    from photo_library.cinema_optical import (
        detect_optical_kind,
        inspect_configured_disc,
        inspect_optical_source,
    )
    from photo_library.version import APP_VERSION

    assert APP_VERSION == "4.0"

    # Serveur sans lecteur optique : aucune erreur, configured=False
    empty_disc = inspect_configured_disc("")
    assert empty_disc["configured"] is False
    assert empty_disc["present"] is False

    # Lecteur optique configuré mais absent
    missing_disc = inspect_configured_disc(str(tmp_path / "no-drive"))
    assert missing_disc["configured"] is True
    assert missing_disc["present"] is False

    # Simulation d'une structure DVD (VIDEO_TS + VTS_01_1.VOB en MPEG-2/MP2 réel)
    dvd_dir = tmp_path / "MonDVD"
    (dvd_dir / "VIDEO_TS").mkdir(parents=True)
    vob = dvd_dir / "VIDEO_TS" / "VTS_01_1.VOB"
    proc = subprocess.run(
        [
            cinema_ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=25:duration=1.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1.5",
            "-c:v",
            "mpeg2video",
            "-c:a",
            "mp2",
            "-shortest",
            str(vob),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-400:]
    assert detect_optical_kind(dvd_dir) == "dvd"
    dvd_info = inspect_optical_source(dvd_dir)
    assert dvd_info["kind"] == "dvd"
    assert dvd_info["readable"] is True
    assert len(dvd_info["titles"]) == 1

    # Simulation d'une structure Blu-ray (BDMV/STREAM/00001.m2ts)
    bd_dir = tmp_path / "MonBluray"
    (bd_dir / "BDMV" / "STREAM").mkdir(parents=True)
    _make_tiny_mp4(bd_dir / "BDMV" / "STREAM" / "00001.m2ts", duration=1.5)
    assert detect_optical_kind(bd_dir) == "bluray"
    bd_info = inspect_optical_source(bd_dir)
    assert bd_info["kind"] == "bluray"
    assert bd_info["readable"] is True
    assert len(bd_info["titles"]) == 1

    # Disque de données monté sur le lecteur configuré
    data_disc = tmp_path / "DiscData"
    _make_tiny_mp4(data_disc / "Film.mp4", duration=1.5)
    disc_res = inspect_configured_disc(str(data_disc))
    assert disc_res["configured"] is True
    assert disc_res["present"] is True
    assert disc_res["kind"] == "data"
    assert disc_res["readable"] is True
    assert len(disc_res["titles"]) == 1


if __name__ == "__main__":
    import tempfile

    test_parse_local_metadata_real_patterns()
    test_wikidata_enrichment_mocked()
    test_ffprobe_json_parsing()
    print("basic ok")
