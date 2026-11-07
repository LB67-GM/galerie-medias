from __future__ import annotations

import sqlite3
import subprocess
import threading
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from photo_library.config import FACE_THUMB_SIZE, JPEG_QUALITY
from photo_library.ffmpeg_util import ffmpeg_bin
from photo_library.scan import kind_of
from photo_library.locate import locate_library_file, maybe_fix_relpath
from photo_library.thumbs import ensure_heif, face_thumb_file

Progress = Callable[[int, int | None, str], None]

YUNET_URLS = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
)
SFACE_URLS = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
)

INSIGHT_SIM = 0.42
SFACE_SIM = 0.363
CLUSTER_DELTA = 0.02
CENTROID_PER_PERSON = 80
_engine = None
_write_lock = threading.Lock()


class FaceHit:
    __slots__ = ("x", "y", "w", "h", "score", "embedding")

    def __init__(self, x: float, y: float, w: float, h: float, score: float, embedding: np.ndarray):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.score = score
        self.embedding = embedding


class FaceEngine:
    name = "unknown"
    threshold = 0.4

    def detect(self, bgr: np.ndarray) -> list[FaceHit]:
        raise NotImplementedError


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def l2norm(vec: np.ndarray) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(arr))
    if n <= 1e-8:
        return arr
    return arr / n


def _download(urls: tuple[str, ...], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "photo-library/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
            if dest.stat().st_size > 50_000:
                return
            dest.unlink(missing_ok=True)
            last_err = RuntimeError(f"fichier trop petit: {url}")
        except Exception as exc:
            dest.unlink(missing_ok=True)
            last_err = exc
    raise RuntimeError(f"téléchargement modèle impossible: {last_err}")


def load_bgr(path: Path, max_side: int = 1280) -> np.ndarray | None:
    ensure_heif()
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > max_side:
                img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            rgb = np.asarray(img)
            return np.ascontiguousarray(rgb[:, :, ::-1])
    except Exception:
        return None


def ffmpeg_frame_bgr(path: Path, seconds: float, max_side: int = 1280) -> np.ndarray | None:
    vf = f"scale='min({max_side},iw)':-2"
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{seconds:.3f}",
        "-i",
        str(path),
        "-an",
        "-frames:v",
        "1",
        "-vf",
        vf,
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=45, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    import cv2

    arr = np.frombuffer(proc.stdout, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return bgr


def video_duration(path: Path) -> float | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    try:
        val = float((proc.stdout or "").strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
    if val <= 0 or val != val:
        return None
    return val


def sample_times(duration: float | None) -> list[float]:
    if duration is None or duration < 0.8:
        return [0.0]
    if duration < 4:
        return [max(0.0, duration * 0.25)]
    return [duration * x for x in (0.12, 0.4, 0.72)]


def save_face_thumb(bgr: np.ndarray, hit: FaceHit, dest: Path) -> None:
    h, w = bgr.shape[:2]
    pad = 0.22
    x1 = max(0, int((hit.x - pad * hit.w) * w))
    y1 = max(0, int((hit.y - pad * hit.h) * h))
    x2 = min(w, int((hit.x + hit.w * (1 + pad)) * w))
    y2 = min(h, int((hit.y + hit.h * (1 + pad)) * h))
    if x2 <= x1 or y2 <= y1:
        return
    crop = bgr[y1:y2, x1:x2]
    rgb = crop[:, :, ::-1]
    img = Image.fromarray(rgb)
    img.thumbnail((FACE_THUMB_SIZE, FACE_THUMB_SIZE), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    img.save(tmp, "JPEG", quality=JPEG_QUALITY)
    tmp.replace(dest)


class InsightFaceEngine(FaceEngine):
    name = "insightface"
    threshold = INSIGHT_SIM

    def __init__(self):
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        self._app = app

    def detect(self, bgr: np.ndarray) -> list[FaceHit]:
        h, w = bgr.shape[:2]
        if h < 16 or w < 16:
            return []
        faces = self._app.get(bgr)
        hits: list[FaceHit] = []
        for face in faces:
            box = face.bbox.astype(float)
            x1, y1, x2, y2 = box.tolist()
            fw = max(1.0, x2 - x1)
            fh = max(1.0, y2 - y1)
            emb = getattr(face, "normed_embedding", None)
            if emb is None:
                emb = l2norm(face.embedding)
            else:
                emb = l2norm(emb)
            hits.append(
                FaceHit(
                    x=x1 / w,
                    y=y1 / h,
                    w=fw / w,
                    h=fh / h,
                    score=float(getattr(face, "det_score", 0.0)),
                    embedding=emb,
                )
            )
        return hits


class SFaceEngine(FaceEngine):
    name = "sface"
    threshold = SFACE_SIM

    def __init__(self, cache: Path):
        import cv2

        models = cache / "models"
        yunet = models / "face_detection_yunet_2023mar.onnx"
        sface = models / "face_recognition_sface_2021dec.onnx"
        if not yunet.is_file():
            _download(YUNET_URLS, yunet)
        if not sface.is_file():
            _download(SFACE_URLS, sface)
        self._cv2 = cv2
        self._yunet_path = str(yunet)
        self._recognizer = cv2.FaceRecognizerSF_create(str(sface), "")

    def detect(self, bgr: np.ndarray) -> list[FaceHit]:
        cv2 = self._cv2
        h, w = bgr.shape[:2]
        if h < 16 or w < 16:
            return []
        detector = cv2.FaceDetectorYN_create(self._yunet_path, "", (w, h), 0.65, 0.3, 50)
        detector.setInputSize((w, h))
        _ok, faces = detector.detect(bgr)
        if faces is None or len(faces) == 0:
            return []
        hits: list[FaceHit] = []
        for row in faces:
            x, y, fw, fh = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
            score = float(row[-1])
            aligned = self._recognizer.alignCrop(bgr, row)
            feat = l2norm(self._recognizer.feature(aligned))
            hits.append(
                FaceHit(
                    x=max(0.0, x / w),
                    y=max(0.0, y / h),
                    w=max(0.002, fw / w),
                    h=max(0.002, fh / h),
                    score=score,
                    embedding=feat,
                )
            )
        return hits


def get_engine(cache: Path) -> FaceEngine:
    global _engine
    if _engine is not None:
        return _engine
    try:
        _engine = InsightFaceEngine()
        return _engine
    except Exception as exc:
        print(f"InsightFace indisponible ({exc}). Repli OpenCV SFace.", flush=True)
        _engine = SFaceEngine(cache)
        return _engine


def _set_engine_meta(conn, engine: FaceEngine) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key='face_engine'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('face_engine', ?)",
            (engine.name,),
        )
        conn.commit()
        return
    if row["value"] == engine.name:
        return
    conn.execute("DELETE FROM faces")
    conn.execute("UPDATE media SET face_scanned=0")
    conn.execute("UPDATE meta SET value=? WHERE key='face_engine'", (engine.name,))
    conn.commit()


def _vec_from_row(row) -> np.ndarray | None:
    arr = np.frombuffer(row["embedding"], dtype=np.float32)
    if arr.size != int(row["dim"]):
        return None
    return l2norm(arr)


def _next_cluster_id(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(cluster_id), 0) FROM faces").fetchone()
    return int(row[0] or 0) + 1


def _person_centroids(conn) -> dict[int, np.ndarray]:
    rows = conn.execute(
        f"""
        SELECT person_id, embedding, dim FROM (
            SELECT person_id, embedding, dim,
                   ROW_NUMBER() OVER (
                       PARTITION BY person_id ORDER BY score DESC, id
                   ) AS rn
            FROM faces
            WHERE person_id IS NOT NULL
        ) WHERE rn <= {int(CENTROID_PER_PERSON)}
        """
    ).fetchall()
    buckets: dict[int, list[np.ndarray]] = {}
    for row in rows:
        vec = _vec_from_row(row)
        if vec is None:
            continue
        buckets.setdefault(int(row["person_id"]), []).append(vec)
    return {pid: l2norm(np.mean(np.stack(vecs), axis=0)) for pid, vecs in buckets.items() if vecs}


def matching_threshold(conn) -> float:
    row = conn.execute(
        "SELECT value FROM meta WHERE key='face_engine'"
    ).fetchone()
    value = (row[0] if row else "") or ""
    if "sface" in value.lower():
        return SFACE_SIM
    return INSIGHT_SIM


def match_unlabeled(conn, threshold: float, media_id: int | None = None) -> int:
    centroids = _person_centroids(conn)
    if not centroids:
        return 0
    pids = list(centroids.keys())
    centers = np.stack([centroids[pid] for pid in pids])
    sql = "SELECT id, embedding, dim FROM faces WHERE person_id IS NULL"
    params: list = []
    if media_id is not None:
        sql += " AND media_id=?"
        params.append(media_id)
    rows = conn.execute(sql, params).fetchall()
    ids: list[int] = []
    vecs: list[np.ndarray] = []
    for row in rows:
        vec = _vec_from_row(row)
        if vec is None:
            continue
        ids.append(int(row["id"]))
        vecs.append(vec)
    if not vecs:
        return 0
    mat = np.stack(vecs)
    sims = mat @ centers.T
    best = np.argmax(sims, axis=1)
    best_sim = sims[np.arange(len(ids)), best]
    updates = [
        (int(pids[int(best[i])]), ids[i])
        for i, sim in enumerate(best_sim)
        if float(sim) >= threshold
    ]
    if not updates:
        return 0
    conn.executemany(
        "UPDATE faces SET person_id=?, cluster_id=NULL WHERE id=?",
        updates,
    )
    conn.commit()
    return len(updates)


def recluster(conn, threshold: float) -> int:
    """Regroupe seulement les visages sans cluster (nouveaux), sans tout recalculer."""
    cut = threshold - CLUSTER_DELTA
    new_rows = conn.execute(
        """
        SELECT id, embedding, dim FROM faces
        WHERE person_id IS NULL AND cluster_id IS NULL
        """
    ).fetchall()
    ids: list[int] = []
    vecs: list[np.ndarray] = []
    for row in new_rows:
        vec = _vec_from_row(row)
        if vec is None:
            continue
        ids.append(int(row["id"]))
        vecs.append(vec)
    if not vecs:
        return 0
    mat = np.stack(vecs)
    assigned = np.full(len(ids), -1, dtype=np.int32)

    old = conn.execute(
        """
        SELECT cluster_id, embedding, dim FROM (
            SELECT cluster_id, embedding, dim,
                   ROW_NUMBER() OVER (
                       PARTITION BY cluster_id ORDER BY score DESC, id
                   ) AS rn
            FROM faces
            WHERE person_id IS NULL AND cluster_id IS NOT NULL
        ) WHERE rn <= 24
        """
    ).fetchall()
    by_cluster: dict[int, list[np.ndarray]] = {}
    for row in old:
        vec = _vec_from_row(row)
        if vec is None:
            continue
        by_cluster.setdefault(int(row["cluster_id"]), []).append(vec)
    if by_cluster:
        cids = list(by_cluster.keys())
        centers = np.stack(
            [l2norm(np.mean(np.stack(by_cluster[cid]), axis=0)) for cid in cids]
        )
        sims = mat @ centers.T
        best = np.argmax(sims, axis=1)
        best_sim = sims[np.arange(len(ids)), best]
        for i, sim in enumerate(best_sim):
            if float(sim) >= cut:
                assigned[i] = int(cids[int(best[i])])

    leftover = np.flatnonzero(assigned < 0)
    next_cluster = _next_cluster_id(conn)
    created = 0
    if leftover.size:
        sub = mat[leftover]
        sub_ass = np.full(leftover.size, -1, dtype=np.int32)
        for i in range(leftover.size):
            if sub_ass[i] >= 0:
                continue
            cid = next_cluster
            next_cluster += 1
            created += 1
            sub_ass[i] = cid
            pending = sub_ass < 0
            if not np.any(pending):
                continue
            sims = sub[pending] @ sub[i]
            hits = np.flatnonzero(pending)[sims >= cut]
            sub_ass[hits] = cid
        assigned[leftover] = sub_ass
    conn.executemany(
        "UPDATE faces SET cluster_id=? WHERE id=?",
        [(int(cid), face_id) for face_id, cid in zip(ids, assigned) if cid >= 0],
    )
    conn.commit()
    return created


def faces_payload(conn, media_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT f.id, f.x, f.y, f.w, f.h, f.score, f.person_id,
               p.name AS person_name
        FROM faces f
        LEFT JOIN people p ON p.id = f.person_id
        WHERE f.media_id=?
        ORDER BY f.score DESC, f.id
        """,
        (media_id,),
    ).fetchall()
    return [
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
        for r in rows
    ]


def scan_media_row(conn, library: Path, cache: Path, row, engine: FaceEngine) -> int:
    media_id = int(row["id"])
    path = locate_library_file(library, row["relpath"])
    if path is None:
        conn.execute("UPDATE media SET face_scanned=1 WHERE id=?", (media_id,))
        return 0
    maybe_fix_relpath(conn, library, row, path)
    kind = row["kind"] or kind_of(path) or "photo"
    packed: list[tuple[np.ndarray, FaceHit]] = []
    if kind == "video":
        raw: list[tuple[np.ndarray, FaceHit]] = []
        for t in sample_times(video_duration(path)):
            frame = ffmpeg_frame_bgr(path, t)
            if frame is None:
                continue
            for hit in engine.detect(frame):
                raw.append((frame, hit))
        cut = max(engine.threshold, 0.55)
        for frame, hit in raw:
            if any(float(np.dot(hit.embedding, other.embedding)) >= cut for _, other in packed):
                continue
            packed.append((frame, hit))
    else:
        image = load_bgr(path)
        if image is not None:
            packed = [(image, hit) for hit in engine.detect(image)]
    conn.execute("DELETE FROM faces WHERE media_id=?", (media_id,))
    added = 0
    for frame, hit in packed:
        cur = conn.execute(
            """
            INSERT INTO faces (
                media_id, x, y, w, h, score, embedding, dim, engine,
                person_id, cluster_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                media_id,
                float(hit.x),
                float(hit.y),
                float(hit.w),
                float(hit.h),
                float(hit.score),
                hit.embedding.astype(np.float32).tobytes(),
                int(hit.embedding.size),
                engine.name,
                now_iso(),
            ),
        )
        face_id = int(cur.lastrowid)
        try:
            save_face_thumb(frame, hit, face_thumb_file(cache, face_id))
        except Exception:
            pass
        added += 1
    conn.execute("UPDATE media SET face_scanned=1 WHERE id=?", (media_id,))
    return added


def scan_one_media(
    conn,
    library: Path,
    cache: Path,
    media_id: int,
    force: bool = False,
) -> dict:
    row = conn.execute(
        "SELECT id, relpath, kind, face_scanned FROM media WHERE id=? AND present=1",
        (media_id,),
    ).fetchone()
    if row is None:
        raise ValueError("média introuvable")
    if int(row["face_scanned"] or 0) and not force:
        return {
            "face_scanned": 1,
            "added": 0,
            "matched": 0,
            "faces": faces_payload(conn, media_id),
        }
    if locate_library_file(library, row["relpath"]) is None:
        raise ValueError("fichier absent du NAS")
    engine = get_engine(cache)
    _set_engine_meta(conn, engine)
    added = scan_media_row(conn, library, cache, row, engine)
    conn.commit()
    matched = match_unlabeled(conn, engine.threshold, media_id=media_id)
    recluster(conn, engine.threshold)
    return {
        "face_scanned": 1,
        "added": added,
        "matched": matched,
        "faces": faces_payload(conn, media_id),
        "engine": engine.name,
    }


def scan_faces(
    conn,
    library: Path,
    cache: Path,
    year: int | None = None,
    limit: int | None = None,
    progress: Progress | None = None,
) -> dict:
    sql = """
        SELECT id, relpath, kind FROM media
        WHERE present=1 AND face_scanned=0
    """
    params: list = []
    if year is not None:
        sql += " AND year=?"
        params.append(year)
    sql += " ORDER BY taken_at DESC, relpath"
    rows = conn.execute(sql, params).fetchall()
    if limit is not None:
        rows = rows[: max(0, limit)]
    total = len(rows)
    added = 0
    photos = 0

    def report(done: int, msg: str, code: str = "", fields: dict | None = None) -> None:
        if progress:
            progress(done, total if total else None, msg, code, fields)

    threshold = matching_threshold(conn)
    report(0, "Rattachement des visages aux personnes nommées", "prog.facesAttach")
    matched = match_unlabeled(conn, threshold)

    if rows:
        engine = get_engine(cache)
        _set_engine_meta(conn, engine)
        threshold = engine.threshold
        for i, row in enumerate(rows, start=1):
            media_id = int(row["id"])
            try:
                added += scan_media_row(conn, library, cache, row, engine)
                photos += 1
            except Exception as exc:
                conn.execute("UPDATE media SET face_scanned=1 WHERE id=?", (media_id,))
                report(i, f"{row['relpath']} : {exc.__class__.__name__}")
            if i % 10 == 0:
                conn.commit()
                report(i, row["relpath"])
        conn.commit()
        matched += match_unlabeled(conn, threshold)
        clusters = recluster(conn, threshold)
        report(
            total,
            f"Visages : {added} détectés, {matched} rattachés, {clusters} groupes",
            "prog.facesDone",
            {"added": added, "matched": matched, "clusters": clusters},
        )
        engine_name = engine.name
    else:
        clusters = 0
        report(
            matched,
            f"Aucun nouveau fichier ; {matched} visage"
            f"{'' if matched == 1 else 's'} rattaché"
            f"{'' if matched == 1 else 's'} aux personnes nommées",
            "prog.facesNone",
            {"n": matched},
        )
        engine_name = "match"

    return {
        "media": photos,
        "faces": added,
        "matched": matched,
        "clusters": clusters,
        "engine": engine_name,
        "total": total,
    }


def _get_or_create_person(conn, name: str) -> tuple[int, str]:
    name = " ".join(name.split())
    if not name:
        raise ValueError("nom vide")
    row = conn.execute(
        "SELECT id, name FROM people WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if row:
        return int(row["id"]), row["name"]
    try:
        cur = conn.execute(
            "INSERT INTO people(name, created_at) VALUES (?, ?)",
            (name, now_iso()),
        )
        return int(cur.lastrowid), name
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT id, name FROM people WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row:
            return int(row["id"]), row["name"]
        raise


def name_cluster(conn, cluster_id: int, name: str) -> dict:
    """Assigne un prénom à tout le cluster. Instantané (pas de match global)."""
    with _write_lock:
        person_id, name = _get_or_create_person(conn, name)
        conn.execute(
            "UPDATE faces SET person_id=?, cluster_id=NULL WHERE cluster_id=?",
            (person_id, cluster_id),
        )
        conn.commit()
    return {
        "person_id": person_id,
        "name": name,
        "matched": 0,
        "clusters": 0,
    }


def _normalize_face_ids(face_ids: list[int], *, cap: int = 400) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for raw in face_ids:
        fid = int(raw)
        if fid in seen:
            continue
        seen.add(fid)
        ids.append(fid)
        if len(ids) > cap:
            raise ValueError(f"trop de visages (max {cap})")
    if not ids:
        raise ValueError("aucun visage")
    return ids


def name_faces_many(conn, face_ids: list[int], name: str) -> dict:
    """Nomme seulement les visages indiqués, pas tout un cluster."""
    ids = _normalize_face_ids(face_ids)
    with _write_lock:
        person_id, name = _get_or_create_person(conn, name)
        qmarks = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE faces SET person_id=?, cluster_id=NULL WHERE id IN ({qmarks})",
            [person_id, *ids],
        )
        named = conn.execute(
            f"SELECT COUNT(*) FROM faces WHERE person_id=? AND id IN ({qmarks})",
            [person_id, *ids],
        ).fetchone()[0]
        conn.commit()
    return {
        "person_id": person_id,
        "name": name,
        "named": int(named),
        "matched": 0,
        "clusters": 0,
    }


def name_face(conn, face_id: int, name: str) -> dict:
    name = " ".join(name.split())
    if not name:
        return unname_face(conn, face_id)
    with _write_lock:
        person_id, name = _get_or_create_person(conn, name)
        conn.execute(
            "UPDATE faces SET person_id=?, cluster_id=NULL WHERE id=?",
            (person_id, face_id),
        )
        conn.commit()
    return {
        "person_id": person_id,
        "name": name,
        "matched": 0,
        "clusters": 0,
        "face_id": face_id,
    }


def _prune_empty_person(conn, person_id: int | None) -> None:
    if not person_id:
        return
    leftover = conn.execute(
        "SELECT COUNT(*) FROM faces WHERE person_id=?", (person_id,)
    ).fetchone()[0]
    if leftover == 0:
        conn.execute("DELETE FROM people WHERE id=?", (person_id,))


def unname_face(conn, face_id: int) -> dict:
    with _write_lock:
        row = conn.execute(
            "SELECT person_id FROM faces WHERE id=?", (face_id,)
        ).fetchone()
        old_id = int(row["person_id"]) if row and row["person_id"] is not None else None
        cluster_id = _next_cluster_id(conn)
        conn.execute(
            "UPDATE faces SET person_id=NULL, cluster_id=? WHERE id=?",
            (cluster_id, face_id),
        )
        _prune_empty_person(conn, old_id)
        conn.commit()
    return {
        "face_id": face_id,
        "name": None,
        "person_id": None,
        "matched": 0,
        "clusters": 0,
    }


def unname_faces_many(conn, face_ids: list[int]) -> dict:
    """Retire le prénom des visages indiqués (erreurs de regroupement)."""
    ids = _normalize_face_ids(face_ids)
    with _write_lock:
        old_ids: set[int] = set()
        next_cluster = _next_cluster_id(conn)
        for fid in ids:
            row = conn.execute(
                "SELECT person_id FROM faces WHERE id=?", (fid,)
            ).fetchone()
            if row is None:
                continue
            if row["person_id"] is not None:
                old_ids.add(int(row["person_id"]))
            conn.execute(
                "UPDATE faces SET person_id=NULL, cluster_id=? WHERE id=?",
                (next_cluster, fid),
            )
            next_cluster += 1
        for pid in old_ids:
            _prune_empty_person(conn, pid)
        conn.commit()
    return {
        "unnamed": len(ids),
        "name": None,
        "matched": 0,
        "clusters": 0,
    }


def rename_person(conn, person_id: int, new_name: str) -> dict:
    new_name = " ".join(new_name.split())
    if not new_name:
        raise ValueError("nom vide")
    with _write_lock:
        row = conn.execute(
            "SELECT id, name FROM people WHERE id=?", (person_id,)
        ).fetchone()
        if row is None:
            raise ValueError("personne introuvable")
        if row["name"] == new_name:
            return {"person_id": person_id, "name": new_name, "merged": False}
        existing = conn.execute(
            "SELECT id, name FROM people WHERE name = ? COLLATE NOCASE AND id != ?",
            (new_name, person_id),
        ).fetchone()
        if existing:
            dest_id = int(existing["id"])
            conn.execute(
                "UPDATE faces SET person_id=? WHERE person_id=?",
                (dest_id, person_id),
            )
            conn.execute("DELETE FROM people WHERE id=?", (person_id,))
            conn.commit()
            return {
                "person_id": dest_id,
                "name": existing["name"],
                "merged": True,
                "matched": 0,
                "clusters": 0,
            }
        conn.execute("UPDATE people SET name=? WHERE id=?", (new_name, person_id))
        conn.commit()
        return {"person_id": person_id, "name": new_name, "merged": False}


def merge_people(conn, keep_id: int, absorb_id: int) -> dict:
    """Tous les visages de `absorb_id` prennent le prénom de `keep_id`."""
    if keep_id == absorb_id:
        raise ValueError("choisissez deux prénoms différents")
    with _write_lock:
        keep = conn.execute("SELECT id, name FROM people WHERE id=?", (keep_id,)).fetchone()
        absorb = conn.execute("SELECT id, name FROM people WHERE id=?", (absorb_id,)).fetchone()
        if keep is None or absorb is None:
            raise ValueError("personne introuvable")
        moved = conn.execute(
            "UPDATE faces SET person_id=? WHERE person_id=?",
            (keep_id, absorb_id),
        ).rowcount
        conn.execute("DELETE FROM people WHERE id=?", (absorb_id,))
        conn.commit()
    return {
        "person_id": keep_id,
        "name": keep["name"],
        "absorbed_id": absorb_id,
        "absorbed_name": absorb["name"],
        "moved": int(moved or 0),
        "merged": True,
    }


def delete_person(conn, person_id: int) -> dict:
    with _write_lock:
        row = conn.execute("SELECT id FROM people WHERE id=?", (person_id,)).fetchone()
        if row is None:
            raise ValueError("personne introuvable")
        cluster_id = _next_cluster_id(conn)
        conn.execute(
            "UPDATE faces SET person_id=NULL, cluster_id=? WHERE person_id=?",
            (cluster_id, person_id),
        )
        conn.execute("DELETE FROM people WHERE id=?", (person_id,))
        conn.commit()
    return {"deleted": True, "matched": 0, "clusters": 0}


def people_for_filters(conn) -> list[dict]:
    """Personnes avec au moins un visage sur un fichier encore présent."""
    rows = conn.execute(
        """
        SELECT p.id, p.name, COUNT(f.id) AS count,
               MIN(m.year) AS year_min, MAX(m.year) AS year_max
        FROM people p
        JOIN faces f ON f.person_id = p.id
        JOIN media m ON m.id = f.media_id AND m.present = 1
        GROUP BY p.id
        ORDER BY p.name COLLATE NOCASE
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "name": r["name"],
                "count": int(r["count"]),
                "year_min": int(r["year_min"]) if r["year_min"] is not None else None,
                "year_max": int(r["year_max"]) if r["year_max"] is not None else None,
            }
        )
    return out


def person_faces_payload(
    conn, person_id: int, offset: int = 0, limit: int = 200
) -> dict:
    """Visages d’une personne encore présents, pour relecture / correction."""
    from photo_library.copies import live_media_id_for_face

    person = conn.execute(
        "SELECT id, name FROM people WHERE id=?", (person_id,)
    ).fetchone()
    if person is None:
        raise ValueError("personne introuvable")
    total = conn.execute(
        """
        SELECT COUNT(*) FROM faces f
        JOIN media m ON m.id = f.media_id
        WHERE f.person_id=? AND m.present=1
        """,
        (person_id,),
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT f.id, f.media_id, f.score, m.size, m.taken_at, m.dhash,
               m.present, m.relpath, m.year
        FROM faces f
        JOIN media m ON m.id = f.media_id
        WHERE f.person_id=? AND m.present=1
        ORDER BY f.score DESC, f.id
        LIMIT ? OFFSET ?
        """,
        (person_id, limit, offset),
    ).fetchall()
    faces = []
    for row in rows:
        item = dict(row)
        live_id = live_media_id_for_face(conn, item)
        if live_id is None:
            continue
        faces.append(
            {
                "id": int(item["id"]),
                "media_id": live_id,
                "score": item["score"],
            }
        )
    return {
        "id": int(person["id"]),
        "name": person["name"],
        "total": int(total),
        "offset": offset,
        "faces": faces,
    }
