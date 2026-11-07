#!/usr/bin/env python3
"""Range une bibliothèque disparate : SOURCE -> DEST/Annee YYYY/Mois YYYY.

Syntaxe : sort_annee_mois.py SOURCE DEST [--apply]
Sans --apply : simulation. Les originaux restent dans SOURCE (copie).
Si SOURCE et DEST sont le même dossier : déplacement sur place.
Ensuite : sort_lieux.py -d DEST --all  (dossiers ville si GPS).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from sort_lieux import (
    MEDIA_SUFFIXES,
    YEAR_DIR_RE,
    is_month_folder,
    month_folder_name,
    skip_walk_dir,
    taken_from_media,
    unique_dest,
)

EXTRA_SKIP_DIRS = {".corbeille", "corbeille"}


def skip_dir(name: str) -> bool:
    if skip_walk_dir(name):
        return True
    return name.lower() in EXTRA_SKIP_DIRS


def already_year_month(rel: Path) -> bool:
    parts = rel.parts
    if len(parts) < 3:
        return False
    return bool(YEAR_DIR_RE.match(parts[0])) and is_month_folder(parts[1])


def dest_for(dest_root: Path, taken) -> Path:
    return dest_root / f"Annee {taken.year}" / month_folder_name(taken.year, taken.month)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def collect_jobs(
    source: Path,
    dest: Path,
    *,
    year_filter: int | None = None,
) -> tuple[list[tuple[Path, Path]], int]:
    source = source.resolve()
    dest = dest.resolve()
    same = source == dest
    already = 0
    planned: list[tuple[Path, Path]] = []
    used: set[str] = set()
    dest_exists = dest.is_dir()
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = [name for name in dirnames if not skip_dir(name)]
        here = Path(dirpath)
        if dest_exists and not same and _is_under(here, dest):
            dirnames[:] = []
            continue
        try:
            rel_dir = here.relative_to(source)
        except ValueError:
            continue
        in_month = (
            same
            and len(rel_dir.parts) >= 2
            and YEAR_DIR_RE.match(rel_dir.parts[0])
            and is_month_folder(rel_dir.parts[1])
        )
        if in_month:
            dirnames[:] = []
            already += sum(
                1
                for name in filenames
                if (here / name).is_file() and (here / name).suffix.lower() in MEDIA_SUFFIXES
            )
            continue
        for name in filenames:
            src = here / name
            if not src.is_file() or src.suffix.lower() not in MEDIA_SUFFIXES:
                continue
            try:
                rel = src.resolve().relative_to(source)
            except (OSError, ValueError):
                continue
            if same and already_year_month(rel):
                already += 1
                continue
            taken = taken_from_media(src)
            if year_filter is not None and taken.year != year_filter:
                continue
            dest_dir = dest_for(dest, taken)
            out = dest_dir / src.name
            try:
                if src.resolve() == out.resolve():
                    already += 1
                    continue
            except OSError:
                pass
            n = 2
            while out.exists() or str(out) in used:
                out = dest_dir / f"{src.stem}-{n}{src.suffix}"
                n += 1
            used.add(str(out))
            planned.append((src, out))
    planned.sort(key=lambda pair: (str(pair[1]), str(pair[0])))
    return planned, already


def prune_empty_dirs(root: Path) -> int:
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        folder = Path(dirpath)
        if folder.resolve() == root.resolve():
            continue
        if skip_dir(folder.name):
            continue
        try:
            if not any(folder.iterdir()):
                folder.rmdir()
                removed += 1
        except OSError:
            continue
    return removed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copie une arborescence disparate vers DEST/Annee YYYY/Mois YYYY. "
            "Sans --apply : simulation. Ensuite : sort_lieux -d DEST --all."
        )
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Dossier photos actuel (vrac / DCIM / arbre disparate)",
    )
    parser.add_argument(
        "dest",
        type=Path,
        help="Destination : Annee YYYY/Mois YYYY y sera créé",
    )
    parser.add_argument("--year", type=int, help="Limiter à une année")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrire vraiment (copie ; déplacement si source = destination)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Traiter seulement N fichiers")
    parser.add_argument("-v", "--verbose", action="store_true", help="Lister chaque fichier")
    return parser.parse_args(argv)


def _lieux_hint(dest: Path) -> None:
    lieux = Path(__file__).resolve().parent / "sort_lieux.py"
    print()
    print("Ensuite, dossiers ville (GPS) sur la destination :")
    print(f"  {sys.executable} {lieux} -d {dest} --all")
    print(f"  {sys.executable} {lieux} -d {dest} --all --apply")


def _configure_stdio() -> None:
    """Evite UnicodeEncodeError sur la console Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if not callable(reconf):
            continue
        try:
            reconf(encoding="utf-8", errors="replace")
            continue
        except Exception:
            pass
        try:
            reconf(errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = parse_args(argv)
    source = args.source.expanduser()
    dest = args.dest.expanduser()
    if not source.is_dir():
        print(f"Source introuvable : {source}", file=sys.stderr)
        return 1
    same = source.resolve() == dest.resolve()
    action = "déplacements" if same else "copies"
    planned, already = collect_jobs(source, dest, year_filter=args.year)
    if args.limit and args.limit > 0:
        planned = planned[: args.limit]
    dest_root = dest.resolve()
    by_dest: dict[str, int] = defaultdict(int)
    for _src, out in planned:
        try:
            by_dest[str(out.parent.relative_to(dest_root))] += 1
        except ValueError:
            by_dest[str(out.parent)] += 1
    print(f"Source       : {source.resolve()}")
    print(f"Destination  : {dest_root}")
    print("Mode         : " + ("APPLICATION (" + action + ")" if args.apply else "simulation (dry-run)"))
    print("Cible        : Annee YYYY / Mois YYYY  (ville = sort_lieux ensuite)")
    print(f"Ignorés      : {already} déjà sous Annee/Mois (si source = dest)")
    print(f"À traiter    : {len(planned)} médias")
    print()
    for folder in sorted(by_dest):
        print(f"  {folder}  ({by_dest[folder]})")
    if args.verbose:
        print()
        src_root = source.resolve()
        for src, out in planned:
            try:
                rel_src = src.resolve().relative_to(src_root)
            except ValueError:
                rel_src = src
            try:
                rel_dest = out.relative_to(dest_root)
            except ValueError:
                rel_dest = out
            print(f"  {rel_src}  ->  {rel_dest}")
    if not planned:
        print()
        print("Rien à faire.")
        _lieux_hint(dest_root)
        return 0
    if not args.apply:
        print()
        print("Aucun fichier écrit. Relancer avec --apply pour écrire.")
        _lieux_hint(dest_root)
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    done = 0
    errors = 0
    for src, out in planned:
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                out = unique_dest(out)
            if same:
                shutil.move(str(src), str(out))
            else:
                shutil.copy2(src, out)
            done += 1
            if args.verbose:
                print(f"OK  {src.name} -> {out.parent.name}/")
        except OSError as exc:
            errors += 1
            print(f"Erreur {src}: {exc}", file=sys.stderr)
    pruned = prune_empty_dirs(source.resolve()) if same else 0
    print()
    verb = "Déplacés" if same else "Copiés"
    extra = f"  dossiers vides retirés : {pruned}" if same else ""
    print(f"{verb} : {done}  erreurs : {errors}{extra}")
    _lieux_hint(dest_root)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
