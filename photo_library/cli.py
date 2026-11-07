from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from photo_library.auth import (
    create_user,
    delete_user_by_name,
    display_role,
    list_users,
    set_user_email,
    set_user_password,
    unlock_all_users,
    unlock_user,
)
from photo_library.config import (
    CAST_HTTP_PORT,
    DEFAULT_CACHE,
    DEFAULT_HOST,
    DEFAULT_LIBRARY,
    DEFAULT_PORT,
)
from photo_library.db import connect, init_schema
from photo_library.faces import scan_faces
from photo_library.scan import index_library, index_missing_files
from photo_library.thumbs import ensure_heif
from photo_library.user_config import data_dir, library_from_settings, portable_cache_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Galerie Médias : visualiser, filtrer, exporter, visages."
    )
    parser.add_argument(
        "-d",
        "--library",
        type=Path,
        default=None,
        help="Bibliothèque (sinon le dossier indiqué dans Réglages)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help=f"Cache SQLite + miniatures (défaut : {DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Mode portable (Mac/Windows) : réglages locaux, cache vide, chemins du fichier de config",
    )
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Lancer le site web local")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument(
        "--tls-host",
        action="append",
        default=[],
        metavar="NOM",
        help="Nom ou IP supplémentaire dans le certificat (répétable)",
    )

    index = sub.add_parser("index", help="Indexer fichiers et miniatures")
    g = index.add_mutually_exclusive_group()
    g.add_argument("--year", type=int, help="Une année (dossier Annee YYYY)")
    g.add_argument("--all", action="store_true", help="Toute la bibliothèque")
    index.add_argument("--limit", type=int, default=None)

    gps = sub.add_parser(
        "scan-gps",
        help="Lire le GPS EXIF (et l’index sort_lieux) pour la carte, sans recréer les miniatures",
    )
    gps.add_argument("--year", type=int, default=None)
    gps.add_argument("--limit", type=int, default=None)

    faces = sub.add_parser("faces", help="Détecter et rattacher les visages")
    faces.add_argument("--year", type=int, default=None)
    faces.add_argument("--limit", type=int, default=None)

    scenes = sub.add_parser(
        "scenes",
        help="Prototype : étiquettes paysage / bâtiment (sans toucher aux originaux)",
    )
    scenes.add_argument("--year", type=int, default=None)
    scenes.add_argument("--place", default=None, help="Lieu (ex. Paris), comme le filtre galerie")
    scenes.add_argument("--limit", type=int, default=None)

    users = sub.add_parser(
        "users",
        help="Créer, lister, déverrouiller ou changer un mot de passe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Mot de passe oublié : lien par courriel (Paramètres → Courriel),\n"
            "ou en ligne de commande :\n"
            "  python run.py users --set-password IDENTIFIANT\n"
            "  python run.py users --set-email IDENTIFIANT --email prenom@exemple.com\n"
            "  python run.py users --unlock IDENTIFIANT\n"
            "  python run.py users --list\n"
            "  python run.py users --create leo --role lecture --email leo@exemple.com\n"
            "  python run.py users --delete leo\n"
        ),
    )
    action = users.add_mutually_exclusive_group()
    action.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Lister les identifiants et les rôles",
    )
    action.add_argument(
        "--create",
        metavar="IDENTIFIANT",
        help="Créer un compte (rôle --role, mot de passe demandé)",
    )
    action.add_argument(
        "--delete",
        metavar="IDENTIFIANT",
        help="Supprimer un compte",
    )
    action.add_argument(
        "--set-password",
        metavar="IDENTIFIANT",
        help="Nouveau mot de passe (8+) et déverrouillage",
    )
    action.add_argument(
        "--set-email",
        metavar="IDENTIFIANT",
        help="Enregistrer le courriel d’un compte (vide pour l’effacer)",
    )
    action.add_argument(
        "--unlock",
        metavar="IDENTIFIANT",
        help="Remettre les essais à zéro (même mot de passe)",
    )
    action.add_argument(
        "--unlock-all",
        action="store_true",
        help="Déverrouiller tous les comptes",
    )
    users.add_argument(
        "--role",
        choices=["admin", "lecture"],
        default="lecture",
        help="Rôle à la création (défaut : lecture)",
    )
    users.add_argument(
        "--password",
        default=None,
        help="Mot de passe (--create ou --set-password ; sinon demandé sans affichage)",
    )
    users.add_argument(
        "--email",
        default="",
        help="Courriel (--create ou --set-email)",
    )
    users.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Ne pas demander confirmation à la suppression",
    )

    backup = sub.add_parser("backup", help="Sauvegarder la base, les réglages et le site")
    backup.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Dossier parent des backup-AAAA-MM-JJ (sinon réglage backup_dir)",
    )

    restore = sub.add_parser("restore", help="Restaurer une sauvegarde backup-AAAA-MM-JJ")
    restore.add_argument("folder", type=Path, help="Dossier backup-AAAA-MM-JJ")
    restore.add_argument(
        "--no-config",
        action="store_true",
        help="Ne pas écraser config.json / secret.key",
    )
    restore.add_argument(
        "--no-site",
        action="store_true",
        help="Ne pas restaurer les pages HTML/CSS/JS",
    )
    restore.add_argument(
        "--site-dest",
        type=Path,
        default=None,
        help="Dossier où copier site/ (défaut : le projet photo-library)",
    )

    completer = sub.add_parser(
        "completer-lieux",
        help="Parcourir la bibliothèque : index manquant + lieux vides + moments (dry-run par défaut)",
    )
    completer.add_argument(
        "--apply",
        action="store_true",
        help="Écrire SQLite (sinon simulation)",
    )
    completer.add_argument(
        "--no-index",
        action="store_true",
        help="Ne pas chercher / indexer les fichiers absents de SQLite",
    )
    completer.add_argument(
        "--keep-generic",
        action="store_true",
        help="Ne pas remplacer Vacances/Voyage par le sous-dossier (Portugal, Marseille…)",
    )
    return parser


def _progress(done: int, total: int | None, message: str) -> None:
    if total:
        print(f"[{done}/{total}] {message}", flush=True)
    else:
        print(f"[{done}] {message}", flush=True)


def _ask_password() -> str:
    try:
        first = getpass.getpass("Mot de passe : ")
        second = getpass.getpass("Encore une fois : ")
    except (EOFError, OSError) as exc:
        raise ValueError(
            "Pas de terminal : ajoutez --password MOTDEPASSE"
        ) from exc
    if first != second:
        raise ValueError("Les deux mots de passe ne correspondent pas.")
    return first


def _print_users(conn) -> None:
    rows = list_users(conn)
    if not rows:
        print("Aucun compte. Le site est ouvert (pas de page de connexion).")
        print("Pour activer la connexion : --create IDENTIFIANT --role admin")
        return
    name_w = max(12, max(len(str(r["username"])) for r in rows))
    print(f"{'Identifiant':<{name_w}}  Rôle      État  Courriel")
    print(f"{'-' * name_w}  --------  ----  --------")
    for row in rows:
        state = "pause" if row.get("locked") else "ok"
        mail = row.get("email") or "—"
        print(
            f"{row['username']:<{name_w}}  {display_role(str(row['role'])):<8}  {state:<4}  {mail}"
        )
    n = len(rows)
    print()
    print(f"{n} compte{'s' if n > 1 else ''}. Connexion obligatoire.")
    print(
        "Mot de passe oublié : lien par courriel, ou --set-password IDENTIFIANT"
    )


def _confirm_delete(username: str) -> bool:
    try:
        reply = input(f"Supprimer {username} ? [o/N] ").strip().lower()
    except (EOFError, OSError):
        return False
    return reply in {"o", "oui", "y", "yes"}


def _run_users(args, cache: Path) -> int:
    cache.mkdir(parents=True, exist_ok=True)
    conn = connect(cache)
    init_schema(conn, refresh_places=False)
    try:
        if args.create:
            password = args.password
            if not password:
                try:
                    password = _ask_password()
                except ValueError as exc:
                    print(str(exc), file=sys.stderr)
                    return 1
            try:
                user = create_user(
                    conn, args.create, password, args.role, args.email or ""
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            note = ""
            if user.get("first") and args.role != "admin":
                note = " (premier compte : admin obligatoire)"
            mail = f"  {user['email']}" if user.get("email") else ""
            print(f"Créé : {user['username']}  rôle {display_role(user['role'])}{note}{mail}")
            return 0
        if args.set_email:
            try:
                updated = set_user_email(conn, args.set_email, args.email or "")
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            shown = updated["email"] or "(aucun)"
            print(f"Courriel : {updated['username']}  {shown}")
            return 0
        if args.set_password:
            password = args.password
            if not password:
                try:
                    password = _ask_password()
                except ValueError as exc:
                    print(str(exc), file=sys.stderr)
                    return 1
            try:
                updated = set_user_password(conn, args.set_password, password)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                f"Mot de passe mis à jour : {updated['username']} "
                f"(compte déverrouillé)"
            )
            return 0
        if args.unlock:
            try:
                unlocked = unlock_user(conn, args.unlock)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Déverrouillé : {unlocked['username']}")
            return 0
        if args.unlock_all:
            n = unlock_all_users(conn)
            print(f"{n} compte{'s' if n != 1 else ''} déverrouillé{'s' if n != 1 else ''}.")
            return 0
        if args.delete:
            name = (args.delete or "").strip()
            if not args.yes and not _confirm_delete(name):
                print("Annulé.")
                return 1
            try:
                deleted = delete_user_by_name(
                    conn, name, allow_last_admin=True
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"Supprimé : {deleted['username']}")
            remaining = list_users(conn)
            if not remaining:
                print("Plus aucun compte : le site est ouvert (pas de page de connexion).")
            elif not any(r["role"] == "admin" for r in remaining):
                print(
                    "Plus de compte admin. Recréez-en un : "
                    "--create IDENTIFIANT --role admin"
                )
            return 0
        _print_users(conn)
        return 0
    finally:
        conn.close()


def normalize_argv(argv: list[str]) -> list[str]:
    subs = {
        "serve",
        "index",
        "faces",
        "scenes",
        "users",
        "backup",
        "restore",
        "completer-lieux",
        "scan-gps",
    }
    if not argv:
        return ["serve"]
    if argv[0] in ("-h", "--help"):
        return argv
    portable = "--portable" in argv
    argv = [a for a in argv if a != "--portable"]
    prefix = ["--portable"] if portable else []
    if not argv:
        return prefix + ["serve"]
    if argv[0] in subs or any(a in subs for a in argv):
        return prefix + argv
    return prefix + ["serve"] + argv


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()
    args = parser.parse_args(argv)
    portable = bool(getattr(args, "portable", False))
    if portable:
        data_dir().mkdir(parents=True, exist_ok=True)
        library = library_from_settings(data_dir() / "Bibliotheque")
        library.mkdir(parents=True, exist_ok=True)
        cache = portable_cache_dir()
    else:
        library = args.library if args.library is not None else library_from_settings(DEFAULT_LIBRARY)
        cache = args.cache
    cache.mkdir(parents=True, exist_ok=True)
    ensure_heif()

    if args.cmd == "serve":
        import uvicorn

        from photo_library.app import create_app
        from photo_library.cast import preferred_lan_ipv4
        from photo_library.tls import (
            dns_names,
            ensure_tls,
            fingerprint_sha256,
            lan_urls,
            letsencrypt_pair,
        )

        extra = getattr(args, "tls_host", None) or []
        app = create_app(
            library,
            cache,
            portable=portable,
            https=True,
            gallery_port=args.port,
        )
        public = letsencrypt_pair(cache)
        if public is not None:
            tls_cert, tls_key = public
            print("Galerie :", flush=True)
            for name in dns_names(tls_cert):
                print(f"  https://{name}:{args.port}/", flush=True)
            print(f"Certificat : {tls_cert}", flush=True)
            print(f"Empreinte SHA-256 : {fingerprint_sha256(tls_cert)}", flush=True)
        else:
            tls = ensure_tls(cache, extra_hosts=extra)
            tls_cert, tls_key = tls.cert, tls.key
            print(f"Galerie : https://{args.host}:{args.port}/", flush=True)
            for url in lan_urls(args.port, extra):
                print(f"  {url}/", flush=True)
            print(f"Certificat maison : {tls.ca_cert}", flush=True)
            print(f"Empreinte SHA-256 : {fingerprint_sha256(tls.cert)}", flush=True)
            print(
                "Premier passage : continuer vers le site (c’est votre ordinateur).",
                flush=True,
            )
        tv_ip = preferred_lan_ipv4() or "127.0.0.1"
        print(
            f"TV (DLNA) : http://{tv_ip}:{CAST_HTTP_PORT}/  "
            "(LG / Samsung, même réseau — bouton TV dans la photo agrandie)",
            flush=True,
        )
        print(f"Bibliothèque : {library}", flush=True)
        if portable:
            print(f"Réglages : {data_dir() / 'config.json'}", flush=True)
        run_kw = {
            "host": args.host,
            "port": args.port,
            "log_level": "info",
            "ssl_certfile": str(tls_cert),
            "ssl_keyfile": str(tls_key),
        }
        uvicorn.run(app, **run_kw)
        return 0

    if args.cmd == "backup":
        from photo_library.backup import run_backup

        result = run_backup(library, cache, progress=_progress, dest_parent=args.dest)
        print(result)
        return 0

    if args.cmd == "restore":
        from photo_library.backup import SITE_ROOT, restore_backup

        result = restore_backup(
            args.folder,
            cache,
            restore_config=not args.no_config,
            restore_site_to=None if args.no_site else (args.site_dest or SITE_ROOT),
        )
        print(result)
        print("Redémarre le site ensuite (systemctl --user restart photo-library.service).")
        return 0

    if args.cmd == "users":
        return _run_users(args, cache)

    if not library.is_dir():
        print(f"Bibliothèque introuvable : {library}", file=sys.stderr)
        return 1

    conn = connect(cache)
    init_schema(conn, refresh_places=args.cmd != "completer-lieux")
    try:
        if args.cmd == "index":
            result = index_library(
                conn,
                library,
                cache,
                year=args.year,
                limit=args.limit,
                progress=_progress,
            )
            print(result)
            return 0
        if args.cmd == "scan-gps":
            from photo_library.gps import scan_media_gps

            result = scan_media_gps(
                conn,
                library,
                year=args.year,
                limit=args.limit,
                progress=_progress,
            )
            print(result)
            return 0
        if args.cmd == "faces":
            result = scan_faces(
                conn,
                library,
                cache,
                year=args.year,
                limit=args.limit,
                progress=_progress,
            )
            print(result)
            return 0
        if args.cmd == "scenes":
            from photo_library.scenes import scan_scenes

            result = scan_scenes(
                conn,
                library,
                cache,
                year=args.year,
                place=getattr(args, "place", None),
                limit=args.limit,
                progress=_progress,
            )
            print(result)
            return 0
        if args.cmd == "completer-lieux":
            from photo_library.places import complete_places_from_paths

            apply = bool(args.apply)
            if not apply:
                print("Simulation (ajoutez --apply pour écrire).", flush=True)
            missing = {"missing": 0, "indexed": 0, "samples_missing": []}
            if not args.no_index:
                missing = index_missing_files(
                    conn,
                    library,
                    cache,
                    apply=apply,
                    progress=_progress,
                )
            places = complete_places_from_paths(
                conn,
                apply=apply,
                upgrade_generic=not args.keep_generic,
            )
            from photo_library.places import complete_moments_from_paths

            moments = complete_moments_from_paths(conn, apply=apply)
            print(
                "fichiers_absents {missing} indexes {indexed} "
                "lieux_vides {filled} enveloppes {upgraded} "
                "enveloppes_vides {cleared} "
                "deja_nommes {skipped} verrouilles {locked} "
                "sans_dossier {no_guess} moments {moments}".format(
                    missing=missing.get("missing", 0),
                    indexed=missing.get("indexed", 0),
                    filled=places["filled"],
                    upgraded=places["upgraded"],
                    cleared=places.get("cleared", 0),
                    skipped=places["skipped"],
                    locked=places["locked"],
                    no_guess=places["no_guess"],
                    moments=moments.get("filled", 0),
                ),
                flush=True,
            )
            if places.get("by_place"):
                print("lieux :", places["by_place"], flush=True)
            for line in missing.get("samples_missing") or []:
                print("  absent :", line, flush=True)
            for line in places.get("samples_upgraded") or []:
                print("  enveloppe :", line, flush=True)
            for line in places.get("samples_cleared") or []:
                print("  titre voyage :", line, flush=True)
            for line in places.get("samples_filled") or []:
                print("  vide :", line, flush=True)
            for line in moments.get("samples") or []:
                print("  moment :", line, flush=True)
            if not apply:
                print("Rien n’a été écrit. Relancez avec --apply pour appliquer.", flush=True)
            return 0
    finally:
        conn.close()
    return 0
