from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from photo_library.config import MEDIA_SUFFIXES
from photo_library.jobs import JobText, emit
from photo_library.metadata import taken_at_for
from photo_library.scan import kind_of
from photo_library.user_config import load_settings

Progress = Callable[[int, int | None, str], None]

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "__pycache__", ".git", "@eadir", ".trash", ".corbeille", "thumbs"}


def sort_script() -> Path:
    local = ROOT / "tools" / "sort_lieux.py"
    if local.is_file():
        return local
    sibling = ROOT.parent / "photo-sort-lieux" / "sort_lieux.py"
    if sibling.is_file():
        return sibling
    raise JobText(
        "prog.noSortTool",
        "Outil de classement introuvable (tools/sort_lieux.py).",
    )


def year_month_script() -> Path:
    local = ROOT / "tools" / "sort_annee_mois.py"
    if local.is_file():
        return local
    sibling = ROOT.parent / "photo-sort-lieux" / "sort_annee_mois.py"
    if sibling.is_file():
        return sibling
    raise JobText(
        "prog.noMonthTool",
        "Outil année / mois introuvable (tools/sort_annee_mois.py).",
    )


def classify_sort_line(text: str) -> tuple[str, dict]:
    """Reconnaît les lignes du classeur pour les traduire dans le bandeau."""
    raw = " ".join(text.split())
    if not raw:
        return "", {}
    low = raw.lower()
    gps = re.search(r"gps\s+(\d+)\s*/\s*(\d+)", low)
    if gps:
        return "prog.gps", {"n": gps.group(1), "total": gps.group(2)}
    found = re.search(r"médias dans le triage\s*:\s*(\d+)", low)
    if found:
        return "prog.triageMedia", {"n": found.group(1)}
    found = re.search(r"médias dans le dossier\s*:\s*(\d+)", low)
    if found:
        return "prog.fbCount", {"n": found.group(1)}
    found = re.search(r"(\d+)\s+médias à ranger", low)
    if found:
        return "prog.toSort", {"n": found.group(1)}
    found = re.search(r"(\d+)\s+médias en vrac", low)
    if found:
        return "prog.loose", {"n": found.group(1)}
    found = re.search(r"lecture gps de\s+(\d+)", low)
    if found:
        return "prog.readingGps", {"n": found.group(1)}
    if "creation_timestamp" in low or "message_*.json" in low:
        return "prog.fbDates", {}
    if low.startswith("cible") and "annee" in low:
        return "prog.targetMonths", {}
    if "dry-run" in low:
        return "prog.dry", {}
    if "application (copie" in low:
        return "prog.applyMode", {}
    if "aucun fichier copié" in low or "aucun fichier copie" in low:
        return "prog.nothingWritten", {}
    if raw.startswith("==="):
        return "prog.section", {"name": raw.strip("= ").strip()}
    copied = re.match(r"nouveau\s+(.+?)\s+->\s+(.+)$", raw, re.I)
    if copied:
        return "prog.newFile", {"name": copied.group(1), "dest": copied.group(2)}
    duplicate = re.match(r"doublon\s+(.+?)\s+=", raw, re.I)
    if duplicate:
        return "prog.dup", {"name": duplicate.group(1)}
    return "", {}


def _run_sort(cmd: list[str], progress: Progress, *, cwd: Path | None = None) -> None:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd) if cwd else None,
    )
    assert proc.stdout is not None
    lines: list[str] = []
    done = 0
    total = None
    for line in proc.stdout:
        text = line.rstrip()
        lines.append(text)
        if not text:
            continue
        gps = re.search(r"GPS\s+(\d+)/(\d+)", text, re.I)
        if gps:
            done = int(gps.group(1))
            total = int(gps.group(2))
            code, fields = classify_sort_line(text)
            progress(done, total, text[:180], code, fields)
            continue
        nums = [int(x) for x in re.findall(r"\d+", text)]
        low = text.lower()
        if "médias dans le triage" in low or "médias à la racine" in low:
            if nums:
                total = nums[-1]
        if text.startswith("==="):
            done += 1
        elif any(k in low for k in ("copié", "copied", "déplacé", "à déplacer", "nouveaux")):
            if nums:
                done = max(done, nums[0])
        code, fields = classify_sort_line(text)
        progress(done, total, text[:180], code, fields)
    code = proc.wait()
    if code != 0:
        tail = "\n".join(lines[-15:]) or f"classement a quitté ({code})"
        raise RuntimeError(tail)


def ingest_dump(src: Path, dest: Path, progress: Progress) -> dict:
    src = src.expanduser().resolve()
    dest = dest.expanduser().resolve()
    if not src.is_dir():
        raise JobText(
            "prog.dumpMissing",
            f"Dossier source introuvable : {src}",
            path=str(src),
        )
    dest.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if any(part.lower() in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        kind = kind_of(path) or "photo"
        try:
            path.resolve().relative_to(dest)
            continue
        except ValueError:
            pass
        files.append(path)
    copied = 0
    total = len(files)
    for i, path in enumerate(files, start=1):
        kind = kind_of(path) or "photo"
        year = int(taken_at_for(path, kind)[:4])
        year_dir = dest / f"Annee {year}"
        year_dir.mkdir(parents=True, exist_ok=True)
        target = year_dir / path.name
        if target.exists() and target.stat().st_size == path.stat().st_size:
            emit(progress, i, total, "prog.already", f"Déjà présent : {path.name}", name=path.name)
            continue
        n = 2
        while target.exists():
            target = year_dir / f"{path.stem}_{n}{path.suffix}"
            n += 1
        shutil.copy2(path, target)
        copied += 1
        emit(
            progress,
            i,
            total,
            "prog.copyYear",
            f"Copie {path.name} → Annee {year}",
            name=path.name,
            year=year,
        )
    return {"files": total, "copied": copied}


def run_classer(apply: bool, progress: Progress, source: str = "triage") -> dict:
    cfg = load_settings()
    kind = (cfg.get("phone_kind") or "iphone").strip().lower()
    source = (source or "triage").strip().lower()
    if source not in {"triage", "library", "year-month"}:
        source = "triage"
    dest_raw = (cfg.get("library_dest") or cfg.get("library_src") or "").strip()
    if not dest_raw:
        raise JobText(
            "prog.needDest",
            "Indiquez le nouvel emplacement de la bibliothèque dans Paramètres, section Classer.",
        )
    dest = Path(dest_raw).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    script = str(sort_script())
    py = sys.executable
    summary: dict = {
        "apply": apply,
        "phone_kind": kind,
        "source": source,
        "library": str(dest),
    }

    if source == "year-month":
        src_raw = (cfg.get("library_src") or dest_raw).strip()
        src = Path(src_raw).expanduser() if src_raw else dest
        if not src.is_dir():
            raise JobText(
                "prog.needLibrary",
                "Indiquez la bibliothèque actuelle dans Paramètres, section Classer.",
            )
        mois = year_month_script()
        emit(progress, 0, None, "prog.yearMonth", "Classement par année / mois…")
        cmd = [py, str(mois), str(src), str(dest)]
        if apply:
            cmd.append("--apply")
        _run_sort(cmd, progress, cwd=mois.parent)
        if apply:
            summary["message"] = (
                "Classement année / mois terminé. Cliquez sur Indexer, puis « Classer la bibliothèque actuelle » pour les villes GPS."
            )
            code = "prog.yearDone"
        else:
            summary["message"] = (
                "Simulation année / mois. Aucun fichier écrit. Relancez « Classer année / mois » pour écrire."
            )
            code = "prog.yearSim"
        emit(progress, 1, 1, code, summary["message"])
        return summary

    if source == "triage":
        if kind == "android":
            dump = (cfg.get("google_dir") or cfg.get("library_src") or "").strip()
            if dump:
                dump_path = Path(dump).expanduser()
                if dump_path.resolve() != dest.resolve():
                    emit(
                        progress,
                        0,
                        None,
                        "prog.googleCopy",
                        "Copie Google Photos / Takeout vers la bibliothèque…",
                    )
                    if apply:
                        summary["ingest"] = ingest_dump(dump_path, dest, progress)
                    else:
                        summary["ingest"] = {"dry_run": True, "source": str(dump_path)}
                        emit(
                            progress,
                            0,
                            None,
                            "prog.simFrom",
                            f"Simulation : copie depuis {dump_path}",
                            path=str(dump_path),
                        )
        elif kind == "facebook":
            facebook = (cfg.get("facebook_dir") or "").strip()
            if not facebook:
                raise JobText(
                    "prog.needFacebook",
                    "Indiquez le dossier de l’archive Facebook dans Paramètres.",
                )
            facebook_path = Path(facebook).expanduser()
            if not facebook_path.is_dir():
                raise JobText(
                    "prog.facebookMissing",
                    f"Dossier Facebook introuvable : {facebook_path}",
                    path=str(facebook_path),
                )
            emit(progress, 0, None, "prog.facebook", "Lecture de l’archive Facebook…")
            cmd = [
                py,
                script,
                "--library",
                str(dest),
                "--facebook",
                "--facebook-dir",
                str(facebook_path),
            ]
            if apply:
                cmd.append("--apply")
            _run_sort(cmd, progress)
            if apply:
                summary["message"] = (
                    "Classement Facebook terminé. Cliquez sur Indexer pour voir les photos."
                )
                code = "prog.facebookDone"
            else:
                summary["message"] = (
                    "Simulation Facebook terminée. Aucun fichier écrit. Relancez « Classer depuis Facebook » pour écrire."
                )
                code = "prog.facebookSim"
            emit(progress, 1, 1, code, summary["message"])
            return summary
        else:
            triage = (cfg.get("triage_dir") or "").strip()
            if not triage:
                if apply:
                    raise JobText(
                        "prog.needTriage",
                        "Indiquez le dossier de triage dans Paramètres, section iCloud.",
                    )
                emit(
                    progress,
                    0,
                    None,
                    "prog.noTriage",
                    "Pas de dossier de triage : simulation du classement par lieu de la bibliothèque seulement.",
                )
            else:
                emit(progress, 0, None, "prog.ingest", "Lecture du dossier de triage…")
                cmd = [
                    py,
                    script,
                    "--library",
                    str(dest),
                    "--triage",
                    "--triage-dir",
                    str(Path(triage).expanduser()),
                ]
                if apply:
                    cmd.append("--apply")
                _run_sort(cmd, progress)
    else:
        src_raw = (cfg.get("library_src") or dest_raw).strip()
        if not src_raw:
            raise JobText(
                "prog.needLibrary",
                "Indiquez la bibliothèque actuelle dans Paramètres, section Classer.",
            )
        emit(
            progress,
            0,
            None,
            "prog.libraryOnly",
            "Classement de la bibliothèque actuelle (sans le triage)…",
        )

    emit(progress, 0, None, "prog.gpsSort", "Classement par lieu…")
    cmd = [py, script, "--library", str(dest), "--all"]
    if apply:
        cmd.append("--apply")
    _run_sort(cmd, progress)
    if apply:
        summary["message"] = (
            "Classement terminé. Cliquez sur Indexer pour voir les photos dans la galerie."
        )
        code = "prog.sortDone"
    else:
        summary["message"] = (
            "Simulation terminée. Aucun fichier n’a été déplacé. Relancez « Classer » pour écrire."
        )
        code = "prog.sortSim"
    emit(progress, 1, 1, code, summary["message"])
    return summary
