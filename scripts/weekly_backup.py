#!/usr/bin/env python3
"""Sauvegarde hebdomadaire (base + réglages) via l’API locale. Destination : Réglages."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from photo_library.tls import client_context  # noqa: E402
POLL_SEC = 5
CACHE = Path.home() / ".cache/photo-library"
RESULT_PATH = CACHE / "last-backup.json"


def write_result(ok: bool, **extra) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": ok,
        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        **extra,
    }
    tmp = RESULT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(RESULT_PATH)
    title = "Sauvegarde galerie terminée" if ok else "Sauvegarde galerie en erreur"
    folder = extra.get("folder") or extra.get("backup_dir") or ""
    body = folder if ok else str(extra.get("error") or "échec")
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


def dest_writable(path: str) -> bool:
    parent = Path(path)
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".galerie-backup-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
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
    info = api("/api/backups")
    dest = info.get("backup_dir") or ""
    if not dest:
        fail("Aucun dossier de sauvegarde (Réglages → Sauvegarde).")
    if not dest_writable(dest):
        fail(f"Dossier de sauvegarde illisible ou non inscriptible : {dest}")
    started = api("/api/backup", {})
    print(
        f"Sauvegarde demandée ({started.get('status')}, {started.get('message') or started.get('kind')})",
        flush=True,
    )
    while True:
        snap = api("/api/job").get("job") or {}
        st = snap.get("status")
        msg = snap.get("message") or ""
        kind = snap.get("kind") or ""
        print(f"{kind} {st or '?'} {snap.get('done')}/{snap.get('total')} {msg}", flush=True)
        if kind == "backup" and st == "error":
            fail(snap.get("error") or msg or "sauvegarde en erreur")
        if kind == "backup" and st == "done":
            result = snap.get("result") or {}
            write_result(
                True,
                result=result,
                message=msg,
                folder=result.get("folder"),
                backup_dir=dest,
                media_count=result.get("media_count"),
                pruned=result.get("pruned"),
            )
            print(f"Terminé : {result or msg}", flush=True)
            return 0
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
