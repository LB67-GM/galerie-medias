#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from photo_library.auth import viewer_allowed  # noqa: E402
from photo_library.cast import (  # noqa: E402
    didl_metadata,
    is_private_http_url,
    make_token,
    parse_renderer_description,
    parse_ssdp_headers,
    parse_token,
    resolve_cast_file,
    soap_envelope,
)
from photo_library.db import connect, init_schema  # noqa: E402


XML = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <friendlyName>Salon LG</friendlyName>
    <manufacturer>LG Electronics</manufacturer>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/AVTransport/control</controlURL>
      </service>
    </serviceList>
  </device>
</root>
"""


def test_token_roundtrip() -> None:
    secret = b"x" * 32
    token = make_token(secret, 42, "preview", now=1_000_000)
    media_id, variant = parse_token(secret, token, now=1_000_001)
    assert media_id == 42
    assert variant == "preview"


def test_token_bad_sig() -> None:
    secret = b"x" * 32
    token = make_token(secret, 1, "preview", now=1_000_000)
    try:
        parse_token(b"y" * 32, token, now=1_000_001)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_token_expired() -> None:
    secret = b"x" * 32
    token = make_token(secret, 1, "preview", now=100)
    try:
        parse_token(secret, token, now=100 + 5 * 3600)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "expiré" in str(exc)


def test_private_urls() -> None:
    assert is_private_http_url("http://192.168.1.40:7676/AV")
    assert is_private_http_url("http://tv.local/AV")
    assert not is_private_http_url("http://example.com/AV")
    assert not is_private_http_url("file:///etc/passwd")


def test_samsung_dmr_xml_parses() -> None:
    xml = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
    <friendlyName>Salon Samsung</friendlyName>
    <manufacturer>Samsung Electronics</manufacturer>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/upnp/control/AVTransport1</controlURL>
      </service>
    </serviceList>
  </device>
</root>
"""
    info = parse_renderer_description(xml, "http://192.168.1.41:9197/dmr")
    assert info is not None
    assert info["name"] == "Salon Samsung"
    assert info["control_url"].endswith("/upnp/control/AVTransport1")


def test_parse_ssdp_and_device_xml() -> None:
    blob = b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.40:7676/desc.xml\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
    headers = parse_ssdp_headers(blob)
    assert headers["LOCATION"] == "http://192.168.1.40:7676/desc.xml"
    info = parse_renderer_description(XML, "http://192.168.1.40:7676/desc.xml")
    assert info is not None
    assert info["name"] == "Salon LG"
    assert info["control_url"] == "http://192.168.1.40:7676/AVTransport/control"


def test_didl_and_soap() -> None:
    didl = didl_metadata("http://192.168.1.20:8766/api/cast/file/t", "a.jpg", "image/jpeg", video=False)
    assert "imageItem" in didl
    env = soap_envelope("Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
    assert b"Play" in env
    assert b"AVTransport" in env


def test_viewer_can_cast() -> None:
    assert viewer_allowed("/api/cast/devices", "GET")
    assert viewer_allowed("/api/cast/play", "POST")
    assert viewer_allowed("/api/cast/stop", "POST")
    assert viewer_allowed("/api/cast/file/1.preview.1.abc", "GET")


def test_resolve_preview(tmp_path: Path) -> None:
    from photo_library.auth import session_secret

    lib = tmp_path / "lib"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    photo = lib / "a.jpg"
    Image.new("RGB", (80, 60), (20, 40, 80)).save(photo, "JPEG")
    conn = connect(cache)
    init_schema(conn, refresh_places=False)
    conn.execute(
        "INSERT INTO media (relpath, size, mtime_ns, kind, year, present) "
        "VALUES (?,?,?,?,?,1)",
        ("a.jpg", photo.stat().st_size, 1, "photo", 2024),
    )
    conn.commit()
    media_id = int(conn.execute("SELECT id FROM media").fetchone()[0])
    conn.close()
    secret = session_secret(cache)
    token = make_token(secret, media_id, "preview")
    path, mime = resolve_cast_file(lib, cache, secret, token)
    assert mime == "image/jpeg"
    assert path.suffix.lower() == ".jpg"
    assert path.is_file()


def test_cast_file_public_asgi(tmp_path: Path) -> None:
    from photo_library.app import create_app
    from photo_library.auth import session_secret
    from test_accounts_scenes import _asgi_call

    lib = tmp_path / "lib"
    cache = tmp_path / "cache"
    lib.mkdir()
    cache.mkdir()
    photo = lib / "b.jpg"
    Image.new("RGB", (40, 30), (90, 10, 10)).save(photo, "JPEG")
    conn = connect(cache)
    init_schema(conn, refresh_places=False)
    conn.execute(
        "INSERT INTO media (relpath, size, mtime_ns, kind, year, present) "
        "VALUES (?,?,?,?,?,1)",
        ("b.jpg", photo.stat().st_size, 1, "photo", 2024),
    )
    conn.commit()
    media_id = int(conn.execute("SELECT id FROM media").fetchone()[0])
    conn.close()
    app = create_app(lib, cache)
    secret = session_secret(cache)
    token = make_token(secret, media_id, "preview")
    status, payload, hdrs = _asgi_call(app, "GET", f"/api/cast/file/{token}")
    assert status == 200
    assert "image/jpeg" in hdrs.get("content-type", "")
    assert payload.startswith(b"\xff\xd8")
    status, _payload, _hdrs = _asgi_call(app, "GET", "/api/cast/file/not-a-token")
    assert status == 403


def test_play_rejects_public_internet() -> None:
    from photo_library.app import create_app
    from test_accounts_scenes import _asgi_call

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as name:
        lib = Path(name) / "lib"
        cache = Path(name) / "cache"
        lib.mkdir()
        cache.mkdir()
        app = create_app(lib, cache)
        status, payload, _hdrs = _asgi_call(
            app,
            "POST",
            "/api/cast/play",
            json_body={"control_url": "http://example.com/AV", "media_id": 1},
        )
        assert status == 400
        assert b"refus" in payload.lower()


if __name__ == "__main__":
    test_token_roundtrip()
    test_token_bad_sig()
    test_token_expired()
    test_private_urls()
    test_parse_ssdp_and_device_xml()
    test_samsung_dmr_xml_parses()
    test_didl_and_soap()
    test_viewer_can_cast()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as name:
        test_resolve_preview(Path(name))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as name:
        test_cast_file_public_asgi(Path(name))
    test_play_rejects_public_internet()
    print("ok")
