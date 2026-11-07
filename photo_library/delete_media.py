"""Corbeille : les originaux quittent la galerie mais restent restaurables 30 jours."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from photo_library.jobs import emit
from photo_library.thumbs import (
    dhash_from_image,
    face_thumb_file,
    make_preview,
    make_thumb,
    preview_file,
    thumb_file,
)

CORBEILLE = ".corbeille"
KEEP_DAYS = 30


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_utc().isoformat()


def path_in_library(library: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(library.resolve())
        return True
    except (OSError, ValueError):
        return False


def _unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _unlink_caches(cache: Path, conn, media_id: int) -> None:
    face_ids = [
        int(r["id"])
        for r in conn.execute("SELECT id FROM faces WHERE media_id=?", (media_id,))
    ]
    for face_id in face_ids:
        face_thumb_file(cache, face_id).unlink(missing_ok=True)
    thumb_file(cache, media_id).unlink(missing_ok=True)
    preview_file(cache, media_id).unlink(missing_ok=True)


def trash_selected(
    conn,
    library: Path,
    cache: Path,
    ids: list[int],
    progress=None,
) -> dict:
    """Déplace les fichiers vers `.corbeille/` et les retire de la galerie."""
    library = library.resolve()
    trashed: list[int] = []
    errors: list[dict] = []
    stamp = now_iso()
    total = len(ids)
    for i, media_id in enumerate(ids, start=1):
        row = conn.execute(
            "SELECT id, relpath, present FROM media WHERE id=?",
            (media_id,),
        ).fetchone()
        if row is None:
            errors.append({"id": media_id, "error": "introuvable"})
        elif conn.execute("SELECT 1 FROM trash WHERE media_id=?", (media_id,)).fetchone():
            errors.append({"id": media_id, "error": "déjà à la corbeille"})
        else:
            orig = row["relpath"]
            if not orig or orig.startswith(CORBEILLE + "/") or orig == CORBEILLE:
                errors.append({"id": media_id, "error": "chemin de corbeille invalide"})
            else:
                src = library / orig
                try:
                    resolved = src.resolve()
                except OSError:
                    resolved = src
                if resolved.exists() and not path_in_library(library, resolved):
                    errors.append({"id": media_id, "error": "chemin hors bibliothèque"})
                else:
                    dest = _unique_path(library / CORBEILLE / orig)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    moved_ok = True
                    if resolved.is_file():
                        try:
                            shutil.move(str(resolved), str(dest))
                        except OSError as exc:
                            errors.append({"id": media_id, "error": str(exc)})
                            moved_ok = False
                        trash_rel = str(dest.relative_to(library))
                    else:
                        trash_rel = str(Path(CORBEILLE) / orig)
                    if moved_ok:
                        conn.execute(
                            "INSERT INTO trash (media_id, orig_relpath, trash_relpath, trashed_at) VALUES (?, ?, ?, ?)",
                            (media_id, orig, trash_rel, stamp),
                        )
                        conn.execute(
                            "UPDATE media SET present=0, relpath=? WHERE id=?",
                            (trash_rel, media_id),
                        )
                        trashed.append(media_id)
                        conn.commit()
        if progress:
            emit(
                progress,
                i,
                total,
                "prog.trashing",
                f"Corbeille {len(trashed)}/{total}",
                n=len(trashed),
                total=total,
            )
    conn.commit()
    return {"trashed": len(trashed), "ids": trashed, "errors": errors, "keep_days": KEEP_DAYS}


def restore_selected(
    conn,
    library: Path,
    ids: list[int],
    cache: Path | None = None,
    progress=None,
) -> dict:
    library = library.resolve()
    restored: list[int] = []
    errors: list[dict] = []
    total = len(ids)
    for i, media_id in enumerate(ids, start=1):
        try:
            row = conn.execute(
                """
                SELECT t.orig_relpath, t.trash_relpath, t.reason, t.restore_id, m.relpath
                FROM trash t JOIN media m ON m.id = t.media_id
                WHERE t.media_id=?
                """,
                (media_id,),
            ).fetchone()
            if row is None:
                errors.append({"id": media_id, "error": "pas dans la corbeille"})
                continue
            reason = (row["reason"] or "deleted") if "reason" in row.keys() else "deleted"
            if reason == "edit":
                sp = f"sp_edit_{int(media_id)}"
                conn.execute(f"SAVEPOINT {sp}")
                try:
                    restore_edit_backup(conn, library, cache, media_id, row)
                    conn.execute(f"RELEASE SAVEPOINT {sp}")
                except FileNotFoundError as exc:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                    errors.append({"id": media_id, "error": str(exc)})
                    continue
                except OSError as exc:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                    errors.append({"id": media_id, "error": str(exc)})
                    continue
                restored.append(media_id)
                conn.commit()
                continue
            src = library / (row["trash_relpath"] or row["relpath"])
            dest = _unique_path(library / row["orig_relpath"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                try:
                    if not path_in_library(library, src.resolve()):
                        errors.append({"id": media_id, "error": "chemin hors bibliothèque"})
                        continue
                    shutil.move(str(src), str(dest))
                except OSError as exc:
                    errors.append({"id": media_id, "error": str(exc)})
                    continue
            new_rel = str(dest.relative_to(library)) if dest.exists() else row["orig_relpath"]
            conn.execute(
                "UPDATE media SET present=1, relpath=? WHERE id=?",
                (new_rel, media_id),
            )
            conn.execute("DELETE FROM trash WHERE media_id=?", (media_id,))
            restored.append(media_id)
            conn.commit()
        finally:
            if progress:
                emit(
                    progress,
                    i,
                    total,
                    "prog.restoring",
                    f"Restauration {len(restored)}/{total}",
                    n=len(restored),
                    total=total,
                )
    conn.commit()
    return {"restored": len(restored), "ids": restored, "errors": errors}


def restore_edit_backup(conn, library: Path, cache: Path | None, backup_id: int, row) -> None:
    """Remet l’original à la place de la photo pivotée / rognée."""
    orig_rel = row["orig_relpath"]
    trash_rel = row["trash_relpath"] or row["relpath"]
    restore_id = row["restore_id"] if "restore_id" in row.keys() else None
    src = library / trash_rel
    dest = library / orig_rel
    live = None
    if restore_id:
        live = conn.execute("SELECT * FROM media WHERE id=?", (int(restore_id),)).fetchone()
    live_present = live is not None and int(live["present"] or 0) == 1
    if live_present:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            if not path_in_library(library, src.resolve()):
                raise FileNotFoundError("chemin hors bibliothèque")
            if dest.exists() and dest.resolve() != src.resolve():
                dest.unlink()
            shutil.move(str(src), str(dest))
        leftover = library / live["relpath"]
        if live["relpath"] != orig_rel and leftover.is_file():
            if leftover.resolve() != dest.resolve():
                leftover.unlink()
        if not dest.is_file():
            raise FileNotFoundError("original introuvable dans la corbeille")
        st = dest.stat()
        width = live["width"]
        height = live["height"]
        try:
            from PIL import Image

            with Image.open(dest) as img:
                width, height = img.size
        except OSError:
            pass
        digest = live["dhash"]
        if cache is not None:
            thumb = thumb_file(cache, int(live["id"]))
            preview = preview_file(cache, int(live["id"]))
            thumb.unlink(missing_ok=True)
            preview.unlink(missing_ok=True)
            make_thumb(dest, thumb, "photo")
            make_preview(dest, preview, "photo")
            digest = dhash_from_image(thumb)
        from photo_library.paths import pair_key_of

        conn.execute(
            """
            UPDATE media SET
                relpath=?, size=?, mtime_ns=?, present=1, thumb_ok=1, face_scanned=0,
                width=?, height=?, dhash=?, pair_key=?
            WHERE id=?
            """,
            (
                orig_rel,
                st.st_size,
                getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                width,
                height,
                digest,
                pair_key_of(orig_rel),
                int(live["id"]),
            ),
        )
        conn.execute("DELETE FROM trash WHERE media_id=?", (backup_id,))
        if cache is not None:
            _unlink_caches(cache, conn, backup_id)
        conn.execute("DELETE FROM media WHERE id=?", (backup_id,))
        return
    dest = _unique_path(library / orig_rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        if not path_in_library(library, src.resolve()):
            raise FileNotFoundError("chemin hors bibliothèque")
        shutil.move(str(src), str(dest))
    new_rel = str(dest.relative_to(library)) if dest.exists() else orig_rel
    conn.execute(
        "UPDATE media SET present=1, relpath=? WHERE id=?",
        (new_rel, backup_id),
    )
    conn.execute("DELETE FROM trash WHERE media_id=?", (backup_id,))


def purge_selected(conn, library: Path, cache: Path, ids: list[int], progress=None) -> dict:
    """Effacement définitif (corbeille ou, rare, fichier encore en place)."""
    library = library.resolve()
    deleted: list[int] = []
    errors: list[dict] = []
    total = len(ids)
    for i, media_id in enumerate(ids, start=1):
        try:
            row = conn.execute(
                "SELECT id, relpath FROM media WHERE id=?",
                (media_id,),
            ).fetchone()
            if row is None:
                errors.append({"id": media_id, "error": "introuvable"})
                continue
            src = library / row["relpath"]
            try:
                resolved = src.resolve()
            except OSError:
                resolved = src
            if resolved.exists() and not path_in_library(library, resolved):
                errors.append({"id": media_id, "error": "chemin hors bibliothèque"})
                continue
            if resolved.is_file():
                try:
                    resolved.unlink()
                except OSError as exc:
                    errors.append({"id": media_id, "error": str(exc)})
                    continue
            _unlink_caches(cache, conn, media_id)
            conn.execute("DELETE FROM trash WHERE media_id=?", (media_id,))
            conn.execute("DELETE FROM media WHERE id=?", (media_id,))
            deleted.append(media_id)
            conn.commit()
        finally:
            if progress:
                emit(
                    progress,
                    i,
                    total,
                    "prog.purging",
                    f"Effacement {len(deleted)}/{total}",
                    n=len(deleted),
                    total=total,
                )
    conn.commit()
    return {"deleted": len(deleted), "ids": deleted, "errors": errors}


def delete_selected(conn, library: Path, cache: Path, ids: list[int]) -> dict:
    """Galerie : mise à la corbeille (plus d’effacement immédiat)."""
    result = trash_selected(conn, library, cache, ids)
    return {
        "deleted": result["trashed"],
        "trashed": result["trashed"],
        "ids": result["ids"],
        "errors": result["errors"],
        "keep_days": result["keep_days"],
    }


def trash_cutoff_iso() -> str:
    return (now_utc() - timedelta(days=KEEP_DAYS)).isoformat()


def trash_count(conn, include_expired: bool = False) -> int:
    if include_expired:
        return int(conn.execute("SELECT COUNT(*) FROM trash").fetchone()[0])
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM trash WHERE trashed_at >= ?",
            (trash_cutoff_iso(),),
        ).fetchone()[0]
    )


def expired_trash_count(conn) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM trash WHERE trashed_at < ?",
            (trash_cutoff_iso(),),
        ).fetchone()[0]
    )


def expired_trash_ids(conn) -> list[int]:
    return [
        int(r["media_id"])
        for r in conn.execute(
            "SELECT media_id FROM trash WHERE trashed_at < ? ORDER BY media_id",
            (trash_cutoff_iso(),),
        ).fetchall()
    ]


def list_trash_ids(conn, include_expired: bool = False) -> list[int]:
    sql = "SELECT media_id FROM trash"
    params: tuple = ()
    if not include_expired:
        sql += " WHERE trashed_at >= ?"
        params = (trash_cutoff_iso(),)
    sql += " ORDER BY trashed_at DESC, media_id DESC"
    return [int(r["media_id"]) for r in conn.execute(sql, params).fetchall()]


def list_trash(
    conn,
    offset: int = 0,
    limit: int | None = None,
    include_expired: bool = False,
) -> list[dict]:
    sql = """
        SELECT m.id, m.relpath, m.kind, m.year, m.place, m.taken_at, m.thumb_ok, m.mtime_ns, m.size,
               t.orig_relpath, t.trashed_at, t.reason, t.restore_id
        FROM trash t
        JOIN media m ON m.id = t.media_id
    """
    params: list = []
    if not include_expired:
        sql += " WHERE t.trashed_at >= ?"
        params.append(trash_cutoff_iso())
    sql += " ORDER BY t.trashed_at DESC, m.id DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
    rows = conn.execute(sql, params).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["name"] = Path(row["orig_relpath"] or row["relpath"]).name
        item["reason"] = (row["reason"] if "reason" in item else None) or "deleted"
        items.append(item)
    return items


def purge_expired(conn, library: Path, cache: Path, progress=None) -> dict:
    ids = expired_trash_ids(conn)
    if not ids:
        return {"deleted": 0, "ids": [], "errors": []}
    return purge_selected(conn, library, cache, ids, progress=progress)
