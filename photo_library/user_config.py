from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

APP_NAME = "GaleriePhotos"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".config" / "galerie-photos"


def config_path() -> Path:
    return data_dir() / "config.json"


def key_path() -> Path:
    return data_dir() / "secret.key"


def portable_cache_dir() -> Path:
    return data_dir() / "cache"


def _restrict(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _fernet() -> Fernet:
    path = key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(Fernet.generate_key())
        _restrict(path)
    return Fernet(path.read_bytes())


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def empty_settings() -> dict:
    return {
        "phone_kind": "iphone",
        "triage_dir": "",
        "apple_id": "",
        "apple_password": "",
        "google_dir": "",
        "facebook_dir": "",
        "library_src": "",
        "library_dest": "",
        "backup_dir": "",
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
        "smtp_from": "",
        "smtp_tls": "1",
        "public_url": "",
        "cinema_dir": "",
        "optical_device": "",
    }


def _is_mount_root(parent: Path) -> bool:
    parts = parent.parts
    if sys.platform != "win32" and len(parts) >= 2 and parts[0] == "/":
        if parts[1] in {"mnt", "media", "Volumes"} and len(parts) <= 2:
            return True
        if parts[1] == "run" and len(parts) >= 3 and parts[2] == "media" and len(parts) <= 4:
            return True
    return False


def cinema_dir_status(raw: str | None = None, *, create_local: bool = False) -> dict:
    """Diagnostique l’accès au dossier Cinéma sans jamais lever d’exception."""
    if raw is None:
        raw = str(load_settings().get("cinema_dir") or "")
    text = str(raw or "").strip()
    if not text:
        return {
            "configured": False,
            "status": "unconfigured",
            "path": "",
            "writable": False,
        }
    path = Path(text).expanduser()
    try:
        if path.is_dir():
            readable = os.access(path, os.R_OK)
            return {
                "configured": True,
                "status": "ready" if readable else "unreadable",
                "path": str(path),
                "writable": os.access(path, os.W_OK),
            }
        if create_local and not _is_mount_root(path.parent):
            parent = path.parent
            if parent.is_dir() and os.access(parent, os.W_OK):
                path.mkdir(parents=True, exist_ok=True)
                return {
                    "configured": True,
                    "status": "ready",
                    "path": str(path),
                    "writable": os.access(path, os.W_OK),
                }
        status = "missing_mount" if _is_mount_root(path.parent) else "missing"
        return {
            "configured": True,
            "status": status,
            "path": str(path),
            "writable": False,
        }
    except OSError:
        return {
            "configured": True,
            "status": "unreadable",
            "path": str(path),
            "writable": False,
        }


def load_settings() -> dict:
    path = config_path()
    data = empty_settings()
    if not path.is_file():
        return data
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in data:
        if key in {"apple_password", "smtp_password"}:
            continue
        if isinstance(raw.get(key), str):
            data[key] = raw[key]
    if data["phone_kind"] not in {"iphone", "android", "facebook"}:
        data["phone_kind"] = "iphone"
    data["smtp_port"] = _smtp_port(data.get("smtp_port"))
    data["smtp_tls"] = "0" if str(data.get("smtp_tls") or "1") == "0" else "1"
    data["public_url"] = str(data.get("public_url") or "").strip().rstrip("/")
    token = raw.get("apple_password_enc")
    if isinstance(token, str) and token:
        data["apple_password"] = decrypt_secret(token)
    smtp_token = raw.get("smtp_password_enc")
    if isinstance(smtp_token, str) and smtp_token:
        data["smtp_password"] = decrypt_secret(smtp_token)
    return data


def _smtp_port(value: object) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:5]
    if not digits:
        return "587"
    port = int(digits)
    if port < 1 or port > 65535:
        return "587"
    return str(port)


def _kept_secret(name: str, update: dict, current: dict) -> str:
    value = update.get(name)
    if isinstance(value, str) and value:
        if name == "smtp_password":
            return "".join(value.split())
        return value
    return str(current.get(name) or "")


def save_settings(update: dict, *, keep_password: bool = False) -> dict:
    current = load_settings()
    next_data = empty_settings()
    for key in (
        "phone_kind",
        "triage_dir",
        "apple_id",
        "google_dir",
        "facebook_dir",
        "library_src",
        "library_dest",
        "backup_dir",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_from",
        "smtp_tls",
        "public_url",
        "cinema_dir",
        "optical_device",
    ):
        value = update.get(key, current.get(key, ""))
        next_data[key] = str(value or "").strip()
    if next_data["phone_kind"] not in {"iphone", "android", "facebook"}:
        next_data["phone_kind"] = "iphone"
    next_data["smtp_port"] = _smtp_port(next_data.get("smtp_port"))
    next_data["smtp_tls"] = "0" if next_data.get("smtp_tls") == "0" else "1"
    next_data["public_url"] = next_data["public_url"].rstrip("/")
    password = str(update.get("apple_password") or "")
    if password:
        next_data["apple_password"] = password
    elif keep_password:
        next_data["apple_password"] = current.get("apple_password") or ""
    next_data["smtp_password"] = _kept_secret("smtp_password", update, current)
    payload = {
        "phone_kind": next_data["phone_kind"],
        "triage_dir": next_data["triage_dir"],
        "apple_id": next_data["apple_id"],
        "google_dir": next_data["google_dir"],
        "facebook_dir": next_data["facebook_dir"],
        "library_src": next_data["library_src"],
        "library_dest": next_data["library_dest"],
        "backup_dir": next_data["backup_dir"],
        "smtp_host": next_data["smtp_host"],
        "smtp_port": next_data["smtp_port"],
        "smtp_user": next_data["smtp_user"],
        "smtp_from": next_data["smtp_from"],
        "smtp_tls": next_data["smtp_tls"],
        "public_url": next_data["public_url"],
        "cinema_dir": next_data["cinema_dir"],
        "optical_device": next_data["optical_device"],
    }
    if next_data["apple_password"]:
        payload["apple_password_enc"] = encrypt_secret(next_data["apple_password"])
    if next_data["smtp_password"]:
        payload["smtp_password_enc"] = encrypt_secret(next_data["smtp_password"])
    dest = config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _restrict(dest)
    return next_data


def public_settings(library: Path | None = None) -> dict:
    data = load_settings()
    src = data["library_src"] or (str(library) if library else "")
    dest = data["library_dest"] or src
    backup = data["backup_dir"] or dest or src
    return {
        "phone_kind": data["phone_kind"] or "iphone",
        "triage_dir": data["triage_dir"],
        "apple_id": data["apple_id"],
        "password_set": bool(data["apple_password"]),
        "google_dir": data["google_dir"],
        "facebook_dir": data["facebook_dir"],
        "library_src": src,
        "library_dest": dest,
        "backup_dir": backup,
        "smtp_host": data["smtp_host"],
        "smtp_port": data["smtp_port"] or "587",
        "smtp_user": data["smtp_user"],
        "smtp_from": data["smtp_from"],
        "smtp_tls": data["smtp_tls"] if data["smtp_tls"] == "0" else "1",
        "smtp_password_set": bool(data["smtp_password"]),
        "public_url": data["public_url"],
        "cinema_dir": data["cinema_dir"],
        "optical_device": data["optical_device"],
        "cinema_status": cinema_dir_status(data["cinema_dir"]),
        "config_file": str(config_path()),
    }


def library_from_settings(fallback: Path) -> Path:
    data = load_settings()
    for key in ("library_dest", "library_src"):
        raw = data.get(key) or ""
        if raw:
            return Path(raw).expanduser()
    return fallback
