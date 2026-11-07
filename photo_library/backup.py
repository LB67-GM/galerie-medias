"""Sauvegarde SQLite + réglages vers un dossier daté (NAS ou autre ordinateur)."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from photo_library.db import db_path
from photo_library.jobs import emit
from photo_library.user_config import config_path, key_path, load_settings

Progress = Callable[[int, int | None, str], None]

BACKUP_DIR_RE = re.compile(r"^backup[-_=](\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
KEEP_BACKUPS = 4
MANIFEST_NAME = "manifest.json"
SITE_ROOT = Path(__file__).resolve().parent.parent
SITE_SKIP_DIRS = {
    ".venv",
    "__pycache__",
    "dist",
    ".git",
    ".cursor",
    ".mypy_cache",
    ".pytest_cache",
    ".proto-demo",
}


def is_backup_folder_name(name: str) -> bool:
    return bool(BACKUP_DIR_RE.match(name.strip()))


def backup_parent(library: Path) -> Path:
    raw = (load_settings().get("backup_dir") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return library


def backup_folder_name(when: date | None = None) -> str:
    return f"backup-{(when or date.today()).isoformat()}"


def list_backup_dirs(parent: Path) -> list[Path]:
    if not parent.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    try:
        children = list(parent.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        match = BACKUP_DIR_RE.match(child.name)
        if match:
            found.append((match.group(1), child))
    found.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in found]


def _copy_if_exists(
    src: Path,
    dest: Path,
    progress: Progress | None,
    step: int,
    total: int,
    label: str,
    code: str,
) -> bool:
    emit(progress, step, total, code, label)
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _mb(n: int) -> int:
    return max(0, n) // (1024 * 1024)


def _copy_file_chunked(
    src: Path,
    dest: Path,
    progress: Progress | None,
    step: int,
    total: int,
    label: str,
) -> int:
    """Copie un fichier déjà clos (NAS/CIFS : pas d’API SQLite sur la destination)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial")
    size = src.stat().st_size
    copied = 0
    emit(
        progress,
        step,
        total,
        "prog.backupSend",
        f"{label} 0/{_mb(size)} Mo",
        done=0,
        total=_mb(size),
    )
    with src.open("rb") as inf, tmp.open("wb") as out:
        while True:
            chunk = inf.read(8 * 1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            copied += len(chunk)
            emit(
                progress,
                step,
                total,
                "prog.backupSend",
                f"{label} {_mb(copied)}/{_mb(size)} Mo",
                done=_mb(copied),
                total=_mb(size),
            )
    tmp.replace(dest)
    return size


def _site_ignore(_directory: str, names: list[str]) -> list[str]:
    skipped: list[str] = []
    for name in names:
        if name in SITE_SKIP_DIRS:
            skipped.append(name)
        elif name.endswith((".pyc", ".pyo")):
            skipped.append(name)
        elif name.startswith("library.sqlite"):
            skipped.append(name)
    return skipped


def copy_site(
    dest_site: Path,
    *,
    progress: Progress | None = None,
    step: int = 2,
    total: int = 6,
) -> dict:
    """Copie HTML/CSS/JS + code Python (sans .venv ni cache)."""
    dest_site = dest_site.expanduser()
    if progress:
        emit(progress, step, total, "prog.siteCopy", "Copie du site (pages, CSS, JS, code)…")
    if dest_site.exists():
        shutil.rmtree(dest_site)
    shutil.copytree(SITE_ROOT, dest_site, ignore=_site_ignore, symlinks=False)
    sort_src = SITE_ROOT.parent / "photo-sort-lieux" / "sort_lieux.py"
    if sort_src.is_file():
        tools = dest_site / "tools"
        tools.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sort_src, tools / "sort_lieux.py")
    mois_src = SITE_ROOT.parent / "photo-sort-lieux" / "sort_annee_mois.py"
    if mois_src.is_file():
        tools = dest_site / "tools"
        tools.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mois_src, tools / "sort_annee_mois.py")
    n_files = sum(1 for path in dest_site.rglob("*") if path.is_file())
    if progress:
        emit(
            progress,
            step,
            total,
            "prog.siteCopied",
            f"Site copié ({n_files} fichiers)",
            n=n_files,
        )
    return {"path": str(dest_site), "files": n_files}


def _backup_sqlite(
    src: Path,
    dest: Path,
    *,
    progress: Progress | None = None,
    step: int = 1,
    total: int = 6,
) -> tuple[int, int | None]:
    """Cliché SQLite en local, puis copie du fichier vers dest (NAS inclus)."""
    if not src.is_file():
        raise FileNotFoundError(f"Base introuvable : {src}")
    local_tmp = src.with_name("library.sqlite.backup-tmp")
    if local_tmp.exists():
        local_tmp.unlink()
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=60)
    try:
        dst_conn = sqlite3.connect(str(local_tmp), timeout=60)
        try:

            def on_pages(_status: int, remaining: int, page_total: int) -> None:
                if not progress or not page_total:
                    return
                done = page_total - remaining
                emit(
                    progress,
                    step,
                    total,
                    "prog.backupPages",
                    f"Cliché local de la base… {done}/{page_total} pages",
                    done=done,
                    total=page_total,
                )

            src_conn.backup(dst_conn, pages=400, progress=on_pages)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    media = _media_count(local_tmp)
    try:
        size = _copy_file_chunked(
            local_tmp,
            dest,
            progress,
            step,
            total,
            "Envoi de la base vers la destination",
        )
    finally:
        local_tmp.unlink(missing_ok=True)
    return size, media


def _media_count(sqlite_file: Path) -> int | None:
    if not sqlite_file.is_file():
        return None
    conn = sqlite3.connect(str(sqlite_file), timeout=15)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM media WHERE present=1"
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def prune_old_backups(parent: Path, keep: int = KEEP_BACKUPS) -> list[str]:
    removed: list[str] = []
    dirs = list_backup_dirs(parent)
    for extra in dirs[keep:]:
        shutil.rmtree(extra, ignore_errors=True)
        removed.append(extra.name)
    return removed


def run_backup(
    library: Path,
    cache: Path,
    *,
    progress: Progress | None = None,
    dest_parent: Path | None = None,
) -> dict:
    parent = dest_parent.expanduser() if dest_parent else backup_parent(library)
    folder = parent / backup_folder_name()
    total = 6
    if progress:
        emit(progress, 0, total, "prog.backupCreate", f"Création {folder}", path=str(folder))
    folder.mkdir(parents=True, exist_ok=True)

    sqlite_src = db_path(cache)
    sqlite_dest = folder / "library.sqlite"
    if progress:
        emit(progress, 1, total, "prog.backupSnap", "Cliché local de la base…")
    size, media_count = _backup_sqlite(
        sqlite_src, sqlite_dest, progress=progress, step=1, total=total
    )

    site_info = copy_site(folder / "site", progress=progress, step=2, total=total)

    copied_config = _copy_if_exists(
        config_path(),
        folder / "config.json",
        progress,
        3,
        total,
        "Réglages…",
        "prog.backupSettings",
    )
    copied_key = _copy_if_exists(
        key_path(),
        folder / "secret.key",
        progress,
        4,
        total,
        "Clé de chiffrement…",
        "prog.backupKey",
    )
    last_index = cache / "last-index.json"
    _copy_if_exists(
        last_index,
        folder / "last-index.json",
        progress,
        5,
        total,
        "Bilan d’index…",
        "prog.backupIndex",
    )

    manifest = {
        "app": "galerie-medias",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "folder": str(folder),
        "library": str(library),
        "cache": str(cache),
        "sqlite_bytes": size,
        "media_count": media_count,
        "has_config": copied_config,
        "has_secret_key": copied_key,
        "has_site": True,
        "site_files": site_info["files"],
        "restore": "python scripts/restore_backup.py " + str(folder),
    }
    (folder / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (folder / "RESTAURER.txt").write_text(
        "Sauvegarde Galerie Médias\n"
        f"Date : {date.today().isoformat()}\n\n"
        "Contenu :\n"
        "  library.sqlite     base (index, visages)\n"
        "  config.json        réglages\n"
        "  site/              pages HTML, CSS, JS et code Python (sans .venv)\n\n"
        "Réinstaller Python si besoin, puis :\n"
        "  python3 -m venv .venv && .venv/bin/python scripts/lire_paquets.py --write .paquets.txt && .venv/bin/pip install -r .paquets.txt\n"
        f"  python scripts/restore_backup.py \"{folder}\"\n"
        "ou, depuis une copie de site/ :\n"
        f"  .venv/bin/python run.py restore \"{folder}\"\n"
        "Option : --no-site pour ne restaurer que la base.\n",
        encoding="utf-8",
    )

    if progress:
        emit(progress, 6, total, "prog.backupRotate", "Rotation des anciennes sauvegardes…")
    pruned = prune_old_backups(parent)
    emit(progress, 6, total, "prog.backupDone", "Sauvegarde terminée")
    return {
        "folder": str(folder),
        "parent": str(parent),
        "sqlite_bytes": size,
        "media_count": manifest["media_count"],
        "site_files": site_info["files"],
        "pruned": pruned,
        "keep": KEEP_BACKUPS,
    }


def read_manifest(folder: Path) -> dict:
    path = folder / MANIFEST_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def restore_site(folder: Path, dest: Path) -> dict:
    src = folder.expanduser() / "site"
    if not src.is_dir():
        raise FileNotFoundError(f"Dossier site/ manquant dans {folder}")
    dest = dest.expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        out = dest / rel
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        copied += 1
    return {"site": str(dest), "files": copied}


def restore_backup(
    folder: Path,
    cache: Path,
    *,
    restore_config: bool = True,
    restore_site_to: Path | None = None,
) -> dict:
    folder = folder.expanduser()
    if not folder.is_dir():
        raise FileNotFoundError(f"Dossier de sauvegarde introuvable : {folder}")
    sqlite_src = folder / "library.sqlite"
    if not sqlite_src.is_file():
        raise FileNotFoundError(f"library.sqlite manquant dans {folder}")

    cache.mkdir(parents=True, exist_ok=True)
    sqlite_dest = db_path(cache)
    for extra in (sqlite_dest.with_name("library.sqlite-wal"), sqlite_dest.with_name("library.sqlite-shm")):
        if extra.exists():
            extra.unlink()
    tmp = sqlite_dest.with_name("library.sqlite.restore-tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(sqlite_src, tmp)
    tmp.replace(sqlite_dest)

    restored = {"sqlite": str(sqlite_dest), "config": None, "secret_key": None, "site": None}
    if restore_config:
        cfg_src = folder / "config.json"
        key_src = folder / "secret.key"
        if cfg_src.is_file():
            dest = config_path()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cfg_src, dest)
            restored["config"] = str(dest)
        if key_src.is_file():
            dest = key_path()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(key_src, dest)
            restored["secret_key"] = str(dest)
    if restore_site_to is not None and (folder / "site").is_dir():
        restored.update(restore_site(folder, restore_site_to))
    restored["folder"] = str(folder)
    restored["media_count"] = _media_count(sqlite_dest)
    return restored
