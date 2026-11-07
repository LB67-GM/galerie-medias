#!/usr/bin/env python3
"""Index hebdomadaire de Galerie Médias via l’API locale. Échoue si la bibliothèque ou le serveur manque."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.config import DEFAULT_LIBRARY  # noqa: E402
from photo_library.tls import client_context  # noqa: E402
from photo_library.user_config import library_from_settings  # noqa: E402
POLL_SEC = 20
CACHE = Path.home() / ".cache/photo-library"
RESULT_PATH = CACHE / "last-index.json"


def media_counts() -> dict:
    db = CACHE / "library.sqlite"
    if not db.is_file():
        return {}
    conn = sqlite3.connect(str(db))
    try:
        present = conn.execute(
            "SELECT COUNT(*) FROM media WHERE present=1"
        ).fetchone()[0]
        by_kind = dict(
            conn.execute(
                "SELECT kind, COUNT(*) FROM media WHERE present=1 GROUP BY kind"
            )
        )
        row = conn.execute(
            "SELECT MIN(year), MAX(year), COUNT(DISTINCT year) FROM media "
            "WHERE present=1 AND year IS NOT NULL"
        ).fetchone()
        return {
            "present": present,
            "photo": int(by_kind.get("photo") or 0),
            "video": int(by_kind.get("video") or 0),
            "year_min": row[0],
            "year_max": row[1],
            "year_count": row[2],
        }
    finally:
        conn.close()


def write_result(ok: bool, **extra) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": ok,
        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        **media_counts(),
        **extra,
    }
    tmp = RESULT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(RESULT_PATH)
    summary = (
        f"{payload.get('present', '?')} médias"
        f" ({payload.get('photo', '?')} photos, {payload.get('video', '?')} vidéos)"
    )
    if payload.get("year_min"):
        summary += f" · {payload['year_min']}–{payload['year_max']}"
    title = "Index Galerie Médias terminé" if ok else "Index Galerie Médias en erreur"
    body = summary if ok else str(extra.get("error") or summary)
    try:
        subprocess.run(
            ["notify-send", "-a", "Galerie Médias", title, body],
            check=False,
            timeout=5,
        )
    except Exception:
        pass


def fail(msg: str, code: int = 1) -> None:
    write_result(False, error=msg)
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def nas_ok() -> bool:
    library = library_from_settings(DEFAULT_LIBRARY)
    if not library.is_dir():
        return False
    try:
        for child in library.iterdir():
            name = child.name.lower()
            if child.is_dir() and name.startswith("annee"):
                return True
    except OSError:
        return False
    return False


def api(path: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode()
    base, ctx = client_context(CACHE)
    req = urllib.request.Request(
        base + path,
        data=body,
        method="GET" if data is None else "POST",
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read()
    except FileNotFoundError as exc:
        fail(f"Certificat maison absent ({exc}). Démarrez le site une fois.")
    except urllib.error.URLError as exc:
        fail(f"Galerie injoignable ({base}) : {exc}")
    if not raw:
        return {}
    return json.loads(raw.decode())


def main() -> int:
    if not nas_ok():
        fail(f"Bibliothèque absente ou illisible ({library_from_settings(DEFAULT_LIBRARY)}).")
    started = api("/api/index", {"all": True})
    print(
        f"Index demandé ({started.get('status')}, {started.get('message') or started.get('kind')})",
        flush=True,
    )
    while True:
        snap = api("/api/job").get("job") or {}
        st = snap.get("status")
        queued = snap.get("queued") or []
        msg = snap.get("message") or ""
        print(f"{st or '?'} {snap.get('done')}/{snap.get('total')} {msg}", flush=True)
        if st == "error":
            fail(snap.get("error") or msg or "index en erreur")
        if st == "running" or queued:
            time.sleep(POLL_SEC)
            continue
        if st == "done":
            write_result(True, result=snap.get("result"), message=msg)
            print(f"Terminé : {snap.get('result') or msg}", flush=True)
            return 0
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
