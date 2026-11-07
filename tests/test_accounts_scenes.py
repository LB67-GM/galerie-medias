#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.auth import (  # noqa: E402
    complete_password_reset,
    create_user,
    decode_session,
    encode_session,
    hash_password,
    issue_reset_token,
    login_user,
    MAX_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LEN,
    set_user_password,
    unlock_user,
    user_count,
    verify_password,
    viewer_allowed,
)
from photo_library.db import connect, init_schema  # noqa: E402
from photo_library.scenes import classify_image, heuristic_tags  # noqa: E402
from photo_library.app import media_from_where  # noqa: E402


def _tmp():
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def test_password_roundtrip() -> None:
    stored = hash_password("secret-ok")
    assert verify_password("secret-ok", stored)
    assert not verify_password("nope", stored)


def test_no_users_means_open_site() -> None:
    with _tmp() as name:
        cache = Path(name)
        conn = connect(cache)
        init_schema(conn, refresh_places=False)
        assert user_count(conn) == 0
        conn.close()


def test_first_user_is_admin() -> None:
    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        user = create_user(conn, "papa", "motdepasse", "lecture")
        assert user["role"] == "admin"
        assert user["first"] is True
        login = login_user(conn, "papa", "motdepasse")
        assert login["username"] == "papa"
        create_user(conn, "enfant", "motdepasse", "lecture")
        kid = login_user(conn, "enfant", "motdepasse")
        assert kid["role"] == "viewer"
        conn.close()


def test_password_reset_and_session() -> None:
    import json
    import sqlite3

    with _tmp() as name:
        cache = Path(name)
        raw = sqlite3.connect(cache / "library.sqlite")
        raw.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        raw.commit()
        raw.close()
        conn = connect(cache)
        init_schema(conn, refresh_places=False)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        assert "email" in cols and "session_epoch" in cols
        create_user(conn, "papa", "secret12", "admin", email="papa@example.com")
        try:
            create_user(conn, "leo", "secret12", "lecture", email="PAPA@example.com")
            raise AssertionError("duplicate email")
        except ValueError as exc:
            assert getattr(exc, "code", "") == "email_taken"
        assert issue_reset_token(conn, "nobody@example.com") is None
        token = issue_reset_token(conn, "Papa@Example.com")
        assert token
        assert issue_reset_token(conn, "papa@example.com") == ""
        user = login_user(conn, "papa", "secret12")
        secret = b"k" * 32
        cookie = encode_session(user, secret)
        assert decode_session(cookie, conn, secret)["username"] == "papa"
        complete_password_reset(conn, token, "nouveaupass")
        assert decode_session(cookie, conn, secret) is None
        try:
            login_user(conn, "papa", "secret12")
            raise AssertionError("old password should fail")
        except ValueError:
            pass
        assert login_user(conn, "papa", "nouveaupass")["username"] == "papa"
        try:
            complete_password_reset(conn, token, "autrepass1")
            raise AssertionError("token reused")
        except ValueError as exc:
            assert getattr(exc, "code", "") == "reset_bad"
        conn.close()

    with _tmp() as name:
        base = Path(name)
        import photo_library.user_config as uc

        previous = uc.data_dir
        uc.data_dir = lambda: base
        try:
            saved = uc.save_settings(
                {
                    "smtp_host": "smtp.example.com",
                    "smtp_password": "secret-mail",
                    "smtp_from": "a@b.c",
                    "public_url": "https://photos.example.com:8765",
                }
            )
            assert saved["smtp_password"] == "secret-mail"
            again = uc.save_settings({"smtp_host": "smtp.example.com"})
            assert again["smtp_password"] == "secret-mail"
            public = uc.public_settings()
            assert public["smtp_password_set"] is True
            assert "smtp_password" not in public
            raw = json.loads((base / "config.json").read_text(encoding="utf-8"))
            assert "secret-mail" not in json.dumps(raw)
            assert raw["smtp_password_enc"]
            assert raw["public_url"] == "https://photos.example.com:8765"
            spaced = uc.save_settings({"smtp_password": "abcd efgh ijkl mnop"})
            assert spaced["smtp_password"] == "abcdefghijklmnop"
        finally:
            uc.data_dir = previous


def test_password_too_short() -> None:
    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        try:
            create_user(conn, "papa", "1234567", "admin")
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert str(MIN_PASSWORD_LEN) in str(exc)
        conn.close()


def test_login_lockout_three_tries() -> None:
    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        create_user(conn, "papa", "motdepasse", "admin")
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            try:
                login_user(conn, "papa", "mauvais")
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
        try:
            login_user(conn, "papa", "mauvais")
            raise AssertionError("expected PermissionError")
        except PermissionError:
            pass
        try:
            login_user(conn, "papa", "motdepasse")
            raise AssertionError("locked account should reject good password")
        except PermissionError:
            pass
        unlock_user(conn, "papa")
        user = login_user(conn, "papa", "motdepasse")
        assert user["username"] == "papa"
        set_user_password(conn, "papa", "nouveaupass")
        user = login_user(conn, "papa", "nouveaupass")
        assert user["username"] == "papa"
        conn.close()


def test_viewer_cannot_delete() -> None:
    assert viewer_allowed("/api/media", "GET")
    assert viewer_allowed("/api/media/12/thumb", "GET")
    assert viewer_allowed("/api/status", "GET")
    assert viewer_allowed("/api/map", "GET")
    assert viewer_allowed("/api/albums", "GET")
    assert viewer_allowed("/api/cast/devices", "GET")
    assert viewer_allowed("/api/cast/play", "POST")
    assert not viewer_allowed("/api/media/delete", "POST")
    assert not viewer_allowed("/api/settings", "GET")
    assert not viewer_allowed("/api/scenes/scan", "POST")
    assert not viewer_allowed("/api/scenes/tag-many", "POST")
    assert not viewer_allowed("/api/scenes/untag-many", "POST")


def _solid(color: tuple[int, int, int], size=(160, 120)) -> Image.Image:
    return Image.new("RGB", size, color)


def test_heuristic_beach_and_forest() -> None:
    beach = Image.new("RGB", (160, 120), (210, 180, 120))
    px = beach.load()
    for y in range(40):
        for x in range(160):
            px[x, y] = (70, 140, 220)
    tags = dict(heuristic_tags(beach))
    assert "plage" in tags or "ciel" in tags or "campagne" in tags
    forest = Image.new("RGB", (160, 120), (30, 120, 40))
    tags_f = dict(heuristic_tags(forest))
    assert "foret" in tags_f or "campagne" in tags_f
    classified = classify_image(forest, cache=None)
    assert classified


def test_scene_filter_sql() -> None:
    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        conn.execute(
            """
            INSERT INTO media (relpath, size, mtime_ns, kind, year, present, thumb_ok)
            VALUES ('Annee 2020/a.jpg', 10, 1, 'photo', 2020, 1, 1)
            """
        )
        mid = int(conn.execute("SELECT id FROM media").fetchone()[0])
        conn.execute(
            "INSERT INTO media_scenes (media_id, tag, kind, score) VALUES (?,?,?,?)",
            (mid, "plage", "landscape", 0.7),
        )
        conn.commit()
        from_sql, clause, params = media_from_where(
            year=None,
            place=None,
            kind=None,
            person_id=None,
            q=None,
            scene="plage",
        )
        ids = [
            int(r[0])
            for r in conn.execute(
                f"SELECT m.id FROM {from_sql} WHERE {clause}", params
            )
        ]
        assert ids == [mid]
        from_sql, clause, params = media_from_where(
            year=None,
            place=None,
            kind=None,
            person_id=None,
            q=None,
            scene="eglise",
        )
        ids = [
            int(r[0])
            for r in conn.execute(
                f"SELECT m.id FROM {from_sql} WHERE {clause}", params
            )
        ]
        assert ids == []
        conn.close()


def test_manual_scene_tag_add_remove() -> None:
    from photo_library.scenes import add_scenes, remove_scenes, scenes_for_media

    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        conn.execute(
            """
            INSERT INTO media (relpath, size, mtime_ns, kind, year, present, thumb_ok)
            VALUES ('Annee 2025/Paris/a.jpg', 10, 1, 'photo', 2025, 1, 1)
            """
        )
        mid = int(conn.execute("SELECT id FROM media").fetchone()[0])
        conn.commit()
        out = add_scenes(conn, [mid], "eglise")
        assert out["updated"] == 1
        tags = [s["tag"] for s in scenes_for_media(conn, mid)]
        assert tags == ["eglise"]
        add_scenes(conn, [mid], "ville")
        tags = {s["tag"] for s in scenes_for_media(conn, mid)}
        assert tags == {"eglise", "ville"}
        remove_scenes(conn, [mid], "eglise")
        tags = [s["tag"] for s in scenes_for_media(conn, mid)]
        assert tags == ["ville"]
        try:
            add_scenes(conn, [mid], "inconnu")
            raise AssertionError("bad tag")
        except ValueError:
            pass
        conn.close()


def test_scenes_workspace_year_place() -> None:
    from photo_library.scenes import add_scenes, scenes_workspace, untagged_media

    with _tmp() as name:
        conn = connect(Path(name))
        init_schema(conn, refresh_places=False)
        conn.execute(
            """
            INSERT INTO media (relpath, size, mtime_ns, kind, year, place, present, thumb_ok)
            VALUES
              ('Annee 2025/Paris/eglise.jpg', 10, 1, 'photo', 2025, 'Paris', 1, 1),
              ('Annee 2025/Paris/rue.jpg', 10, 2, 'photo', 2025, 'Paris', 1, 1),
              ('Annee 2024/Paris/old.jpg', 10, 3, 'photo', 2024, 'Paris', 1, 1)
            """
        )
        conn.commit()
        eglise_id, rue_id, old_id = [
            int(r[0])
            for r in conn.execute(
                "SELECT id FROM media ORDER BY mtime_ns"
            ).fetchall()
        ]
        add_scenes(conn, [eglise_id], "eglise")
        add_scenes(conn, [old_id], "ville")
        ws = scenes_workspace(conn, year=2025, place="Paris", limit=80)
        assert ws["status"]["tagged"] == 1
        assert ws["status"]["untagged"] == 1
        assert ws["untagged"]["total"] == 1
        assert ws["untagged"]["items"][0]["id"] == rue_id
        assert [t["value"] for t in ws["tags"]] == ["eglise"]
        assert "Paris" in ws["places"]
        all_untagged = untagged_media(conn, year=None, place=None)
        assert all_untagged["total"] == 1
        ws24 = scenes_workspace(conn, year=2024, place="Paris")
        assert [t["value"] for t in ws24["tags"]] == ["ville"]
        conn.close()


def _asgi_call(app, method: str, path: str, *, body: bytes = b"", cookie: str | None = None, json_body: dict | None = None):
    import asyncio
    import json as jsonlib

    if json_body is not None:
        body = jsonlib.dumps(json_body).encode("utf-8")
        content_type = b"application/json"
    else:
        content_type = b"application/octet-stream"
    headers = [
        (b"host", b"test"),
        (b"content-type", content_type),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    headers_out = {
        k.decode("latin1").lower(): v.decode("latin1") for k, v in start["headers"]
    }
    return start["status"], payload, headers_out


def test_auth_off_allows_index() -> None:
    from photo_library.app import create_app

    with _tmp() as name:
        lib = Path(name) / "lib"
        cache = Path(name) / "cache"
        lib.mkdir()
        cache.mkdir()
        app = create_app(lib, cache)
        status, payload, _hdrs = _asgi_call(app, "GET", "/api/auth/status")
        assert status == 200
        assert b'"enabled":false' in payload.replace(b" ", b"")
        status, _payload, _hdrs = _asgi_call(
            app, "POST", "/api/index", json_body={"all": True, "limit": 1}
        )
        assert status == 200


def test_viewer_blocked_after_accounts() -> None:
    from photo_library.app import create_app

    with _tmp() as name:
        lib = Path(name) / "lib"
        cache = Path(name) / "cache"
        lib.mkdir()
        cache.mkdir()
        app = create_app(lib, cache)
        status, payload, _hdrs = _asgi_call(
            app,
            "POST",
            "/api/users",
            json_body={"username": "papa", "password": "secret12", "role": "viewer"},
        )
        assert status == 400
        assert b"email_required" in payload
        status, payload, hdrs = _asgi_call(
            app,
            "POST",
            "/api/users",
            json_body={
                "username": "papa",
                "password": "secret12",
                "role": "viewer",
                "email": "papa@example.com",
            },
        )
        assert status == 200
        assert b'"role":"admin"' in payload.replace(b" ", b"")
        cookie = hdrs.get("set-cookie", "")
        status, _p, hdrs2 = _asgi_call(
            app,
            "POST",
            "/api/users",
            json_body={
                "username": "leo",
                "password": "secret12",
                "role": "viewer",
                "email": "leo@example.com",
            },
            cookie=cookie.split(";", 1)[0] if cookie else None,
        )
        assert status == 200
        status, _p, _h = _asgi_call(app, "GET", "/api/settings")
        assert status == 401
        status, payload, hdrs = _asgi_call(
            app,
            "POST",
            "/api/auth/login",
            json_body={"username": "leo", "password": "secret12"},
        )
        assert status == 200
        cookie = hdrs.get("set-cookie", "").split(";", 1)[0]
        status, _p, _h = _asgi_call(app, "GET", "/api/media", cookie=cookie)
        assert status == 200
        status, _p, _h = _asgi_call(app, "GET", "/api/settings", cookie=cookie)
        assert status == 403
        status, _p, _h = _asgi_call(
            app, "POST", "/api/index", json_body={"all": True}, cookie=cookie
        )
        assert status == 403


def test_health_hides_library_until_status() -> None:
    import json as jsonlib

    from photo_library.app import create_app

    with _tmp() as name:
        lib = Path(name) / "lib"
        cache = Path(name) / "cache"
        lib.mkdir()
        cache.mkdir()
        app = create_app(lib, cache)
        status, payload, hdrs = _asgi_call(
            app,
            "POST",
            "/api/users",
            json_body={
                "username": "papa",
                "password": "secret12",
                "role": "admin",
                "email": "papa@example.com",
            },
        )
        assert status == 200
        cookie = hdrs.get("set-cookie", "").split(";", 1)[0]
        status, payload, _h = _asgi_call(app, "GET", "/api/health")
        assert status == 200
        data = jsonlib.loads(payload)
        assert data.get("ok") is True
        from photo_library.version import APP_VERSION

        assert data.get("version") == APP_VERSION
        assert "library" not in data
        assert "cache" not in data
        assert "job" not in data
        assert data["auth"]["enabled"] is True
        status, payload, _h = _asgi_call(app, "GET", "/api/status")
        assert status == 401
        status, payload, _h = _asgi_call(app, "GET", "/api/status", cookie=cookie)
        assert status == 200
        data = jsonlib.loads(payload)
        assert "library" in data
        assert str(lib) in data["library"]


def test_loopback_index_without_cookie() -> None:
    from photo_library.app import create_app

    with _tmp() as name:
        lib = Path(name) / "lib"
        cache = Path(name) / "cache"
        lib.mkdir()
        cache.mkdir()
        app = create_app(lib, cache)
        _asgi_call(
            app,
            "POST",
            "/api/users",
            json_body={
                "username": "papa",
                "password": "secret12",
                "role": "admin",
                "email": "papa@example.com",
            },
        )
        status, _p, _h = _asgi_call(
            app, "POST", "/api/index", json_body={"all": True, "limit": 1}
        )
        assert status == 200


def test_tls_local_cert() -> None:
        from cryptography import x509
        from photo_library.tls import MDNS_HOST, ensure_tls, fingerprint_sha256, ssl_context

        with _tmp() as name:
            cache = Path(name)
            paths = ensure_tls(cache, extra_hosts=["192.0.2.8"])
            assert paths.cert.is_file()
            assert paths.key.is_file()
            assert paths.ca_cert.is_file()
            assert ":" in fingerprint_sha256(paths.cert)
            cert = x509.load_pem_x509_certificate(paths.cert.read_bytes())
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            dns = {str(n.value).lower() for n in san.value if isinstance(n, x509.DNSName)}
            assert MDNS_HOST in dns
            ctx = ssl_context(cache)
            assert ctx is not None
            again = ensure_tls(cache, extra_hosts=["192.0.2.8"])
            assert again.cert.read_bytes() == paths.cert.read_bytes()
            from photo_library.tls import client_context, letsencrypt_pair

            assert letsencrypt_pair(cache) is None
            public = cache / "letsencrypt"
            public.mkdir()
            (public / "fullchain.pem").write_bytes(paths.cert.read_bytes())
            (public / "privkey.pem").write_bytes(paths.key.read_bytes())
            base, public_ctx = client_context(cache, port=8765)
            assert base == "https://galerie.local:8765"
            assert public_ctx is not None


def test_users_cli_list_create_delete() -> None:
    import io
    from contextlib import redirect_stdout

    from photo_library.cli import main

    with _tmp() as name:
        cache = Path(name) / "cache"
        lib = Path(name) / "lib"
        lib.mkdir()
        cache.mkdir()
        common = ["--cache", str(cache), "-d", str(lib), "users"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert main(common + ["--list"]) == 0
        assert "Aucun compte" in buf.getvalue()
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert (
                main(
                    common
                    + [
                        "--create",
                        "papa",
                        "--role",
                        "admin",
                        "--password",
                        "secret12",
                    ]
                )
                == 0
            )
            assert (
                main(
                    common
                    + [
                        "--create",
                        "leo",
                        "--role",
                        "lecture",
                        "--password",
                        "secret12",
                    ]
                )
                == 0
            )
        assert "papa" in buf.getvalue() and "leo" in buf.getvalue()
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert (
                main(
                    common
                    + [
                        "--set-password",
                        "leo",
                        "--password",
                        "nouveaupass",
                    ]
                )
                == 0
            )
        assert "Mot de passe mis à jour" in buf.getvalue()
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert main(common + ["-l"]) == 0
        listed = buf.getvalue()
        assert "papa" in listed and "admin" in listed
        assert "leo" in listed and "lecture" in listed
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert main(common + ["--delete", "leo", "--yes"]) == 0
            assert main(common + ["--delete", "papa", "--yes"]) == 0
        assert "Plus aucun compte" in buf.getvalue()
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert main(common) == 0
        assert "Aucun compte" in buf.getvalue()


if __name__ == "__main__":
    test_password_roundtrip()
    test_no_users_means_open_site()
    test_first_user_is_admin()
    test_viewer_cannot_delete()
    test_heuristic_beach_and_forest()
    test_scene_filter_sql()
    test_manual_scene_tag_add_remove()
    test_scenes_workspace_year_place()
    test_auth_off_allows_index()
    test_viewer_blocked_after_accounts()
    test_health_hides_library_until_status()
    test_loopback_index_without_cookie()
    test_tls_local_cert()
    test_users_cli_list_create_delete()
    test_password_reset_and_session()
    test_password_too_short()
    test_login_lockout_three_tries()
    print("ok")
