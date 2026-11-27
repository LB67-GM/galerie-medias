from __future__ import annotations

import atexit
from contextlib import asynccontextmanager
import shutil
import threading
import time
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from photo_library.albums import (
    add_to_album,
    assign_media_albums,
    create_album,
    delete_album,
    list_albums,
    media_album_map,
    remove_from_album,
    remove_media_albums,
    set_favorite,
)
from photo_library.auth import (
    AccountLocked,
    AuthError,
    auth_enabled,
    clear_session_cookie,
    complete_password_reset,
    create_user,
    current_user_from_request,
    delete_user,
    deny,
    is_public_path,
    issue_reset_token,
    list_users,
    login_user,
    loopback_admin_allowed,
    session_secret,
    set_session_cookie,
    set_user_email_by_id,
    user_count,
    viewer_allowed,
)
from photo_library.mail import public_base, send_password_reset, smtp_configured
from photo_library.tls import paths_for as tls_paths_for
from photo_library.cast import (
    discover_renderers,
    is_private_http_url,
    make_token,
    media_http_base,
    resolve_cast_file,
    set_and_play,
    start_cast_http_server,
    stop_renderer,
)
from photo_library.config import CAST_HTTP_PORT, DEFAULT_PORT
from photo_library.backup import (
    KEEP_BACKUPS,
    backup_parent,
    list_backup_dirs,
    read_manifest,
    run_backup,
)
from photo_library.copies import (
    copy_groups,
    live_media_id_for_face,
    trash_extra_copies,
    unique_faces,
)
from photo_library.db import connect, init_schema, row_dict
from photo_library.delete_media import (
    KEEP_DAYS,
    expired_trash_count,
    list_trash,
    list_trash_ids,
    purge_expired,
    purge_selected,
    restore_selected,
    trash_count,
    trash_selected,
)
from photo_library.edit import apply_photo_edit
from photo_library.faces import (
    delete_person,
    faces_payload,
    merge_people,
    name_cluster,
    name_face,
    name_faces_many,
    people_for_filters,
    person_faces_payload,
    rename_person,
    scan_faces,
    scan_one_media,
    unname_faces_many,
)
from photo_library.geo import apply_folder_aliases, map_places, reverse_place, search_places
from photo_library.icloud_run import run_download as icloud_download, submit_mfa
from photo_library.jobs import JobRunner
from photo_library.locate import locate_library_file, locate_still_sibling, maybe_fix_relpath
from photo_library.move_media import move_selected, move_targets
from photo_library.place_groups import aliases_for, cluster_places
from photo_library.paths import is_moment_folder, is_month_folder, list_years
from photo_library.play import cached_play_path, ensure_play_mp4
from photo_library.places import set_media_places
from photo_library.scan import index_library
from photo_library.version import APP_VERSION
from photo_library.scenes import (
    add_scenes,
    media_for_scene,
    remove_scenes,
    scan_scenes,
    scene_catalog,
    scenes_for_filters,
    scenes_for_media,
    scenes_workspace,
    untagged_media,
)
from photo_library.user_config import (
    cinema_dir_status,
    load_settings,
    public_settings,
    save_settings,
)
from photo_library.cinema_meta import CATEGORIES, MEDIA_TYPES
from photo_library.cinema_optical import (
    inspect_configured_disc,
    inspect_optical_source,
    resolve_optical_title,
)
from photo_library.cinema_probe import extract_subtitle_vtt, probe_media
from photo_library.cinema_scan import (
    CINEMA_KEEP_DAYS,
    cinema_filters,
    cinema_poster_path,
    cinema_trash_count,
    clear_cinema_progress,
    continue_watching,
    enrich_cinema_library,
    get_cinema_item,
    list_cinema_items,
    list_cinema_trash,
    purge_cinema_item,
    restore_cinema_item,
    save_cinema_progress,
    scan_cinema_library,
    trash_cinema_item,
    update_cinema_metadata,
)
from photo_library.ffmpeg_util import ffmpeg_capabilities
from photo_library.hls_stream import HlsSessionManager
from photo_library.sort_job import run_classer
from photo_library.thumbs import make_preview, preview_file, thumb_file, face_thumb_file

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

PLACEHOLDER_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="360" height="240" viewBox="0 0 360 240">
  <rect fill="#3d3832" width="360" height="240"/>
  <text x="180" y="118" fill="#d7cfc4" font-size="16" font-family="system-ui,sans-serif" text-anchor="middle">{label}</text>
  <text x="180" y="142" fill="#9a9288" font-size="12" font-family="system-ui,sans-serif" text-anchor="middle">fichier illisible</text>
</svg>
"""


class IndexBody(BaseModel):
    year: int | None = None
    all: bool = False
    limit: int | None = Field(default=None, ge=1, le=50_000)


class FacesBody(BaseModel):
    year: int | None = None
    limit: int | None = Field(default=None, ge=1, le=50_000)


class ScenesBody(BaseModel):
    year: int | None = None
    place: str | None = None
    limit: int | None = Field(default=None, ge=1, le=50_000)


class LoginBody(BaseModel):
    username: str
    password: str


class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    email: str = ""


class UserEmailBody(BaseModel):
    email: str = ""


class ForgotBody(BaseModel):
    email: str = ""


class ResetBody(BaseModel):
    token: str = ""
    password: str = ""


def _raise_auth(exc: Exception, status: int) -> None:
    code = getattr(exc, "code", None)
    if not code:
        raise HTTPException(status, str(exc))
    payload: dict = {"code": code, "message": str(exc)}
    n = getattr(exc, "n", None)
    if n is not None:
        payload["n"] = n
    raise HTTPException(status, payload)


class ExportCopyBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    dest: str


class ExportZipBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=2000)


class DeleteMediaBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class MoveTargetsBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class MoveMediaBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    dest: str = Field(min_length=1, max_length=500)


class TrashActionBody(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=20000)
    all: bool = False


class ConfirmBody(BaseModel):
    confirm: bool = False


class EditPhotoBody(BaseModel):
    rotate: int = 0
    crop: dict | None = None


class AlbumBody(BaseModel):
    name: str = ""


class AlbumMediaBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)


class AssignAlbumsBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    album_ids: list[int] = Field(default_factory=list)
    create: str = ""
    replace: bool = False


class FavoriteBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    favorite: bool = True


class PlaceBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    place: str = ""
    apply_folder: bool = False
    lat: float | None = None
    lon: float | None = None
    cc: str = Field(default="", max_length=8)


class MergePeopleBody(BaseModel):
    keep_id: int
    absorb_id: int


class SettingsBody(BaseModel):
    phone_kind: str = "iphone"
    triage_dir: str = ""
    apple_id: str = ""
    apple_password: str = ""
    google_dir: str = ""
    facebook_dir: str = ""
    library_src: str = ""
    library_dest: str = ""
    backup_dir: str = ""
    smtp_host: str = ""
    smtp_port: str = "587"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: str = "1"
    public_url: str = ""
    cinema_dir: str = ""
    optical_device: str = ""


class CinemaMetadataBody(BaseModel):
    title: str | None = None
    media_type: str | None = None
    year: int | None = None
    clear_year: bool = False
    director: str | None = None
    overview: str | None = None
    categories: list[str] | None = None
    metadata_locked: bool = True


class CinemaEnrichBody(BaseModel):
    lang: str = "fr"
    only_missing: bool = True
    limit: int | None = Field(default=None, ge=1, le=5000)


class CinemaStreamStartBody(BaseModel):
    item_id: int | None = None
    disc: bool = False
    title_index: int | None = Field(default=None, ge=0, le=99999)
    start_s: float = Field(default=0.0, ge=0.0)
    audio_idx: int | None = Field(default=None, ge=0, le=64)
    quality: str = "auto"


class CastCinemaBody(BaseModel):
    control_url: str
    item_id: int


class CinemaProgressBody(BaseModel):
    item_id: int
    position_s: float = Field(default=0.0, ge=0.0)
    duration_s: float = Field(default=0.0, ge=0.0)
    title_index: int = Field(default=0, ge=0)
    audio_idx: int | None = None
    subtitle_idx: int | None = None


class CinemaClearProgressBody(BaseModel):
    item_id: int | None = None


class SortBody(BaseModel):
    apply: bool = False
    source: str = "triage"


class IcloudDownloadBody(BaseModel):
    year: int
    month: int | None = None
    apple_id: str = ""
    apple_password: str = ""
    triage_dir: str = ""


class MfaBody(BaseModel):
    code: str


class NameClusterBody(BaseModel):
    name: str


class FaceIdsNameBody(BaseModel):
    ids: list[int]
    name: str


class FaceIdsBody(BaseModel):
    ids: list[int]


class SceneIdsBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    tag: str


class CastPlayBody(BaseModel):
    control_url: str
    media_id: int


class CastStopBody(BaseModel):
    control_url: str


def _mime_for(path: Path, kind: str) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".3gp": "video/3gpp",
        ".mpg": "video/mpeg",
        ".mpeg": "video/mpeg",
        ".mpe": "video/mpeg",
        ".mts": "video/mp2t",
        ".m2ts": "video/mp2t",
        ".wmv": "video/x-ms-wmv",
    }.get(suffix, "video/mp4" if kind == "video" else "application/octet-stream")


def _unique_dest(folder: Path, name: str) -> Path:
    dest = folder / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while True:
        candidate = folder / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def year_match_clause(prefix: str = "m.") -> str:
    """Année du dossier ou année EXIF/fichier (les filtres se combinent en ET)."""
    return (
        f"({prefix}year=? OR CAST(substr({prefix}taken_at, 1, 4) AS INTEGER)=?)"
    )


# Noms de dossiers « Janvier 2006 » (sort_annee_mois). LIKE sans ESCAPE : noms fixes.
MONTH_FOLDER_SPELLINGS: dict[int, tuple[str, ...]] = {
    1: ("Janvier",),
    2: ("Février", "Fevrier"),
    3: ("Mars",),
    4: ("Avril",),
    5: ("Mai",),
    6: ("Juin",),
    7: ("Juillet",),
    8: ("Août", "Aout"),
    9: ("Septembre",),
    10: ("Octobre",),
    11: ("Novembre",),
    12: ("Décembre", "Decembre"),
}


def _relpath_fwd(prefix: str) -> str:
    return f"replace({prefix}relpath, char(92), '/')"


def month_match_clause(
    prefix: str, month: int, year: int | None
) -> tuple[str, list]:
    """Mois EXIF (taken_at) ou dossier « Mois AAAA » dans le chemin."""
    month = int(month)
    if month < 1 or month > 12:
        raise ValueError("mois invalide")
    mm = f"{month:02d}"
    rel = _relpath_fwd(prefix)
    likes: list[str] = []
    params: list = [mm]
    for name in MONTH_FOLDER_SPELLINGS[month]:
        folder = f"{name} {int(year)}" if year is not None else f"{name} %"
        likes.append(f"{rel} LIKE ?")
        params.append(f"%/{folder}/%")
        likes.append(f"{rel} LIKE ?")
        params.append(f"{folder}/%")
    clause = f"(substr({prefix}taken_at, 6, 2)=? OR {' OR '.join(likes)})"
    return clause, params


def _like_escape(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _fold_search(q: str) -> str:
    """Rome ≠ Andromède : recherche par mot entier, pas par sous-chaîne."""
    t = unicodedata.normalize("NFKD", q or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    for ch in "-_/.'":
        t = t.replace(ch, " ")
    return " ".join(t.lower().split())


# Accents seulement sur les prénoms (table petite). LIKE est déjà insensible
# à la casse ASCII : « rome » trouve Rome.
_SQL_NAME_ACCENTS = (
    ("à", "a"),
    ("â", "a"),
    ("ä", "a"),
    ("é", "e"),
    ("è", "e"),
    ("ê", "e"),
    ("ë", "e"),
    ("î", "i"),
    ("ï", "i"),
    ("ô", "o"),
    ("ö", "o"),
    ("ù", "u"),
    ("û", "u"),
    ("ü", "u"),
    ("ç", "c"),
    ("À", "a"),
    ("Â", "a"),
    ("Ä", "a"),
    ("É", "e"),
    ("È", "e"),
    ("Ê", "e"),
    ("Ë", "e"),
    ("Î", "i"),
    ("Ï", "i"),
    ("Ô", "o"),
    ("Ö", "o"),
    ("Ù", "u"),
    ("Û", "u"),
    ("Ü", "u"),
    ("Ç", "c"),
    ("œ", "oe"),
    ("Œ", "oe"),
)


def _sql_tokens(expr: str) -> str:
    e = f"replace({expr}, char(92), '/')"
    e = f"replace({e}, '-', ' ')"
    e = f"replace({e}, '_', ' ')"
    e = f"replace({e}, '/', ' ')"
    e = f"replace({e}, '.', ' ')"
    return f"replace({e}, char(39), ' ')"


def _sql_fold_name(expr: str) -> str:
    e = _sql_tokens(expr)
    for src, dst in _SQL_NAME_ACCENTS:
        e = f"replace({e}, '{src}', '{dst}')"
    return e


def _word_like(spaced_expr: str) -> str:
    return f"(' ' || {spaced_expr} || ' ') LIKE ? ESCAPE '\\'"


def search_match_clause(prefix: str, q: str) -> tuple[str, list]:
    """Fichier, lieu, moment, ou prénom : mot entier (Rome ≠ Andromède)."""
    folded = _fold_search(q)
    if not folded:
        return "1=1", []
    word_pat = f"% {_like_escape(folded)} %"
    prefix_pat = f"{_like_escape(folded)}%"
    rel = _relpath_fwd(prefix)
    place_expr = _sql_tokens(f"IFNULL({prefix}place, '')")
    moment_expr = _sql_tokens(f"IFNULL({prefix}moment, '')")
    folded_name = _sql_fold_name("psq.name")
    sql = (
        f"({_word_like(_sql_tokens(rel))} "
        f"OR {_word_like(place_expr)} "
        f"OR {_word_like(moment_expr)} "
        f"OR EXISTS (SELECT 1 FROM faces fsq JOIN people psq ON psq.id = fsq.person_id "
        f"WHERE fsq.media_id = {prefix}id AND ("
        f"{_word_like(folded_name)} "
        f"OR {folded_name} LIKE ? ESCAPE '\\')))"
    )
    return sql, [word_pat, word_pat, word_pat, word_pat, prefix_pat]


def media_from_where(
    *,
    year: int | None,
    place: str | None,
    kind: str | None,
    person_id: int | None,
    q: str | None,
    place_aliases: list[str] | None = None,
    album_id: int | None = None,
    favorite: bool = False,
    scene: str | None = None,
    scene_kind: str | None = None,
    month: int | None = None,
    moment: str | None = None,
) -> tuple[str, str, list]:
    """FROM + WHERE pour la galerie. Filtre personne : join sur faces, pas EXISTS."""
    params: list = []
    from_sql = "media AS m"
    if person_id is not None:
        pid = int(person_id)
        from_sql = (
            "media AS m JOIN ("
            "SELECT DISTINCT media_id FROM faces WHERE person_id=? "
            "UNION "
            "SELECT v.id FROM media AS v "
            "WHERE v.kind='video' AND v.present=1 "
            "AND v.pair_key IS NOT NULL AND v.pair_key != '' "
            "AND v.pair_key IN ("
            "SELECT p.pair_key FROM media AS p "
            "JOIN faces AS f ON f.media_id = p.id AND f.person_id=? "
            "WHERE p.kind='photo' AND p.present=1 "
            "AND p.pair_key IS NOT NULL AND p.pair_key != ''"
            ")"
            ") AS fp ON fp.media_id = m.id"
        )
        params.extend([pid, pid])
    if album_id is not None:
        from_sql += (
            " JOIN album_media AS am ON am.media_id = m.id AND am.album_id=?"
        )
        params.append(int(album_id))
    where = ["m.present=1"]
    if favorite:
        where.append("m.favorite=1")
    if year is not None:
        where.append(year_match_clause("m."))
        params.extend([year, year])
    if place == "__none__":
        where.append("(m.place IS NULL OR m.place='')")
    if moment == "__none__":
        where.append("(m.moment IS NULL OR m.moment='')")
    elif moment:
        where.append("m.moment=?")
        params.append(moment)
    if kind in {"photo", "video"}:
        where.append("m.kind=?")
        params.append(kind)
    if month is not None:
        mclause, mparams = month_match_clause("m.", int(month), year)
        where.append(mclause)
        params.extend(mparams)
    qn = (q or "").strip()[:80]
    if qn:
        sclause, sparams = search_match_clause("m.", qn)
        if sparams:
            where.append(sclause)
            params.extend(sparams)
    if place_aliases:
        placeholders = ",".join("?" * len(place_aliases))
        where.append(f"m.place IN ({placeholders})")
        params.extend(place_aliases)
    if scene:
        where.append("m.id IN (SELECT media_id FROM media_scenes WHERE tag=?)")
        params.append(scene)
    if scene_kind in {"landscape", "building"}:
        where.append("m.id IN (SELECT media_id FROM media_scenes WHERE kind=?)")
        params.append(scene_kind)
    return from_sql, " AND ".join(where), params


# Année du dossier d’abord : l’EXIF d’anciens APN est parfois fantaisiste (ex. 2029).
GALLERY_ORDER_SQL = (
    "COALESCE(m.year, CAST(substr(m.taken_at, 1, 4) AS INTEGER), 0) DESC, "
    "m.taken_at DESC, m.id DESC"
)


def create_app(
    library: Path,
    cache: Path,
    *,
    portable: bool = False,
    https: bool = False,
    gallery_port: int = DEFAULT_PORT,
    cast_http_port: int = CAST_HTTP_PORT,
) -> FastAPI:
    library = library.resolve()
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "exports").mkdir(parents=True, exist_ok=True)

    conn0 = connect(cache)
    init_schema(conn0)
    conn0.close()
    secret = session_secret(cache)

    jobs = JobRunner()
    expire_lock = threading.Lock()
    expire_state = {"last": 0.0}
    EXPIRE_EVERY_SEC = 3600

    def _trash_expire_busy() -> bool:
        snap = jobs.snapshot()
        if not snap:
            return False
        if snap.get("kind") == "trash-expire" and snap.get("status") in (
            "running",
            "queued",
        ):
            return True
        return any(
            q.get("kind") == "trash-expire" for q in (snap.get("queued") or [])
        )

    def _kick_trash_expire(force: bool = False) -> dict | None:
        with expire_lock:
            now = time.monotonic()
            if not force and now - expire_state["last"] < EXPIRE_EVERY_SEC:
                return None
            if _trash_expire_busy():
                return None
            conn = connect(cache)
            try:
                n = expired_trash_count(conn)
            finally:
                conn.close()
            expire_state["last"] = now
            if n == 0:
                return {"deleted": 0, "ids": [], "errors": []}

            def run(progress):
                conn = connect(cache)
                try:
                    return purge_expired(conn, library, cache, progress=progress)
                finally:
                    conn.close()

            return jobs.start("trash-expire", run)

    hls = HlsSessionManager(cache)
    atexit.register(hls.stop_all)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            hls.stop_all()

    app = FastAPI(title="Photo library", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.library = library
    app.state.cache = cache
    app.state.jobs = jobs
    app.state.hls = hls
    app.state.https = https
    app.state.gallery_port = gallery_port
    app.state.cast_http_port = cast_http_port
    if https:
        try:
            start_cast_http_server(
                host="0.0.0.0",
                port=cast_http_port,
                resolve=lambda token: resolve_cast_file(library, cache, secret, token),
            )
        except OSError as exc:
            print(f"Port TV {cast_http_port} indisponible : {exc}", flush=True)

    @app.middleware("http")
    async def auth_gate(request: Request, call_next):
        path = request.url.path
        method = request.method
        if is_public_path(path, method):
            return await call_next(request)
        conn = connect(cache)
        try:
            enabled = auth_enabled(conn)
            user = current_user_from_request(request, conn, secret) if enabled else None
        finally:
            conn.close()
        request.state.auth_enabled = enabled
        request.state.user = user
        if not enabled:
            return await call_next(request)
        if user is None:
            if loopback_admin_allowed(request):
                return await call_next(request)
            return deny(401, "connexion requise")
        if user["role"] == "viewer" and not viewer_allowed(path, method):
            return deny(403, "lecture seule : galerie et filtres uniquement")
        return await call_next(request)

    def media_or_404(conn, media_id: int, *, require_file: bool = True, require_present: bool = True):
        sql = "SELECT * FROM media WHERE id=?"
        if require_present:
            sql += " AND present=1"
        row = conn.execute(sql, (media_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "média introuvable")
        path = locate_library_file(library, row["relpath"])
        if path is not None:
            maybe_fix_relpath(conn, library, row, path)
            refreshed = conn.execute(
                "SELECT * FROM media WHERE id=?", (media_id,)
            ).fetchone()
            return refreshed or row, path
        if require_file:
            raise HTTPException(404, "fichier absent du NAS")
        return row, None

    @app.get("/", response_class=HTMLResponse)
    def home():
        html = STATIC / "index.html"
        if not html.is_file():
            raise HTTPException(500, "interface manquante")
        return HTMLResponse(
            html.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/favicon.ico")
    def favicon():
        ico = STATIC / "favicon.ico"
        if not ico.is_file():
            raise HTTPException(404, "favicon manquant")
        return FileResponse(ico, media_type="image/x-icon", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/manifest.json")
    def manifest():
        f = STATIC / "manifest.json"
        if not f.is_file():
            raise HTTPException(404, "manifest manquant")
        return FileResponse(f, media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/sw.js")
    def service_worker():
        f = STATIC / "sw.js"
        if not f.is_file():
            raise HTTPException(404, "service worker manquant")
        return FileResponse(f, media_type="application/javascript", headers={"Cache-Control": "no-cache"})

    def _auth_snapshot(request: Request, conn):
        enabled = auth_enabled(conn)
        me = current_user_from_request(request, conn, secret) if enabled else None
        return enabled, me

    def _is_admin(enabled: bool, user: dict | None) -> bool:
        if not enabled:
            return True
        return bool(user and user.get("role") == "admin")

    @app.get("/galerie-ca.pem")
    def galerie_ca():
        ca = tls_paths_for(cache).ca_cert
        if not ca.is_file():
            raise HTTPException(404, "certificat maison absent")
        return FileResponse(
            ca,
            media_type="application/x-pem-file",
            filename="galerie-ca.pem",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/health")
    def health(request: Request):
        conn = connect(cache)
        try:
            enabled, me = _auth_snapshot(request, conn)
        finally:
            conn.close()
        return {"ok": True, "version": APP_VERSION, "auth": {"enabled": enabled, "user": me}}

    def _cast_base() -> str:
        return media_http_base(
            https=https,
            gallery_port=gallery_port,
            cast_port=cast_http_port,
        )

    @app.get("/api/cast/devices")
    def cast_devices():
        devices = discover_renderers()
        return {
            "devices": devices,
            "http_base": _cast_base(),
            "hint": (
                "Aucune télévision ? Allumée, Wi-Fi maison (pas l’invité). "
                "La Samsung apparaît sous le nom donné dans ses paramètres "
                "(pas Smart View). Réessayez Chercher."
            ),
        }

    @app.get("/api/cast/file/{token}")
    def cast_file(token: str):
        try:
            path, mime = resolve_cast_file(library, cache, secret, token)
        except ValueError as exc:
            raise HTTPException(403, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return FileResponse(path, media_type=mime)

    @app.post("/api/cast/play")
    def cast_play(body: CastPlayBody):
        if not is_private_http_url(body.control_url):
            raise HTTPException(400, "adresse TV refusée")
        conn = connect(cache)
        try:
            row, path = media_or_404(conn, body.media_id)
        finally:
            conn.close()
        kind = row["kind"]
        title = Path(row["relpath"]).name
        variant = "preview"
        mime = "image/jpeg"
        note = None
        if kind == "video":
            dest = cached_play_path(
                cache, body.media_id, int(row["size"] or 0), int(row["mtime_ns"] or 0)
            )
            try:
                ensure_play_mp4(path, dest)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            variant = "play"
            mime = "video/mp4"
        prev = preview_file(cache, body.media_id)
        if variant == "preview" and not prev.is_file() and path.is_file():
            try:
                make_preview(path, prev, kind)
            except Exception as exc:
                raise HTTPException(404, "aperçu impossible pour la TV") from exc
        token = make_token(secret, body.media_id, variant)
        uri = f"{_cast_base()}/api/cast/file/{token}"
        try:
            set_and_play(
                body.control_url,
                uri,
                title,
                mime,
                video=variant == "play",
            )
        except Exception as exc:
            raise HTTPException(
                502,
                "La télévision n’affiche pas le média (port 8766). "
                "Windows : autoriser-parefeu.bat. Mac : autoriser-parefeu-mac.command. "
                "Linux : ouvrez le port 8766 sur le réseau local.",
            ) from exc
        return {"ok": True, "name": title, "note": note}

    @app.post("/api/cast/stop")
    def cast_stop(body: CastStopBody):
        if not is_private_http_url(body.control_url):
            raise HTTPException(400, "adresse TV refusée")
        try:
            stop_renderer(body.control_url)
        except Exception:
            return {"ok": True, "note": "TV oubliée (éteinte ou occupée)."}
        return {"ok": True}

    @app.post("/api/cast/cinema")
    def cast_cinema(body: CastCinemaBody):
        if not is_private_http_url(body.control_url):
            raise HTTPException(400, "adresse TV refusée")
        conn = connect(cache)
        try:
            item, fpath = _cinema_item_path(conn, body.item_id)
        finally:
            conn.close()
        if item["source_type"] != "file":
            raise HTTPException(
                422,
                "Envoi DLNA direct réservé aux fichiers vidéo (utilisez le navigateur pour DVD/Blu-ray).",
            )
        dest = (
            cache
            / "cinema_cast"
            / f"{body.item_id}-{int(item.get('size') or 0)}-{int(item.get('mtime_ns') or 0)}.mp4"
        )
        try:
            ensure_play_mp4(fpath, dest)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        token = make_token(secret, body.item_id, "cinema")
        uri = f"{_cast_base()}/api/cast/file/{token}"
        title = str(item.get("title") or fpath.name)
        try:
            set_and_play(body.control_url, uri, title, "video/mp4", video=True)
        except Exception as exc:
            raise HTTPException(
                502,
                "La télévision n’affiche pas la vidéo (port 8766).",
            ) from exc
        return {"ok": True, "name": title}

    @app.get("/api/status")
    def status(request: Request):
        conn = connect(cache)
        try:
            enabled, me = _auth_snapshot(request, conn)
            count = conn.execute(
                "SELECT COUNT(*) FROM media WHERE present=1"
            ).fetchone()[0]
            payload = {
                "ok": True,
                "version": APP_VERSION,
                "library_ok": library.is_dir(),
                "media": count,
                "portable": portable,
                "auth": {"enabled": enabled, "user": me},
            }
            if _is_admin(enabled, me):
                _kick_trash_expire()
                trash_n = trash_count(conn) + cinema_trash_count(conn)
                tagged = conn.execute(
                    "SELECT COUNT(DISTINCT media_id) FROM media_scenes"
                ).fetchone()[0]
                payload.update(
                    {
                        "library": str(library),
                        "trash": trash_n,
                        "job": jobs.snapshot(),
                        "needs_setup": portable
                        and not bool(load_settings().get("library_dest")),
                        "scenes_tagged": tagged,
                    }
                )
        finally:
            conn.close()
        return payload

    @app.get("/api/auth/status")
    def auth_status(request: Request):
        conn = connect(cache)
        try:
            enabled = auth_enabled(conn)
            me = current_user_from_request(request, conn, secret) if enabled else None
        finally:
            conn.close()
        return {"enabled": enabled, "user": me}

    @app.post("/api/auth/login")
    def auth_login(body: LoginBody):
        conn = connect(cache)
        try:
            if not auth_enabled(conn):
                raise HTTPException(400, "Aucun compte : le site est ouvert (comportement actuel).")
            try:
                user = login_user(conn, body.username, body.password)
            except AccountLocked as exc:
                _raise_auth(exc, 423)
            except AuthError as exc:
                _raise_auth(exc, 401)
            except PermissionError as exc:
                raise HTTPException(423, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(401, str(exc)) from exc
        finally:
            conn.close()
        public = {key: user[key] for key in ("id", "username", "role")}
        resp = JSONResponse({"ok": True, "user": public})
        set_session_cookie(resp, user, secret, secure=https)
        return resp

    @app.post("/api/auth/forgot")
    def auth_forgot(body: ForgotBody, request: Request):
        settings = load_settings()
        if not smtp_configured(settings):
            _raise_auth(
                AuthError(
                    "mail_off",
                    "Le courriel n’est pas configuré. Un administrateur l’ajoute dans Paramètres, section Courriel.",
                ),
                503,
            )
        conn = connect(cache)
        try:
            token = issue_reset_token(conn, body.email)
        finally:
            conn.close()
        if token:
            link = f"{public_base(settings, str(request.base_url))}/?reset={token}"
            try:
                send_password_reset(settings, body.email.strip().lower(), link)
            except Exception:
                _raise_auth(
                    AuthError(
                        "mail_failed",
                        "Le message n’a pas pu être envoyé. Vérifiez le serveur courriel dans Paramètres.",
                    ),
                    502,
                )
        return {"ok": True}

    @app.post("/api/auth/reset")
    def auth_reset(body: ResetBody):
        conn = connect(cache)
        try:
            try:
                complete_password_reset(conn, body.token, body.password)
            except AuthError as exc:
                _raise_auth(exc, 400)
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/api/auth/logout")
    def auth_logout():
        resp = JSONResponse({"ok": True})
        clear_session_cookie(resp)
        return resp

    @app.get("/api/auth/me")
    def auth_me(request: Request):
        conn = connect(cache)
        try:
            enabled = auth_enabled(conn)
            me = current_user_from_request(request, conn, secret) if enabled else None
        finally:
            conn.close()
        return {"enabled": enabled, "user": me}

    @app.get("/api/users")
    def users_list():
        conn = connect(cache)
        try:
            return {"users": list_users(conn), "enabled": auth_enabled(conn)}
        finally:
            conn.close()

    @app.post("/api/users")
    def users_create(body: CreateUserBody):
        conn = connect(cache)
        try:
            first = user_count(conn) == 0
            try:
                if not (body.email or "").strip():
                    raise AuthError(
                        "email_required",
                        "Indiquez le courriel de cette personne. C’est l’adresse qui recevra le lien.",
                    )
                user = create_user(
                    conn, body.username, body.password, body.role, body.email
                )
            except AuthError as exc:
                _raise_auth(exc, 400)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            public = {key: user[key] for key in ("id", "username", "role", "email")}
            payload = {"user": public, "enabled": True, "first": first}
            resp = JSONResponse(payload)
            if first:
                set_session_cookie(resp, user, secret, secure=https)
            return resp
        finally:
            conn.close()

    @app.post("/api/users/{user_id}/email")
    def users_email(user_id: int, body: UserEmailBody):
        conn = connect(cache)
        try:
            try:
                return set_user_email_by_id(conn, user_id, body.email)
            except AuthError as exc:
                _raise_auth(exc, 400)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.delete("/api/users/{user_id}")
    def users_delete(user_id: int):
        conn = connect(cache)
        try:
            try:
                return delete_user(conn, user_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/settings")
    def get_settings():
        return public_settings(library)

    @app.post("/api/settings")
    def post_settings(body: SettingsBody):
        before = public_settings(library)
        saved = save_settings(body.model_dump(), keep_password=not body.apple_password)
        dest = saved["library_dest"] or saved["library_src"]
        if dest:
            Path(dest).expanduser().mkdir(parents=True, exist_ok=True)
        if saved["triage_dir"]:
            Path(saved["triage_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        if saved["google_dir"]:
            Path(saved["google_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        if saved.get("facebook_dir"):
            Path(saved["facebook_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        if saved.get("cinema_dir"):
            cinema_dir_status(saved["cinema_dir"], create_local=True)
        after = public_settings(library)
        lib_changed = (
            before["library_src"] != after["library_src"]
            or before["library_dest"] != after["library_dest"]
        )
        if lib_changed:
            message = (
                "Tous les réglages sont enregistrés. Relancez l’application "
                "pour que la galerie utilise le nouvel emplacement."
            )
            code = "settings.savedLib"
        else:
            message = (
                "Tous les réglages sont enregistrés "
                "(téléphone, iCloud, Google, Facebook, classement, sauvegarde)."
            )
            code = "settings.savedAll"
        return {
            **after,
            "restart_needed": lib_changed,
            "message": message,
            "message_code": code,
        }

    @app.get("/api/backups")
    def get_backups():
        parent = backup_parent(library)
        items = []
        for folder in list_backup_dirs(parent)[:12]:
            info = read_manifest(folder)
            items.append(
                {
                    "name": folder.name,
                    "path": str(folder),
                    "created_at": info.get("created_at"),
                    "media_count": info.get("media_count"),
                }
            )
        return {
            "backup_dir": str(parent),
            "keep": KEEP_BACKUPS,
            "backups": items,
        }

    @app.post("/api/backup")
    def start_backup():
        def work(progress):
            return run_backup(library, cache, progress=progress)

        return jobs.start("backup", work)

    @app.post("/api/icloud/download")
    def start_icloud(body: IcloudDownloadBody):
        year = body.year
        month = body.month
        patch = {}
        if body.apple_id.strip():
            patch["apple_id"] = body.apple_id.strip()
        if body.triage_dir.strip():
            patch["triage_dir"] = body.triage_dir.strip()
        if body.apple_password:
            patch["apple_password"] = body.apple_password
        if patch:
            save_settings(patch, keep_password=not body.apple_password)
            triage = (patch.get("triage_dir") or "").strip()
            if triage:
                Path(triage).expanduser().mkdir(parents=True, exist_ok=True)

        def run(progress):
            return icloud_download(year, month, progress, patch=jobs.patch)

        return jobs.start("icloud", run)

    @app.post("/api/icloud/mfa")
    def send_icloud_mfa(body: MfaBody):
        try:
            submit_mfa(body.code)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        jobs.patch(
            mfa_needed=False,
            message="Code envoyé, authentification…",
            message_code="prog.mfaSent",
            message_vars={},
        )
        return {"ok": True}

    @app.post("/api/sort")
    def start_sort(body: SortBody):
        apply = bool(body.apply)
        source = (body.source or "triage").strip().lower()
        if source not in {"triage", "library", "year-month"}:
            source = "triage"

        def run(progress):
            return run_classer(apply, progress, source=source)

        return jobs.start("sort", run)

    @app.get("/api/job")
    def job_status():
        return {"job": jobs.snapshot()}

    def place_mapping(conn, year: int | None = None) -> dict[str, str]:
        sql = """
            SELECT place, COUNT(*) AS c FROM media
            WHERE present=1 AND place IS NOT NULL AND place != ''
        """
        params: list = []
        if year is not None:
            sql += f" AND {year_match_clause('')}"
            params.extend([year, year])
        sql += " GROUP BY place"
        rows = conn.execute(sql, params).fetchall()
        names = [
            r["place"]
            for r in rows
            if (
                r["place"]
                and not is_month_folder(r["place"])
                and not is_moment_folder(r["place"])
            )
        ]
        counts = {r["place"]: int(r["c"]) for r in rows if r["place"] in set(names)}
        from photo_library.places import user_alias_map, user_coord_map

        return apply_folder_aliases(
            cluster_places(names, counts),
            names,
            counts,
            extra=user_alias_map(conn),
            skip_keys=set(user_coord_map(conn).keys()),
        )

    @app.get("/api/library/years")
    def library_years():
        return {"years": list_years(library)}

    @app.get("/api/filters")
    def filters(year: int | None = None):
        conn = connect(cache)
        try:
            years = [
                int(r[0])
                for r in conn.execute(
                    "SELECT DISTINCT year FROM media WHERE present=1 AND year IS NOT NULL ORDER BY year DESC"
                )
            ]
            mapping = place_mapping(conn, year)
            places = sorted(set(mapping.values()), key=str.casefold)
            moment_sql = """
                SELECT DISTINCT moment FROM media
                WHERE present=1 AND moment IS NOT NULL AND moment != ''
            """
            moment_params: list = []
            if year is not None:
                moment_sql += f" AND {year_match_clause('')}"
                moment_params.extend([year, year])
            moment_sql += " ORDER BY moment COLLATE NOCASE"
            moments = [r[0] for r in conn.execute(moment_sql, moment_params)]
            kinds = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT kind FROM media WHERE present=1 ORDER BY kind"
                )
            ]
            people = people_for_filters(conn)
            albums = list_albums(conn)
            scenes = scenes_for_filters(conn)
        finally:
            conn.close()
        return {
            "years": years,
            "places": places,
            "moments": moments,
            "kinds": kinds,
            "people": people,
            "albums": albums,
            "scenes": scenes,
            "scene_catalog": scene_catalog(),
        }

    @app.get("/api/media")
    def list_media(
        year: int | None = None,
        month: int | None = Query(None, ge=1, le=12),
        place: str | None = None,
        moment: str | None = None,
        kind: str | None = None,
        person_id: int | None = None,
        q: str | None = None,
        album_id: int | None = None,
        favorite: bool = False,
        scene: str | None = None,
        scene_kind: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(80, ge=1, le=400),
    ):
        conn = connect(cache)
        try:
            aliases: list[str] | None = None
            if place and place != "__none__":
                aliases = aliases_for(place, place_mapping(conn, year))
            from_sql, clause, params = media_from_where(
                year=year,
                month=month,
                place=place,
                moment=moment,
                kind=kind,
                person_id=person_id,
                q=q,
                place_aliases=aliases,
                album_id=album_id,
                favorite=favorite,
                scene=scene,
                scene_kind=scene_kind,
            )
            total = conn.execute(
                f"SELECT COUNT(*) FROM {from_sql} WHERE {clause}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT m.id, m.relpath, m.kind, m.year, m.place, m.moment, m.taken_at, m.size, m.mtime_ns, m.thumb_ok, m.favorite
                FROM {from_sql}
                WHERE {clause}
                ORDER BY {GALLERY_ORDER_SQL}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            items = []
            id_list = [int(row["id"]) for row in rows]
            albums_by_media = media_album_map(conn, id_list)
            scenes_by_media: dict[int, list] = {}
            if id_list:
                qmarks = ",".join("?" * len(id_list))
                for r in conn.execute(
                    f"SELECT media_id, tag, kind, score FROM media_scenes WHERE media_id IN ({qmarks})",
                    id_list,
                ):
                    mid = int(r["media_id"])
                    scenes_by_media.setdefault(mid, []).append(
                        {
                            "tag": r["tag"],
                            "kind": r["kind"],
                            "label": r["tag"],
                            "score": r["score"],
                        }
                    )
            from photo_library.scenes import SCENE_LABEL

            for row in rows:
                item = dict(row)
                item["name"] = Path(row["relpath"]).name
                item["album_ids"] = albums_by_media.get(int(row["id"]), [])
                item["favorite"] = bool(row["favorite"]) or bool(item["album_ids"])
                scenes = scenes_by_media.get(int(row["id"]), [])
                for s in scenes:
                    s["label"] = SCENE_LABEL.get(s["tag"], s["tag"])
                item["scenes"] = scenes
                items.append(item)
        finally:
            conn.close()
        return {"total": total, "offset": offset, "limit": limit, "items": items}

    @app.get("/api/media/ids")
    def list_ids(
        year: int | None = None,
        month: int | None = Query(None, ge=1, le=12),
        place: str | None = None,
        moment: str | None = None,
        kind: str | None = None,
        person_id: int | None = None,
        q: str | None = None,
        album_id: int | None = None,
        favorite: bool = False,
        scene: str | None = None,
        scene_kind: str | None = None,
        limit: int = Query(2000, ge=1, le=5000),
    ):
        data = list_media(
            year=year,
            month=month,
            place=place,
            moment=moment,
            kind=kind,
            person_id=person_id,
            q=q,
            album_id=album_id,
            favorite=favorite,
            scene=scene,
            scene_kind=scene_kind,
            offset=0,
            limit=limit,
        )
        return {"ids": [item["id"] for item in data["items"]], "total": data["total"]}

    @app.get("/api/media/copies")
    def list_copies(
        limit: int = Query(12, ge=1, le=50),
        offset: int = Query(0, ge=0),
    ):
        conn = connect(cache)
        try:
            return copy_groups(conn, limit=limit, offset=offset)
        finally:
            conn.close()

    @app.post("/api/media/copies/trash-extras")
    def trash_copy_extras(body: ConfirmBody):
        if not body.confirm:
            raise HTTPException(400, "confirmation requise")

        def run(progress):
            conn = connect(cache)
            try:
                return trash_extra_copies(conn, library, cache, progress=progress)
            finally:
                conn.close()

        return jobs.start("copies-trash", run)

    @app.get("/api/media/{media_id}")
    def media_detail(media_id: int):
        conn = connect(cache)
        try:
            row, path = media_or_404(conn, media_id)
            people = [
                {"id": int(r["id"]), "name": r["name"]}
                for r in conn.execute(
                    """
                    SELECT DISTINCT p.id, p.name
                    FROM faces f JOIN people p ON p.id = f.person_id
                    WHERE f.media_id=?
                    ORDER BY p.name COLLATE NOCASE
                    """,
                    (media_id,),
                )
            ]
            faces = [
                {
                    "id": int(r["id"]),
                    "x": r["x"],
                    "y": r["y"],
                    "w": r["w"],
                    "h": r["h"],
                    "score": r["score"],
                    "person_id": r["person_id"],
                    "name": r["person_name"],
                }
                for r in conn.execute(
                    """
                    SELECT f.id, f.x, f.y, f.w, f.h, f.score, f.person_id,
                           p.name AS person_name
                    FROM faces f
                    LEFT JOIN people p ON p.id = f.person_id
                    WHERE f.media_id=?
                    ORDER BY f.score DESC, f.id
                    """,
                    (media_id,),
                )
            ]
            album_ids = media_album_map(conn, [media_id]).get(media_id, [])
            scenes = scenes_for_media(conn, media_id)
        finally:
            conn.close()
        item = row_dict(row)
        assert item is not None
        item["name"] = path.name
        item["people"] = people
        item["faces"] = faces
        item["album_ids"] = album_ids
        item["favorite"] = bool(item.get("favorite")) or bool(album_ids)
        item["scenes"] = scenes
        return item

    @app.get("/api/media/{media_id}/faces")
    def media_faces(media_id: int):
        conn = connect(cache)
        try:
            row = conn.execute(
                "SELECT id, face_scanned, relpath FROM media WHERE id=? AND present=1",
                (media_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "média introuvable")
            path = locate_library_file(library, row["relpath"])
            if path is not None:
                maybe_fix_relpath(conn, library, row, path)
            return {
                "face_scanned": int(row["face_scanned"] or 0),
                "faces": faces_payload(conn, media_id),
                "file_ok": path is not None,
            }
        finally:
            conn.close()

    @app.post("/api/media/{media_id}/faces/scan")
    def scan_media_faces(media_id: int):
        conn = connect(cache)
        try:
            try:
                return scan_one_media(conn, library, cache, media_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/media/{media_id}/thumb")
    def media_thumb(media_id: int):
        conn = connect(cache)
        try:
            row, _path = media_or_404(conn, media_id, require_file=False, require_present=False)
        finally:
            conn.close()
        dest = thumb_file(cache, media_id)
        if dest.is_file():
            return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        svg = PLACEHOLDER_SVG.format(label="vidéo" if row["kind"] == "video" else "photo")
        return Response(svg, media_type="image/svg+xml")

    @app.get("/api/media/{media_id}/preview")
    def media_preview(media_id: int):
        conn = connect(cache)
        try:
            row, path = media_or_404(conn, media_id, require_file=False, require_present=False)
        finally:
            conn.close()
        dest = preview_file(cache, media_id)
        if dest.is_file():
            return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        if path is not None and path.is_file():
            try:
                make_preview(path, dest, row["kind"])
                return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
            except Exception:
                pass
        thumb = thumb_file(cache, media_id)
        if thumb.is_file():
            return FileResponse(thumb, media_type="image/jpeg")
        sibling = locate_still_sibling(library, row["relpath"])
        if sibling is not None:
            try:
                make_preview(sibling, dest, "photo")
                return FileResponse(dest, media_type="image/jpeg")
            except Exception:
                pass
        raise HTTPException(404, "aperçu impossible")

    @app.get("/api/media/{media_id}/file")
    def media_file(media_id: int):
        conn = connect(cache)
        try:
            row, path = media_or_404(conn, media_id)
        finally:
            conn.close()
        return FileResponse(
            path,
            media_type=_mime_for(path, row["kind"]),
            filename=path.name,
        )

    @app.post("/api/media/{media_id}/edit")
    def media_edit(media_id: int, body: EditPhotoBody):
        conn = connect(cache)
        try:
            try:
                return apply_photo_edit(
                    conn, library, cache, media_id, rotate=body.rotate, crop=body.crop
                )
            except FileNotFoundError as exc:
                raise HTTPException(404, str(exc)) from exc
            except FileExistsError as exc:
                raise HTTPException(409, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/media/{media_id}/play")
    def media_play(media_id: int):
        """H.264 / AAC pour le <video> HTML (conversion HEVC, MPG, etc.)."""
        conn = connect(cache)
        try:
            row, path = media_or_404(conn, media_id)
            kind = row["kind"]
            size = int(row["size"] or 0)
            mtime_ns = int(row["mtime_ns"] or 0)
        finally:
            conn.close()
        if kind != "video":
            raise HTTPException(400, "pas une vidéo")
        dest = cached_play_path(cache, media_id, size, mtime_ns)
        try:
            out = ensure_play_mp4(path, dest)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return FileResponse(out, media_type="video/mp4")

    @app.post("/api/index")
    def start_index(body: IndexBody):
        year = None if body.all else body.year

        def run(progress):
            conn = connect(cache)
            try:
                return index_library(
                    conn,
                    library,
                    cache,
                    year=year,
                    limit=body.limit,
                    progress=progress,
                )
            finally:
                conn.close()

        return jobs.start("index", run)

    @app.post("/api/faces/scan")
    def start_faces(body: FacesBody):
        def run(progress):
            conn = connect(cache)
            try:
                return scan_faces(
                    conn,
                    library,
                    cache,
                    year=body.year,
                    limit=body.limit,
                    progress=progress,
                )
            finally:
                conn.close()

        return jobs.start("faces", run)

    @app.post("/api/scenes/scan")
    def start_scenes(body: ScenesBody):
        def run(progress):
            conn = connect(cache)
            try:
                return scan_scenes(
                    conn,
                    library,
                    cache,
                    year=body.year,
                    place=body.place,
                    limit=body.limit,
                    progress=progress,
                )
            finally:
                conn.close()

        return jobs.start("scenes", run)

    @app.post("/api/scenes/tag-many")
    def scenes_tag_many(body: SceneIdsBody):
        conn = connect(cache)
        try:
            try:
                return add_scenes(conn, body.ids, body.tag)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/scenes/untag-many")
    def scenes_untag_many(body: SceneIdsBody):
        conn = connect(cache)
        try:
            try:
                return remove_scenes(conn, body.ids, body.tag)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/scenes/workspace")
    def scenes_workspace_api(
        year: int | None = None,
        place: str | None = None,
        limit: int = Query(80, ge=1, le=200),
    ):
        conn = connect(cache)
        try:
            return scenes_workspace(conn, year=year, place=place, limit=limit)
        finally:
            conn.close()

    @app.get("/api/scenes/untagged")
    def scenes_untagged_api(
        year: int | None = None,
        place: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(80, ge=1, le=200),
    ):
        conn = connect(cache)
        try:
            return untagged_media(
                conn, year=year, place=place, offset=offset, limit=limit
            )
        finally:
            conn.close()

    @app.get("/api/scenes/{tag}/media")
    def scenes_review_media(
        tag: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=400),
        year: int | None = None,
        place: str | None = None,
    ):
        conn = connect(cache)
        try:
            try:
                return media_for_scene(
                    conn, tag, offset=offset, limit=limit, year=year, place=place
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/people/merge")
    def merge_persons(body: MergePeopleBody):
        conn = connect(cache)
        try:
            try:
                return merge_people(conn, body.keep_id, body.absorb_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/people")
    def list_people():
        conn = connect(cache)
        try:
            rows = conn.execute(
                """
                SELECT p.id, p.name, COUNT(f.id) AS count
                FROM people p
                LEFT JOIN faces f ON f.person_id = p.id
                GROUP BY p.id
                ORDER BY p.name COLLATE NOCASE
                """
            ).fetchall()
            return {"people": [dict(r) for r in rows]}
        finally:
            conn.close()

    @app.get("/api/people/{person_id}/faces")
    def list_person_faces(
        person_id: int,
        offset: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=400),
    ):
        conn = connect(cache)
        try:
            try:
                return person_faces_payload(conn, person_id, offset, limit)
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc
        finally:
            conn.close()

    @app.patch("/api/people/{person_id}")
    def patch_person(person_id: int, body: NameClusterBody):
        conn = connect(cache)
        try:
            try:
                return rename_person(conn, person_id, body.name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.delete("/api/people/{person_id}")
    def remove_person(person_id: int):
        conn = connect(cache)
        try:
            try:
                return delete_person(conn, person_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/faces/status")
    def faces_status():
        conn = connect(cache)
        try:
            present = conn.execute(
                "SELECT COUNT(*) FROM media WHERE present=1"
            ).fetchone()[0]
            scanned = conn.execute(
                "SELECT COUNT(*) FROM media WHERE present=1 AND face_scanned=1"
            ).fetchone()[0]
            faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
            unlabeled = conn.execute(
                "SELECT COUNT(*) FROM faces WHERE person_id IS NULL"
            ).fetchone()[0]
            copies = conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT 1 FROM media
                    WHERE present=1 AND size > 0 AND taken_at IS NOT NULL
                    GROUP BY size, taken_at
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]
        finally:
            conn.close()
        return {
            "media": present,
            "scanned": scanned,
            "pending": max(0, present - scanned),
            "faces": faces,
            "unlabeled": unlabeled,
            "copy_groups": copies,
        }

    @app.get("/api/faces/clusters")
    def list_clusters(limit: int = Query(40, ge=1, le=200)):
        conn = connect(cache)
        try:
            clusters = conn.execute(
                """
                SELECT cluster_id, COUNT(*) AS count
                FROM faces
                WHERE person_id IS NULL AND cluster_id IS NOT NULL
                GROUP BY cluster_id
                ORDER BY count DESC, cluster_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            out = []
            for cl in clusters:
                cid = int(cl["cluster_id"])
                faces = conn.execute(
                    """
                    SELECT f.id, f.media_id, f.score, m.size, m.taken_at, m.dhash,
                           m.present, m.relpath, m.year
                    FROM faces f
                    JOIN media m ON m.id = f.media_id
                    WHERE f.cluster_id=? AND f.person_id IS NULL
                    ORDER BY f.score DESC, f.id
                    LIMIT 400
                    """,
                    (cid,),
                ).fetchall()
                live_rows = []
                for face in faces:
                    item = dict(face)
                    live_id = live_media_id_for_face(conn, item)
                    if live_id is None:
                        continue
                    item["media_id"] = live_id
                    live_rows.append(item)
                unique, hidden = unique_faces(live_rows)
                shown = unique
                if not shown:
                    continue
                out.append(
                    {
                        "id": cid,
                        "count": int(cl["count"]),
                        "photos": len(unique),
                        "copies": hidden,
                        "faces": [
                            {"id": f["id"], "media_id": f["media_id"], "score": f["score"]}
                            for f in shown
                        ],
                    }
                )
            unlabeled = conn.execute(
                "SELECT COUNT(*) FROM faces WHERE person_id IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()
        return {"clusters": out, "unlabeled": unlabeled}

    @app.get("/api/faces/{face_id}/thumb")
    def face_thumb(face_id: int):
        dest = face_thumb_file(cache, face_id)
        if dest.is_file():
            return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        conn = connect(cache)
        try:
            row = conn.execute("SELECT media_id FROM faces WHERE id=?", (face_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HTTPException(404, "visage introuvable")
        return media_thumb(int(row["media_id"]))

    @app.post("/api/faces/name-many")
    def name_many_faces(body: FaceIdsNameBody):
        conn = connect(cache)
        try:
            try:
                return name_faces_many(conn, body.ids, body.name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/faces/unname-many")
    def unname_many_faces(body: FaceIdsBody):
        conn = connect(cache)
        try:
            try:
                return unname_faces_many(conn, body.ids)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/faces/{face_id}/name")
    def name_one_face(face_id: int, body: NameClusterBody):
        conn = connect(cache)
        try:
            row = conn.execute("SELECT id FROM faces WHERE id=?", (face_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "visage introuvable")
            try:
                result = name_face(conn, face_id, body.name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()
        return result

    @app.post("/api/faces/clusters/{cluster_id}/name")
    def name_faces(cluster_id: int, body: NameClusterBody):
        conn = connect(cache)
        try:
            exists = conn.execute(
                "SELECT COUNT(*) FROM faces WHERE cluster_id=?", (cluster_id,)
            ).fetchone()[0]
            if not exists:
                raise HTTPException(404, "groupe introuvable")
            try:
                result = name_cluster(conn, cluster_id, body.name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()
        return result

    @app.post("/api/export/copy")
    def export_copy(body: ExportCopyBody):
        dest = Path(body.dest).expanduser()
        try:
            dest = dest.resolve()
        except OSError as exc:
            raise HTTPException(400, str(exc)) from exc
        lib = library.resolve()
        if dest == lib or lib in dest.parents:
            raise HTTPException(400, "destination à l'intérieur de la bibliothèque")
        dest.mkdir(parents=True, exist_ok=True)
        conn = connect(cache)
        copied = []
        errors = []
        try:
            for media_id in body.ids:
                row = conn.execute(
                    "SELECT id, relpath FROM media WHERE id=? AND present=1",
                    (media_id,),
                ).fetchone()
                if row is None:
                    errors.append({"id": media_id, "error": "introuvable"})
                    continue
                src = locate_library_file(library, row["relpath"])
                if src is None:
                    errors.append({"id": media_id, "error": "absent du NAS"})
                    continue
                target = _unique_dest(dest, src.name)
                try:
                    shutil.copy2(src, target)
                    copied.append(str(target))
                except OSError as exc:
                    errors.append({"id": media_id, "error": str(exc)})
        finally:
            conn.close()
        return {"dest": str(dest), "copied": len(copied), "files": copied, "errors": errors}

    @app.post("/api/export/zip")
    def export_zip(body: ExportZipBody):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        zip_path = cache / "exports" / f"export-{stamp}.zip"
        conn = connect(cache)
        n = 0
        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
                used: set[str] = set()
                for media_id in body.ids:
                    row = conn.execute(
                        "SELECT relpath FROM media WHERE id=? AND present=1",
                        (media_id,),
                    ).fetchone()
                    if row is None:
                        continue
                    src = locate_library_file(library, row["relpath"])
                    if src is None:
                        continue
                    name = src.name
                    if name in used:
                        name = f"{src.stem}_{media_id}{src.suffix}"
                    used.add(name)
                    zf.write(src, arcname=name)
                    n += 1
        finally:
            conn.close()
        if n == 0:
            zip_path.unlink(missing_ok=True)
            raise HTTPException(400, "aucun fichier à exporter")
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"photos-{stamp}.zip",
        )

    @app.post("/api/media/move-targets")
    def media_move_targets(body: MoveTargetsBody):
        conn = connect(cache)
        try:
            try:
                return move_targets(conn, library, body.ids)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/media/move")
    def media_move(body: MoveMediaBody):
        conn = connect(cache)
        try:
            try:
                return move_selected(conn, library, body.ids, body.dest)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/media/delete")
    def delete_media(body: DeleteMediaBody):
        conn = connect(cache)
        try:
            return trash_selected(conn, library, cache, body.ids)
        finally:
            conn.close()

    @app.post("/api/media/favorite")
    def favorite_media(body: FavoriteBody):
        conn = connect(cache)
        try:
            return set_favorite(conn, body.ids, body.favorite)
        finally:
            conn.close()

    @app.post("/api/media/place")
    def media_place(body: PlaceBody):
        conn = connect(cache)
        try:
            try:
                return set_media_places(
                    conn,
                    body.ids,
                    body.place,
                    apply_folder=body.apply_folder,
                    lat=body.lat,
                    lon=body.lon,
                    cc=body.cc,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/albums")
    def get_albums():
        conn = connect(cache)
        try:
            return {"albums": list_albums(conn)}
        finally:
            conn.close()

    @app.post("/api/albums")
    def post_album(body: AlbumBody):
        conn = connect(cache)
        try:
            try:
                return create_album(conn, body.name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/albums/remove")
    def albums_remove(body: AssignAlbumsBody):
        conn = connect(cache)
        try:
            try:
                return remove_media_albums(conn, body.ids, body.album_ids)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/albums/assign")
    def albums_assign(body: AssignAlbumsBody):
        conn = connect(cache)
        try:
            try:
                return assign_media_albums(
                    conn,
                    body.ids,
                    body.album_ids,
                    create=body.create,
                    replace=body.replace,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.delete("/api/albums/{album_id}")
    def drop_album(album_id: int):
        conn = connect(cache)
        try:
            try:
                return delete_album(conn, album_id)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/albums/{album_id}/media")
    def album_add(album_id: int, body: AlbumMediaBody):
        conn = connect(cache)
        try:
            try:
                return add_to_album(conn, album_id, body.ids)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/albums/{album_id}/remove")
    def album_remove(album_id: int, body: AlbumMediaBody):
        conn = connect(cache)
        try:
            return remove_from_album(conn, album_id, body.ids)
        finally:
            conn.close()

    @app.get("/api/map")
    def get_map():
        conn = connect(cache)
        try:
            return map_places(conn)
        finally:
            conn.close()

    @app.get("/api/geo/search")
    def geo_search(q: str = Query("", max_length=80)):
        conn = connect(cache)
        try:
            from photo_library.places import user_coord_map

            return {"matches": search_places(q, overrides=user_coord_map(conn))}
        finally:
            conn.close()

    @app.get("/api/geo/reverse")
    def geo_reverse(
        lat: float = Query(..., ge=-90, le=90),
        lon: float = Query(..., ge=-180, le=180),
    ):
        return reverse_place(lat, lon)

    TRASH_SYNC_MAX = 200

    def _trash_ids_for(body: TrashActionBody) -> list[int]:
        conn = connect(cache)
        try:
            if body.all:
                return list_trash_ids(conn)
            seen: set[int] = set()
            ids: list[int] = []
            for media_id in body.ids:
                if media_id in seen:
                    continue
                seen.add(media_id)
                ids.append(media_id)
            return ids
        finally:
            conn.close()

    def _run_trash_action(kind: str, body: TrashActionBody, worker):
        ids = _trash_ids_for(body)
        if not ids:
            raise HTTPException(400, "cochez des photos")
        if len(ids) > TRASH_SYNC_MAX:

            def run(progress):
                conn = connect(cache)
                try:
                    return worker(conn, ids, progress)
                finally:
                    conn.close()

            return jobs.start(kind, run)
        conn = connect(cache)
        try:
            return worker(conn, ids, None)
        finally:
            conn.close()

    @app.get("/api/trash")
    def get_trash(
        offset: int = Query(0, ge=0),
        limit: int = Query(80, ge=1, le=200),
    ):
        conn = connect(cache)
        try:
            expiring = expired_trash_count(conn)
            kicked = _kick_trash_expire(force=True) if expiring else None
            total = trash_count(conn)
            items = list_trash(conn, offset=offset, limit=limit)
            purged = 0
            if isinstance(kicked, dict) and "deleted" in kicked and "status" not in kicked:
                purged = int(kicked.get("deleted") or 0)
            return {
                "items": items,
                "count": total,
                "offset": offset,
                "limit": limit,
                "keep_days": KEEP_DAYS,
                "purged": purged,
                "expiring": expiring if not purged else 0,
            }
        finally:
            conn.close()

    @app.post("/api/trash/expire")
    def trash_expire(body: ConfirmBody):
        if not body.confirm:
            raise HTTPException(400, "confirmation requise")
        result = _kick_trash_expire(force=True)
        return result or {"status": "skipped"}

    @app.get("/api/trash/ids")
    def get_trash_ids():
        conn = connect(cache)
        try:
            ids = list_trash_ids(conn)
            return {"ids": ids, "total": len(ids)}
        finally:
            conn.close()

    @app.post("/api/trash/restore")
    def trash_restore(body: TrashActionBody):
        def worker(conn, ids, progress):
            return restore_selected(conn, library, ids, cache, progress=progress)

        return _run_trash_action("trash-restore", body, worker)

    @app.post("/api/trash/purge")
    def trash_purge(body: TrashActionBody):
        def worker(conn, ids, progress):
            return purge_selected(conn, library, cache, ids, progress=progress)

        return _run_trash_action("trash-purge", body, worker)

    def _cinema_user_key(request: Request) -> str:
        user = getattr(request.state, "user", None)
        if isinstance(user, dict) and user.get("id") is not None:
            return f"user:{int(user['id'])}"
        return "default"

    def _cinema_item_path(conn, item_id: int) -> tuple[dict, Path]:
        item = get_cinema_item(conn, item_id)
        if item is None:
            raise HTTPException(404, "vidéo introuvable")
        cfg = load_settings()
        root_raw = str(cfg.get("cinema_dir") or "").strip()
        if not root_raw:
            raise HTTPException(400, "dossier Cinéma non configuré")
        root = Path(root_raw).expanduser().resolve()
        fpath = (root / item["relpath"]).resolve()
        try:
            fpath.relative_to(root)
        except ValueError as exc:
            raise HTTPException(403, "chemin hors dossier Cinéma") from exc
        if not fpath.exists():
            raise HTTPException(404, "fichier vidéo absent du disque ou NAS")
        return item, fpath

    @app.get("/api/cinema/status")
    def cinema_status():
        cfg = load_settings()
        dstatus = cinema_dir_status(cfg.get("cinema_dir"))
        conn = connect(cache)
        try:
            flt = cinema_filters(conn)
        finally:
            conn.close()
        return {
            "cinema_dir": cfg.get("cinema_dir") or "",
            "optical_device": cfg.get("optical_device") or "",
            "dir_status": dstatus,
            "ffmpeg": ffmpeg_capabilities(),
            "total": flt["total"],
            "all_types": list(MEDIA_TYPES),
            "all_categories": list(CATEGORIES),
        }

    @app.get("/api/cinema/filters")
    def get_cinema_filters():
        conn = connect(cache)
        try:
            data = cinema_filters(conn)
        finally:
            conn.close()
        data["all_types"] = list(MEDIA_TYPES)
        data["all_categories"] = list(CATEGORIES)
        return data

    @app.get("/api/cinema/items")
    def get_cinema_items(
        request: Request,
        media_type: str | None = None,
        category: str | None = None,
        year: int | None = None,
        q: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(80, ge=1, le=200),
    ):
        conn = connect(cache)
        try:
            return list_cinema_items(
                conn,
                media_type=media_type or None,
                category=category or None,
                year=year,
                q=q,
                offset=offset,
                limit=limit,
                user_key=_cinema_user_key(request),
            )
        finally:
            conn.close()

    @app.get("/api/cinema/continue")
    def get_cinema_continue(request: Request, limit: int = Query(12, ge=1, le=40)):
        conn = connect(cache)
        try:
            return {"items": continue_watching(conn, _cinema_user_key(request), limit=limit)}
        finally:
            conn.close()

    @app.get("/api/cinema/items/{item_id}")
    def get_cinema_item_detail(item_id: int, request: Request):
        conn = connect(cache)
        try:
            item = get_cinema_item(conn, item_id, user_key=_cinema_user_key(request))
        finally:
            conn.close()
        if item is None:
            raise HTTPException(404, "vidéo introuvable")
        return item

    @app.get("/api/cinema/items/{item_id}/info")
    def get_cinema_item_info(item_id: int, request: Request):
        conn = connect(cache)
        try:
            item, fpath = _cinema_item_path(conn, item_id)
            item = get_cinema_item(conn, item_id, user_key=_cinema_user_key(request)) or item
        finally:
            conn.close()
        if item["source_type"] in {"dvd", "bluray"}:
            opt = inspect_optical_source(fpath, hint_kind=item["source_type"])
            titles = opt["titles"]
            chosen = titles[0] if titles else None
            for t in titles:
                if t.index == opt["default_title"]:
                    chosen = t
                    break
            probe_dict = (
                chosen.probe.to_dict()
                if (chosen is not None and chosen.probe is not None)
                else {
                    "readable": False,
                    "duration_s": None,
                    "width": None,
                    "height": None,
                    "video_codec": "",
                    "pix_fmt": "",
                    "audio_tracks": [],
                    "subtitle_tracks": [],
                    "chapters": [],
                    "tags": {},
                }
            )
            return {
                "item": item,
                "probe": probe_dict,
                "titles": [t.to_dict() for t in titles],
                "default_title": opt["default_title"],
                "encrypted": opt["encrypted"],
                "encryption_hint": opt["encryption_hint"],
            }
        probe = probe_media(fpath).to_dict()
        return {"item": item, "probe": probe, "titles": []}

    @app.get("/api/cinema/disc")
    def get_cinema_disc():
        cfg = load_settings()
        return inspect_configured_disc(str(cfg.get("optical_device") or ""))

    @app.get("/api/cinema/items/{item_id}/poster")
    def get_cinema_poster(item_id: int):
        poster = cinema_poster_path(cache, item_id)
        if poster.is_file() and poster.stat().st_size > 128:
            return FileResponse(
                poster,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        svg = PLACEHOLDER_SVG.format(label="Cinéma")
        return Response(content=svg, media_type="image/svg+xml")

    @app.get("/api/cinema/items/{item_id}/subtitles/{sub_idx}.vtt")
    def get_cinema_subtitle(item_id: int, sub_idx: int):
        conn = connect(cache)
        try:
            item, fpath = _cinema_item_path(conn, item_id)
        finally:
            conn.close()
        dest = (
            cache
            / "cinema_subs"
            / f"{item_id}-{int(item.get('mtime_ns') or 0)}-{int(sub_idx)}.vtt"
        )
        try:
            out = extract_subtitle_vtt(fpath, sub_idx, dest)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return FileResponse(out, media_type="text/vtt; charset=utf-8")

    @app.post("/api/cinema/items/{item_id}/metadata")
    def post_cinema_metadata(item_id: int, body: CinemaMetadataBody):
        conn = connect(cache)
        try:
            updated = update_cinema_metadata(
                conn,
                item_id,
                title=body.title,
                media_type=body.media_type,
                year=body.year,
                clear_year=body.clear_year,
                director=body.director,
                overview=body.overview,
                categories=body.categories,
                metadata_locked=body.metadata_locked,
            )
        finally:
            conn.close()
        if updated is None:
            raise HTTPException(404, "vidéo introuvable")
        return updated

    @app.post("/api/cinema/scan")
    def post_cinema_scan():
        cfg = load_settings()
        status = cinema_dir_status(cfg.get("cinema_dir"), create_local=True)
        if status["status"] != "ready":
            raise HTTPException(
                400,
                f"Dossier Cinéma indisponible ({status['status']}) : {status['path'] or 'non configuré'}",
            )
        cinema_root = Path(status["path"])

        def run(progress):
            conn = connect(cache)
            try:
                return scan_cinema_library(conn, cinema_root, cache, progress=progress)
            finally:
                conn.close()

        return jobs.start("cinema-scan", run)

    @app.post("/api/cinema/enrich")
    def post_cinema_enrich(body: CinemaEnrichBody):
        def run(progress):
            conn = connect(cache)
            try:
                return enrich_cinema_library(
                    conn,
                    lang=body.lang,
                    only_missing=body.only_missing,
                    limit=body.limit,
                    progress=progress,
                )
            finally:
                conn.close()

        return jobs.start("cinema-enrich", run)

    @app.post("/api/cinema/stream/start")
    def post_cinema_stream_start(body: CinemaStreamStartBody):
        quality = (
            body.quality
            if body.quality in {"auto", "original", "1080p", "720p", "480p"}
            else "auto"
        )
        if body.disc:
            cfg = load_settings()
            dev_raw = str(cfg.get("optical_device") or "").strip()
            if not dev_raw:
                raise HTTPException(400, "aucun lecteur optique configuré dans Paramètres")
            dev_path = Path(dev_raw).expanduser()
            try:
                title, _opt = resolve_optical_title(dev_path, title_index=body.title_index)
                return hls.start_session(
                    dev_path,
                    item_key=f"disc:{title.index}",
                    start_s=body.start_s,
                    audio_idx=body.audio_idx,
                    quality=quality,
                    input_args=title.input_args,
                    probe=title.probe,
                    force_transcode=True,
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

        if body.item_id is None:
            raise HTTPException(400, "item_id ou disc requis")
        conn = connect(cache)
        try:
            item, fpath = _cinema_item_path(conn, body.item_id)
        finally:
            conn.close()
        if item["source_type"] in {"dvd", "bluray"}:
            try:
                title, _opt = resolve_optical_title(
                    fpath,
                    hint_kind=item["source_type"],
                    title_index=body.title_index,
                )
                return hls.start_session(
                    fpath,
                    item_key=f"item:{body.item_id}",
                    start_s=body.start_s,
                    audio_idx=body.audio_idx,
                    quality=quality,
                    input_args=title.input_args,
                    probe=title.probe,
                    force_transcode=True,
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        try:
            return hls.start_session(
                fpath,
                item_key=f"item:{body.item_id}",
                start_s=body.start_s,
                audio_idx=body.audio_idx,
                quality=quality,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/cinema/stream/{sid}/{filename}")
    def get_cinema_stream_file(sid: str, filename: str):
        path = hls.resolve_file(sid, filename)
        if path is None:
            raise HTTPException(404, "segment ou session HLS introuvable")
        if filename.endswith(".m3u8"):
            return Response(
                content=path.read_bytes(),
                media_type="application/vnd.apple.mpegurl",
                headers={"Cache-Control": "no-store, no-cache"},
            )
        return FileResponse(
            path,
            media_type="video/mp2t",
            headers={"Cache-Control": "public, max-age=60"},
        )

    @app.post("/api/cinema/stream/{sid}/stop")
    def post_cinema_stream_stop(sid: str):
        return {"stopped": hls.stop_session(sid)}

    @app.post("/api/cinema/progress")
    def post_cinema_progress(body: CinemaProgressBody, request: Request):
        conn = connect(cache)
        try:
            return save_cinema_progress(
                conn,
                user_key=_cinema_user_key(request),
                item_key=f"item:{body.item_id}",
                position_s=body.position_s,
                duration_s=body.duration_s,
                title_index=body.title_index,
                audio_idx=body.audio_idx,
                subtitle_idx=body.subtitle_idx,
            )
        finally:
            conn.close()

    @app.post("/api/cinema/progress/clear")
    def post_cinema_progress_clear(body: CinemaClearProgressBody, request: Request):
        conn = connect(cache)
        try:
            cleared = clear_cinema_progress(
                conn,
                user_key=_cinema_user_key(request),
                item_id=body.item_id,
            )
            return {"cleared": cleared}
        finally:
            conn.close()

    def _cinema_root_or_400() -> Path:
        cfg = load_settings()
        raw = str(cfg.get("cinema_dir") or "").strip()
        if not raw:
            raise HTTPException(400, "dossier Cinéma non configuré")
        return Path(raw).expanduser().resolve()

    @app.post("/api/cinema/items/{item_id}/trash")
    def post_cinema_trash_item(item_id: int):
        root = _cinema_root_or_400()
        conn = connect(cache)
        try:
            return trash_cinema_item(conn, root, item_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(500, str(exc)) from exc
        finally:
            conn.close()

    @app.get("/api/cinema/trash")
    def get_cinema_trash():
        conn = connect(cache)
        try:
            items = list_cinema_trash(conn)
            return {"items": items, "count": len(items), "keep_days": CINEMA_KEEP_DAYS}
        finally:
            conn.close()

    @app.post("/api/cinema/trash/{item_id}/restore")
    def post_cinema_trash_restore(item_id: int):
        root = _cinema_root_or_400()
        conn = connect(cache)
        try:
            return restore_cinema_item(conn, root, item_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(500, str(exc)) from exc
        finally:
            conn.close()

    @app.post("/api/cinema/trash/{item_id}/purge")
    def post_cinema_trash_purge(item_id: int):
        root = _cinema_root_or_400()
        conn = connect(cache)
        try:
            return purge_cinema_item(conn, root, cache, item_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(500, str(exc)) from exc
        finally:
            conn.close()

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
