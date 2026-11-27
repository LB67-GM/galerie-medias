"""Comptes locaux. Sans aucun utilisateur, le site reste ouvert."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

COOKIE = "galerie_session"
MAX_AGE_S = 14 * 24 * 3600
PBKDF2_ROUNDS = 80_000
MIN_PASSWORD_LEN = 8
MAX_LOGIN_ATTEMPTS = 3
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESET_TTL = timedelta(hours=1)
ROLES = frozenset({"admin", "viewer"})
ROLE_ALIASES = {
    "admin": "admin",
    "viewer": "viewer",
    "lecture": "viewer",
}

VIEWER_GET_EXACT = frozenset(
    {
        "/",
        "/favicon.ico",
        "/manifest.json",
        "/sw.js",
        "/api/health",
        "/api/status",
        "/galerie-ca.pem",
        "/api/auth/me",
        "/api/auth/status",
        "/api/filters",
        "/api/library/years",
        "/api/people",
        "/api/albums",
        "/api/map",
        "/api/media",
        "/api/media/ids",
        "/api/cast/devices",
        "/api/cinema/status",
        "/api/cinema/filters",
        "/api/cinema/items",
        "/api/cinema/continue",
        "/api/cinema/disc",
    }
)
VIEWER_GET_RE = re.compile(
    r"^/api/media/\d+$"
    r"|^/api/media/\d+/(?:thumb|preview|file|play)$"
    r"|^/api/cast/file/"
    r"|^/api/cinema/items/\d+(?:/(?:info|poster|subtitles/\d+\.vtt))?$"
    r"|^/api/cinema/stream/[0-9a-f]+/(?:index\.m3u8|seg_\d+\.ts)$"
    r"|^/static/"
)
VIEWER_POST_RE = re.compile(r"^/api/cinema/stream/[0-9a-f]+/stop$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def session_secret(cache: Path) -> bytes:
    path = cache / "session.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(os.urandom(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_bytes()


def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, PBKDF2_ROUNDS
    )
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        kind, rounds_s, salt_hex, digest_hex = stored.split("$", 3)
    except ValueError:
        return False
    if kind != "pbkdf2":
        return False
    try:
        rounds = int(rounds_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    got = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(got, expected)


def user_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    return int(row[0] if row else 0)


def auth_enabled(conn: sqlite3.Connection) -> bool:
    return user_count(conn) > 0


def public_user(row: sqlite3.Row | dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    return {
        "id": int(data["id"]),
        "username": str(data["username"]),
        "role": str(data["role"]),
    }


class AuthError(ValueError):
    def __init__(self, code: str, message: str, n: int | None = None):
        super().__init__(message)
        self.code = code
        self.n = n


class AccountLocked(PermissionError):
    code = "locked"

    def __init__(self) -> None:
        super().__init__(lock_message())


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, username, role, created_at, "
        "COALESCE(email, '') AS email, "
        "COALESCE(failed_attempts, 0) AS failed_attempts, "
        "COALESCE(locked, 0) AS locked "
        "FROM users ORDER BY username COLLATE NOCASE"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["locked"] = bool(int(item.get("locked") or 0))
        item["failed_attempts"] = int(item.get("failed_attempts") or 0)
        out.append(item)
    return out


def get_user_by_name(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE username=? COLLATE NOCASE", (username.strip(),)
    ).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def parse_role(role: str) -> str:
    key = (role or "").strip().lower()
    mapped = ROLE_ALIASES.get(key)
    if mapped is None:
        raise ValueError("Rôle inconnu (admin ou lecture).")
    return mapped


def display_role(role: str) -> str:
    return "lecture" if (role or "").strip().lower() == "viewer" else "admin"


def _admin_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='admin'"
    ).fetchone()
    return int(row[0] if row else 0)


def normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not email:
        return ""
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise AuthError("email_invalid", "Courriel invalide.")
    return email


def _email_taken(
    conn: sqlite3.Connection, email: str, except_id: int | None = None
) -> bool:
    if not email:
        return False
    row = conn.execute(
        "SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)
    ).fetchone()
    if row is None:
        return False
    if except_id is not None and int(row["id"]) == int(except_id):
        return False
    return True


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    role: str,
    email: str = "",
) -> dict[str, Any]:
    name = (username or "").strip()
    if not USERNAME_RE.match(name):
        raise AuthError(
            "username_invalid",
            "Identifiant : 2 à 32 caractères (lettres, chiffres, point, _ ou -).",
        )
    if len(password or "") < MIN_PASSWORD_LEN:
        raise AuthError(
            "password_short",
            f"Mot de passe : {MIN_PASSWORD_LEN} caractères minimum.",
        )
    role = parse_role(role)
    first = user_count(conn) == 0
    if first:
        role = "admin"
    if get_user_by_name(conn, name):
        raise AuthError("username_taken", "Cet identifiant existe déjà.")
    mail = normalize_email(email)
    if _email_taken(conn, mail):
        raise AuthError("email_taken", "Ce courriel est déjà utilisé.")
    now = _now().replace(microsecond=0).isoformat()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at, email) "
        "VALUES (?,?,?,?,?)",
        (name, hash_password(password), role, now, mail),
    )
    conn.commit()
    return {
        "id": int(cur.lastrowid),
        "username": name,
        "role": role,
        "email": mail,
        "created_at": now,
        "first": first,
        "session_epoch": 0,
    }


def delete_user(
    conn: sqlite3.Connection, user_id: int, *, allow_last_admin: bool = False
) -> dict[str, Any]:
    row = get_user(conn, user_id)
    if row is None:
        raise ValueError("Compte introuvable.")
    if (
        row["role"] == "admin"
        and _admin_count(conn) <= 1
        and not allow_last_admin
    ):
        raise ValueError("Impossible de supprimer le dernier compte admin.")
    conn.execute("DELETE FROM password_resets WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    return {
        "deleted": user_id,
        "username": str(row["username"]),
        "role": str(row["role"]),
    }


def delete_user_by_name(
    conn: sqlite3.Connection, username: str, *, allow_last_admin: bool = False
) -> dict[str, Any]:
    row = get_user_by_name(conn, username)
    if row is None:
        raise ValueError("Compte introuvable.")
    return delete_user(
        conn, int(row["id"]), allow_last_admin=allow_last_admin
    )


def _int_col(row: sqlite3.Row, name: str, default: int = 0) -> int:
    try:
        value = row[name]
    except (IndexError, KeyError):
        return default
    if value is None:
        return default
    return int(value)


def account_locked(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    return _int_col(row, "locked") != 0


def lock_message() -> str:
    return (
        "Compte verrouillé après 3 essais. Utilisez « Mot de passe oublié » "
        "ou demandez à un administrateur de le réinitialiser."
    )


def login_user(conn: sqlite3.Connection, username: str, password: str) -> dict[str, Any]:
    row = get_user_by_name(conn, username)
    if row is None:
        raise AuthError("bad_login", "Identifiant ou mot de passe incorrect.")
    if account_locked(row):
        raise AccountLocked()
    if not verify_password(password, row["password_hash"]):
        failed = _int_col(row, "failed_attempts") + 1
        locked = 1 if failed >= MAX_LOGIN_ATTEMPTS else 0
        conn.execute(
            "UPDATE users SET failed_attempts=?, locked=? WHERE id=?",
            (failed, locked, int(row["id"])),
        )
        conn.commit()
        if locked:
            raise AccountLocked()
        left = MAX_LOGIN_ATTEMPTS - failed
        if left == 1:
            message = (
                "Oups, ce n’est pas le bon mot de passe. Encore 1 essai, "
                "puis le compte est verrouillé."
            )
        else:
            message = (
                f"Oups, ce n’est pas le bon mot de passe. Encore {left} essais."
            )
        raise AuthError("bad_password", message, n=left)
    conn.execute(
        "UPDATE users SET failed_attempts=0, locked=0 WHERE id=?",
        (int(row["id"]),),
    )
    conn.commit()
    user = public_user(row)
    assert user is not None
    user["session_epoch"] = _int_col(row, "session_epoch")
    return user


def unlock_user(conn: sqlite3.Connection, username: str) -> dict[str, Any]:
    row = get_user_by_name(conn, username)
    if row is None:
        raise ValueError("Compte introuvable.")
    conn.execute(
        "UPDATE users SET failed_attempts=0, locked=0 WHERE id=?",
        (int(row["id"]),),
    )
    conn.commit()
    return {
        "username": str(row["username"]),
        "role": str(row["role"]),
        "unlocked": True,
    }


def unlock_all_users(conn: sqlite3.Connection) -> int:
    cur = conn.execute("UPDATE users SET failed_attempts=0, locked=0")
    conn.commit()
    return int(cur.rowcount or 0)


def set_user_password(
    conn: sqlite3.Connection, username: str, password: str
) -> dict[str, Any]:
    if len(password or "") < MIN_PASSWORD_LEN:
        raise AuthError(
            "password_short",
            f"Mot de passe : {MIN_PASSWORD_LEN} caractères minimum.",
        )
    row = get_user_by_name(conn, username)
    if row is None:
        raise ValueError("Compte introuvable.")
    conn.execute(
        "UPDATE users SET password_hash=?, failed_attempts=0, locked=0, "
        "session_epoch=COALESCE(session_epoch, 0) + 1 WHERE id=?",
        (hash_password(password), int(row["id"])),
    )
    conn.commit()
    return {
        "username": str(row["username"]),
        "role": str(row["role"]),
        "password_updated": True,
        "unlocked": True,
    }


def set_user_email(conn: sqlite3.Connection, username: str, email: str) -> dict[str, Any]:
    row = get_user_by_name(conn, username)
    if row is None:
        raise ValueError("Compte introuvable.")
    mail = normalize_email(email)
    if _email_taken(conn, mail, except_id=int(row["id"])):
        raise AuthError("email_taken", "Ce courriel est déjà utilisé.")
    conn.execute("UPDATE users SET email=? WHERE id=?", (mail, int(row["id"])))
    conn.commit()
    return {"username": str(row["username"]), "email": mail, "id": int(row["id"])}


def set_user_email_by_id(
    conn: sqlite3.Connection, user_id: int, email: str
) -> dict[str, Any]:
    row = get_user(conn, user_id)
    if row is None:
        raise ValueError("Compte introuvable.")
    return set_user_email(conn, str(row["username"]), email)


def issue_reset_token(conn: sqlite3.Connection, email: str) -> str | None:
    """Jeton brut, chaîne vide si un lien vient d’être émis, None si inconnu."""
    try:
        mail = normalize_email(email)
    except AuthError:
        return None
    if not mail:
        return None
    row = conn.execute(
        "SELECT id FROM users WHERE email = ? COLLATE NOCASE", (mail,)
    ).fetchone()
    if row is None:
        return None
    user_id = int(row["id"])
    fresh_after = (_now() + RESET_TTL - timedelta(seconds=60)).isoformat()
    recent = conn.execute(
        "SELECT 1 FROM password_resets WHERE user_id=? AND used=0 AND expires_at > ?",
        (user_id, fresh_after),
    ).fetchone()
    if recent:
        return ""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires = (_now() + RESET_TTL).replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM password_resets WHERE user_id=?", (user_id,))
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at, used) "
        "VALUES (?,?,?,0)",
        (user_id, digest, expires),
    )
    conn.commit()
    return token


def complete_password_reset(
    conn: sqlite3.Connection, token: str, password: str
) -> dict[str, Any]:
    if len(password or "") < MIN_PASSWORD_LEN:
        raise AuthError(
            "password_short",
            f"Mot de passe : {MIN_PASSWORD_LEN} caractères minimum.",
        )
    raw = (token or "").strip()
    if not raw:
        raise AuthError("reset_bad", "Ce lien a expiré ou a déjà été utilisé.")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = conn.execute(
        "SELECT id, user_id, expires_at, used FROM password_resets WHERE token_hash=?",
        (digest,),
    ).fetchone()
    if row is None or int(row["used"] or 0):
        raise AuthError("reset_bad", "Ce lien a expiré ou a déjà été utilisé.")
    try:
        expires = datetime.fromisoformat(str(row["expires_at"]))
    except ValueError:
        expires = _now() - timedelta(seconds=1)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _now():
        raise AuthError("reset_bad", "Ce lien a expiré ou a déjà été utilisé.")
    user = get_user(conn, int(row["user_id"]))
    if user is None:
        raise AuthError("reset_bad", "Ce lien a expiré ou a déjà été utilisé.")
    conn.execute(
        "UPDATE users SET password_hash=?, failed_attempts=0, locked=0, "
        "session_epoch=COALESCE(session_epoch, 0) + 1 WHERE id=?",
        (hash_password(password), int(user["id"])),
    )
    conn.execute(
        "UPDATE password_resets SET used=1 WHERE user_id=?", (int(user["id"]),)
    )
    conn.commit()
    return {"username": str(user["username"]), "reset": True}


def encode_session(user: dict[str, Any], secret: bytes) -> str:
    exp = int((_now() + timedelta(seconds=MAX_AGE_S)).timestamp())
    epoch = int(user.get("session_epoch") or 0)
    payload = f"{int(user['id'])}:{user['role']}:{exp}:{epoch}"
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def decode_session(
    token: str | None, conn: sqlite3.Connection, secret: bytes
) -> dict[str, Any] | None:
    if not token:
        return None
    parts = token.split(":")
    if len(parts) == 4:
        uid_s, role, exp_s, sig = parts
        epoch_s = "0"
        payload = f"{uid_s}:{role}:{exp_s}"
    elif len(parts) == 5:
        uid_s, role, exp_s, epoch_s, sig = parts
        payload = f"{uid_s}:{role}:{exp_s}:{epoch_s}"
    else:
        return None
    expect = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        exp = int(exp_s)
        uid = int(uid_s)
        epoch = int(epoch_s)
    except ValueError:
        return None
    if exp < int(_now().timestamp()):
        return None
    row = get_user(conn, uid)
    if row is None or _int_col(row, "session_epoch") != epoch:
        return None
    return public_user(row)


def set_session_cookie(
    response: Response,
    user: dict[str, Any],
    secret: bytes,
    *,
    secure: bool = False,
) -> None:
    response.set_cookie(
        COOKIE,
        encode_session(user, secret),
        max_age=MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def is_public_path(path: str, method: str) -> bool:
    if path.startswith("/static/"):
        return True
    if path in {
        "/",
        "/favicon.ico",
        "/manifest.json",
        "/sw.js",
        "/api/health",
        "/galerie-ca.pem",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/forgot",
        "/api/auth/reset",
    }:
        return True
    if path == "/api/auth/logout" and method in {"POST", "GET"}:
        return True
    if method in {"GET", "HEAD"} and path.startswith("/api/cast/file/"):
        return True
    return False


LOOPBACK_ADMIN = frozenset(
    {
        ("GET", "/api/job"),
        ("GET", "/api/backups"),
        ("POST", "/api/index"),
        ("POST", "/api/backup"),
        ("POST", "/api/trash/expire"),
    }
)


def is_loopback_client(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    host = (client.host or "").split("%", 1)[0]
    return host in {"127.0.0.1", "::1", "localhost"}


def loopback_admin_allowed(request: Request) -> bool:
    if not is_loopback_client(request):
        return False
    return (request.method, request.url.path) in LOOPBACK_ADMIN


def viewer_allowed(path: str, method: str) -> bool:
    if method in {"HEAD", "OPTIONS"}:
        return True
    if method == "POST" and path == "/api/auth/logout":
        return True
    if method == "POST" and path in {
        "/api/cast/play",
        "/api/cast/cinema",
        "/api/cast/stop",
        "/api/cinema/stream/start",
        "/api/cinema/progress",
        "/api/cinema/progress/clear",
    }:
        return True
    if method == "POST" and VIEWER_POST_RE.match(path):
        return True
    if method != "GET":
        return False
    if path in VIEWER_GET_EXACT:
        return True
    return bool(VIEWER_GET_RE.match(path))


def deny(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def current_user_from_request(
    request: Request, conn: sqlite3.Connection, secret: bytes
) -> dict[str, Any] | None:
    return decode_session(request.cookies.get(COOKIE), conn, secret)
