from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path

from photo_library.config import MEDIA_SUFFIXES
from photo_library.jobs import emit
from photo_library.user_config import load_settings
from photo_library.venv_bins import venv_executable

Progress = Callable[[int, int | None, str], None]
Patch = Callable[..., None]

_MFA_MARKERS = (
    "two-factor",
    "two factor",
    "2fa",
    "authentication code",
    "enter the code",
    "enter one of the received",
    "approved devices",
    "trusted device",
    "code you received",
)

_lock = threading.Lock()
_proc: subprocess.Popen[str] | None = None


def _period(year: int, month: int | None) -> tuple[date, date, str]:
    if year < 2000 or year > date.today().year + 1:
        raise ValueError(f"Année invalide : {year}")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Le mois doit être entre 1 et 12")
    start = date(year, month or 1, 1)
    if month is None:
        end = date(year + 1, 1, 1)
        label = str(year)
    elif month == 12:
        end = date(year + 1, 1, 1)
        label = f"{month:02d}/{year}"
    else:
        end = date(year, month + 1, 1)
        label = f"{month:02d}/{year}"
    return start, end, label


def _count_media(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES)


def _looks_like_mfa(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in _MFA_MARKERS)


def submit_mfa(code: str) -> None:
    text = "".join(c for c in code if c.isdigit())
    if len(text) < 4:
        raise ValueError("Code 2FA trop court")
    with _lock:
        proc = _proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            raise ValueError("Aucun téléchargement n’attend un code 2FA")
        proc.stdin.write(text + "\n")
        proc.stdin.flush()


def run_download(
    year: int,
    month: int | None,
    progress: Progress,
    patch: Patch | None = None,
) -> dict:
    global _proc
    cfg = load_settings()
    dest = (cfg.get("triage_dir") or "").strip()
    user = (cfg.get("apple_id") or "").strip()
    password = cfg.get("apple_password") or ""
    if not dest:
        raise ValueError("Indiquez le dossier de triage dans Réglages → iCloud")
    if not user:
        raise ValueError("Indiquez l’Apple ID dans Réglages → iCloud")
    if not password:
        raise ValueError("Enregistrez le mot de passe iCloud dans Réglages → iCloud")
    icloudpd = venv_executable("icloudpd")
    if icloudpd is None:
        raise ValueError(
            "icloudpd n’est pas installé. Relancez start-linux.sh, start-mac.command "
            "ou start-windows.bat, ou : pip install icloudpd"
        )
    start, end, label = _period(year, month)
    dest_path = Path(dest).expanduser()
    dest_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(icloudpd),
        "--username",
        user,
        "--password-provider",
        "parameter",
        "--password",
        password,
        "--mfa-provider",
        "console",
        "--directory",
        str(dest_path),
        "--folder-structure",
        "{:%Y/%m}",
        "--skip-created-before",
        start.isoformat(),
        "--skip-created-after",
        end.isoformat(),
        "--log-level",
        "info",
    ]
    emit(
        progress,
        0,
        None,
        "prog.icloudAuth",
        f"iCloud {label} : authentification…",
        label=label,
    )
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    with _lock:
        _proc = proc
    mfa_shown = False
    lines: list[str] = []
    got = 0
    before = _count_media(dest_path)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            text = line.rstrip()
            lines.append(text)
            low = text.lower()
            if _looks_like_mfa(text) and not mfa_shown:
                mfa_shown = True
                if patch:
                    patch(mfa_needed=True)
                emit(
                    progress,
                    got,
                    None,
                    "prog.icloudMfa",
                    "Code demandé par Apple. Il s’affiche sur l’iPhone ou l’iPad. Saisissez-le dans Paramètres.",
                )
                continue
            if "downloaded" in low or "would download" in low:
                got += 1
                if patch:
                    patch(mfa_needed=False)
                emit(
                    progress,
                    got,
                    None,
                    "prog.icloudGot",
                    f"{got} fichier(s) reçu(s)",
                    n=got,
                )
            elif "looking up" in low or "authenticat" in low:
                emit(
                    progress,
                    got,
                    None,
                    "prog.icloudAuth",
                    f"iCloud {label} : authentification…",
                    label=label,
                )
        code = proc.wait()
    finally:
        with _lock:
            if _proc is proc:
                _proc = None
        if proc.stdin:
            try:
                proc.stdin.close()
            except OSError:
                pass
    if patch:
        patch(mfa_needed=False)
    if code != 0:
        tail = "\n".join(lines[-12:]) or f"icloudpd a quitté ({code})"
        blob = "\n".join(lines).lower()
        if "setup is not complete" in blob or "authentication_failed" in blob:
            tail += (
                "\n\nApple a accepté le compte, mais refuse l’accès web Photos.\n"
                "Ouvrez https://www.icloud.com/photos, acceptez les conditions "
                "si elles s’affichent, puis relancez le téléchargement."
            )
        raise RuntimeError(tail)
    added = max(got, max(0, _count_media(dest_path) - before))
    emit(
        progress,
        added,
        added or 1,
        "prog.icloudDone",
        f"iCloud {label} terminé : {added} fichier(s) → {dest_path}",
        label=label,
        n=added,
        dest=str(dest_path),
    )
    return {"year": year, "month": month, "dest": str(dest_path), "label": label, "files": added}
