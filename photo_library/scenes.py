"""Prototype : étiquettes paysage / bâtiment (heuristique + MobileNet optionnel)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image

from photo_library.thumbs import ensure_heif, preview_file, thumb_file

Progress = Callable[[int, int | None, str], None]

SCENE_DEFS: list[tuple[str, str, str]] = [
    ("plage", "landscape", "Plage"),
    ("montagne", "landscape", "Montagne"),
    ("foret", "landscape", "Forêt"),
    ("lac", "landscape", "Lac"),
    ("neige", "landscape", "Neige"),
    ("campagne", "landscape", "Campagne"),
    ("ciel", "landscape", "Ciel"),
    ("ville", "building", "Ville"),
    ("eglise", "building", "Église / religieux"),
    ("pont", "building", "Pont"),
    ("chateau", "building", "Château / palais"),
    ("maison", "building", "Maison"),
    ("monument", "building", "Monument"),
    ("interieur", "building", "Intérieur"),
]
SCENE_KIND = {tag: kind for tag, kind, _label in SCENE_DEFS}
SCENE_LABEL = {tag: label for tag, _kind, label in SCENE_DEFS}

# ImageNet-1k (index) → étiquette galerie. MobileNetV2 si le .onnx est présent.
IMAGENET_SCENE: dict[int, str] = {
    425: "maison",
    442: "eglise",
    449: "maison",
    460: "pont",
    483: "chateau",
    497: "eglise",
    526: "ville",
    546: "monument",
    580: "maison",
    663: "eglise",
    698: "chateau",
    718: "pont",
    762: "interieur",
    825: "monument",
    832: "pont",
    839: "pont",
    853: "maison",
    873: "monument",
    888: "pont",
    970: "montagne",
    972: "montagne",
    975: "lac",
    976: "montagne",
    978: "plage",
    979: "campagne",
    980: "montagne",
    984: "campagne",
    987: "campagne",
}

MOBILENET_NAME = "mobilenetv2-12.onnx"
MOBILENET_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/"
    "classification/mobilenet/model/mobilenetv2-12.onnx"
)
ONNX_MIN_SCORE = 0.12
HEURISTIC_MIN = 0.22
_onnx_session = None
_onnx_tried = False


def model_path(cache: Path) -> Path:
    return cache / "models" / MOBILENET_NAME


def ensure_model(cache: Path, progress: Progress | None = None) -> Path | None:
    dest = model_path(cache)
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        return dest
    return None


def _onnx_session_for(cache: Path, progress: Progress | None = None):
    global _onnx_session, _onnx_tried
    if _onnx_tried:
        return _onnx_session
    _onnx_tried = True
    path = ensure_model(cache, progress)
    if path is None:
        return None
    try:
        import onnxruntime as ort

        _onnx_session = ort.InferenceSession(
            str(path), providers=["CPUExecutionProvider"]
        )
    except Exception:
        _onnx_session = None
    return _onnx_session


def _rgb_small(img: Image.Image, size: tuple[int, int] = (160, 120)) -> np.ndarray:
    rgb = img.convert("RGB")
    rgb = rgb.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(rgb, dtype=np.uint8)


def heuristic_tags(img: Image.Image) -> list[tuple[str, float]]:
    """Prototype visuel sans réseau : ciel, vert, neige, bords (bâtiment)."""
    arr = _rgb_small(img)
    h, _w, _ = arr.shape
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)
    top, _mid, bot = np.split(arr, 3, axis=0)
    tr, tg, tb = [c.astype(np.float32) for c in (top[:, :, 0], top[:, :, 1], top[:, :, 2])]
    br, bg, bb = [c.astype(np.float32) for c in (bot[:, :, 0], bot[:, :, 1], bot[:, :, 2])]
    top_blue = float(((tb > tr + 18) & (tb > tg + 8)).mean())
    bot_green = float(((bg > br + 12) & (bg > bb + 4)).mean())
    bot_beige = float(((br > 140) & (bg > 120) & (bb < bg) & (br > bb + 15)).mean())
    bright = float(((r + g + b) / 3 > 200).mean())
    green = float(((g > r + 10) & (g > b + 5)).mean())
    gray = np.abs(r - g) + np.abs(g - b) + np.abs(r - b)
    grayish = float((gray < 35).mean())
    lum = (r + g + b) / 3
    gy = float(np.abs(np.diff(lum, axis=0)).mean())
    gx = float(np.abs(np.diff(lum, axis=1)).mean())
    edges = (gx + gy) / 2

    scores: dict[str, float] = {}
    if top_blue > 0.22 and bot_beige > 0.18:
        scores["plage"] = min(0.85, 0.35 + top_blue + bot_beige * 0.4)
    if top_blue > 0.28 and bot_green > 0.18:
        scores["campagne"] = min(0.8, 0.3 + top_blue * 0.4 + bot_green)
        scores["ciel"] = min(0.7, top_blue)
    if green > 0.35 and top_blue < 0.45:
        scores["foret"] = min(0.82, 0.25 + green)
    if top_blue > 0.2 and bot_green < 0.12 and grayish > 0.25 and bot_beige < 0.2:
        scores["montagne"] = min(0.78, 0.28 + top_blue)
        scores["lac"] = min(0.55, top_blue * 0.8)
    if bright > 0.55 and grayish > 0.4:
        scores["neige"] = min(0.88, 0.3 + bright)
    if edges > 9 and green < 0.28 and top_blue < 0.35:
        scores["ville"] = min(0.8, 0.2 + min(edges / 40, 0.5))
        if grayish > 0.3:
            scores["monument"] = min(0.65, 0.2 + grayish * 0.4)
    if green < 0.15 and top_blue < 0.12 and lum.mean() < 110 and edges > 6:
        scores["interieur"] = min(0.7, 0.25 + (1 - top_blue))

    return [
        (tag, round(score, 3))
        for tag, score in sorted(scores.items(), key=lambda kv: -kv[1])
        if score >= HEURISTIC_MIN
    ][:3]


def _onnx_tags(img: Image.Image, session) -> list[tuple[str, float]]:
    rgb = img.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    chw = np.transpose(arr, (2, 0, 1))[None, ...]
    inp = session.get_inputs()[0]
    out = session.run(None, {inp.name: chw})[0].reshape(-1)
    out = out - out.max()
    exp = np.exp(out)
    prob = exp / exp.sum()
    scored: dict[str, float] = {}
    for idx in np.argsort(prob)[-8:][::-1]:
        tag = IMAGENET_SCENE.get(int(idx))
        if not tag:
            continue
        p = float(prob[int(idx)])
        if p < ONNX_MIN_SCORE:
            continue
        scored[tag] = max(scored.get(tag, 0.0), p)
    return sorted(scored.items(), key=lambda kv: -kv[1])[:3]


def classify_image(
    img: Image.Image, cache: Path | None = None, progress: Progress | None = None
) -> list[tuple[str, float]]:
    tags: list[tuple[str, float]] = []
    if cache is not None:
        session = _onnx_session_for(cache, progress)
        if session is not None:
            try:
                tags = _onnx_tags(img, session)
            except Exception:
                tags = []
    if not tags:
        tags = heuristic_tags(img)
    return tags


def _open_for_scene(path: Path) -> Image.Image | None:
    ensure_heif()
    try:
        img = Image.open(path)
        img.load()
        return ImageOps_exif(img)
    except Exception:
        return None


def ImageOps_exif(img: Image.Image) -> Image.Image:
    from PIL import ImageOps

    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def classify_path(
    path: Path, cache: Path | None = None, progress: Progress | None = None
) -> list[tuple[str, float]]:
    img = _open_for_scene(path)
    if img is None:
        return []
    try:
        return classify_image(img, cache=cache, progress=progress)
    finally:
        img.close()


def scenes_for_filters(
    conn, year: int | None = None, place: str | None = None
) -> list[dict]:
    sql = """
        SELECT s.tag, s.kind, COUNT(DISTINCT s.media_id) AS c
        FROM media_scenes s
        JOIN media m ON m.id = s.media_id AND m.present=1
        WHERE 1=1
    """
    params: list = []
    if year is not None:
        sql += " AND m.year=?"
        params.append(year)
    place = (place or "").strip()
    if place:
        sql += " AND m.place = ? COLLATE NOCASE"
        params.append(place)
    sql += " GROUP BY s.tag, s.kind ORDER BY c DESC, s.tag"
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "value": r["tag"],
            "label": SCENE_LABEL.get(r["tag"], r["tag"]),
            "kind": r["kind"],
            "count": int(r["c"]),
        }
        for r in rows
    ]


def scenes_for_media(conn, media_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT tag, kind, score FROM media_scenes
        WHERE media_id=? ORDER BY score DESC
        """,
        (media_id,),
    ).fetchall()
    return [
        {
            "tag": r["tag"],
            "kind": r["kind"],
            "label": SCENE_LABEL.get(r["tag"], r["tag"]),
            "score": r["score"],
        }
        for r in rows
    ]


def scene_catalog() -> list[dict]:
    return [
        {"value": tag, "label": label, "kind": kind}
        for tag, kind, label in SCENE_DEFS
    ]


def parse_scene_tag(tag: str) -> str:
    key = (tag or "").strip().lower()
    if key not in SCENE_KIND:
        raise ValueError("Étiquette inconnue (choisissez plage, ville, église…).")
    return key


def _present_media_ids(conn, media_ids: list[int]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for raw in media_ids or []:
        try:
            mid = int(raw)
        except (TypeError, ValueError):
            continue
        if mid in seen:
            continue
        seen.add(mid)
        row = conn.execute(
            "SELECT id FROM media WHERE id=? AND present=1", (mid,)
        ).fetchone()
        if row:
            out.append(mid)
    return out


def add_scenes(conn, media_ids: list[int], tag: str) -> dict:
    tag = parse_scene_tag(tag)
    kind = SCENE_KIND[tag]
    ids = _present_media_ids(conn, media_ids)
    if not ids:
        raise ValueError("Aucune photo à étiqueter.")
    for mid in ids:
        conn.execute(
            "INSERT OR REPLACE INTO media_scenes (media_id, tag, kind, score) VALUES (?,?,?,?)",
            (mid, tag, kind, 1.0),
        )
        conn.execute("UPDATE media SET scene_scanned=1 WHERE id=?", (mid,))
    conn.commit()
    return {
        "ok": True,
        "tag": tag,
        "label": SCENE_LABEL[tag],
        "updated": len(ids),
    }


def remove_scenes(conn, media_ids: list[int], tag: str) -> dict:
    tag = parse_scene_tag(tag)
    ids = _present_media_ids(conn, media_ids)
    if not ids:
        raise ValueError("Aucune photo à corriger.")
    qmarks = ",".join("?" * len(ids))
    conn.execute(
        f"DELETE FROM media_scenes WHERE tag=? AND media_id IN ({qmarks})",
        [tag, *ids],
    )
    conn.commit()
    return {
        "ok": True,
        "tag": tag,
        "label": SCENE_LABEL[tag],
        "updated": len(ids),
    }


def _scope_sql(
    year: int | None, place: str | None, *, alias: str = "m"
) -> tuple[str, list]:
    sql = f" {alias}.present=1"
    params: list = []
    if year is not None:
        sql += f" AND {alias}.year=?"
        params.append(year)
    place = (place or "").strip()
    if place:
        sql += f" AND {alias}.place = ? COLLATE NOCASE"
        params.append(place)
    return sql, params


def media_for_scene(
    conn,
    tag: str,
    *,
    offset: int = 0,
    limit: int = 200,
    year: int | None = None,
    place: str | None = None,
) -> dict:
    tag = parse_scene_tag(tag)
    scope, params = _scope_sql(year, place)
    total = int(
        conn.execute(
            f"""
            SELECT COUNT(DISTINCT m.id)
            FROM media m
            JOIN media_scenes s ON s.media_id = m.id AND s.tag=?
            WHERE {scope}
            """,
            [tag, *params],
        ).fetchone()[0]
    )
    rows = conn.execute(
        f"""
        SELECT m.id, m.relpath, m.mtime_ns, m.thumb_ok, m.kind
        FROM media m
        JOIN media_scenes s ON s.media_id = m.id AND s.tag=?
        WHERE {scope}
        ORDER BY m.taken_at DESC, m.id DESC
        LIMIT ? OFFSET ?
        """,
        [tag, *params, limit, offset],
    ).fetchall()
    return {
        "tag": tag,
        "label": SCENE_LABEL[tag],
        "total": total,
        "offset": offset,
        "items": [
            {
                "id": int(r["id"]),
                "relpath": r["relpath"],
                "mtime_ns": r["mtime_ns"],
                "thumb_ok": r["thumb_ok"],
                "kind": r["kind"],
            }
            for r in rows
        ],
    }


def untagged_media(
    conn,
    *,
    year: int | None = None,
    place: str | None = None,
    offset: int = 0,
    limit: int = 80,
) -> dict:
    scope, params = _scope_sql(year, place)
    total = int(
        conn.execute(
            f"""
            SELECT COUNT(*) FROM media m
            WHERE {scope}
            AND m.id NOT IN (SELECT media_id FROM media_scenes)
            """,
            params,
        ).fetchone()[0]
    )
    rows = conn.execute(
        f"""
        SELECT m.id, m.relpath, m.mtime_ns, m.thumb_ok, m.kind
        FROM media m
        WHERE {scope}
        AND m.id NOT IN (SELECT media_id FROM media_scenes)
        ORDER BY m.taken_at DESC, m.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return {
        "total": total,
        "offset": offset,
        "items": [
            {
                "id": int(r["id"]),
                "relpath": r["relpath"],
                "mtime_ns": r["mtime_ns"],
                "thumb_ok": r["thumb_ok"],
                "kind": r["kind"],
            }
            for r in rows
        ],
    }


def scenes_status(
    conn, *, year: int | None = None, place: str | None = None
) -> dict:
    scope, params = _scope_sql(year, place)
    pending = int(
        conn.execute(
            f"SELECT COUNT(*) FROM media m WHERE {scope} AND m.scene_scanned=0",
            params,
        ).fetchone()[0]
    )
    scanned = int(
        conn.execute(
            f"SELECT COUNT(*) FROM media m WHERE {scope} AND m.scene_scanned=1",
            params,
        ).fetchone()[0]
    )
    tagged = int(
        conn.execute(
            f"""
            SELECT COUNT(DISTINCT m.id) FROM media m
            JOIN media_scenes s ON s.media_id = m.id
            WHERE {scope}
            """,
            params,
        ).fetchone()[0]
    )
    untagged = int(
        conn.execute(
            f"""
            SELECT COUNT(*) FROM media m
            WHERE {scope}
            AND m.id NOT IN (SELECT media_id FROM media_scenes)
            """,
            params,
        ).fetchone()[0]
    )
    return {
        "pending": pending,
        "scanned": scanned,
        "tagged": tagged,
        "untagged": untagged,
    }


def scenes_workspace(
    conn,
    *,
    year: int | None = None,
    place: str | None = None,
    limit: int = 80,
) -> dict:
    tags = scenes_for_filters(conn, year=year, place=place)
    year_scope, year_params = _scope_sql(year, None)
    place_rows = conn.execute(
        f"""
        SELECT DISTINCT m.place FROM media m
        WHERE {year_scope}
        AND m.place IS NOT NULL AND TRIM(m.place) != ''
        ORDER BY m.place COLLATE NOCASE
        """,
        year_params,
    ).fetchall()
    return {
        "status": scenes_status(conn, year=year, place=place),
        "catalog": scene_catalog(),
        "tags": tags,
        "untagged": untagged_media(
            conn, year=year, place=place, offset=0, limit=limit
        ),
        "places": [r["place"] for r in place_rows],
        "year": year,
        "place": place or None,
    }


def scan_scenes(
    conn,
    library: Path,
    cache: Path,
    year: int | None = None,
    place: str | None = None,
    limit: int | None = None,
    progress: Progress | None = None,
) -> dict:
    sql = """
        SELECT id, relpath, kind, thumb_ok FROM media
        WHERE present=1 AND scene_scanned=0
    """
    params: list = []
    if year is not None:
        sql += " AND year=?"
        params.append(year)
    place = (place or "").strip()
    if place:
        sql += " AND place = ? COLLATE NOCASE"
        params.append(place)
    sql += " ORDER BY taken_at DESC, relpath"
    rows = conn.execute(sql, params).fetchall()
    if limit is not None:
        rows = rows[: max(0, limit)]
    total = len(rows)
    tagged = 0
    skipped = 0

    def report(done: int, msg: str, code: str = "", fields: dict | None = None) -> None:
        if progress:
            progress(done, total if total else None, msg, code, fields)

    report(0, "Reconnaissance des scènes…", "prog.scenes")
    from photo_library.locate import locate_library_file

    for i, row in enumerate(rows, start=1):
        media_id = int(row["id"])
        thumb = thumb_file(cache, media_id)
        preview = preview_file(cache, media_id)
        src: Path | None = None
        if thumb.is_file():
            src = thumb
        elif preview.is_file():
            src = preview
        else:
            src = locate_library_file(library, row["relpath"])
        tags: list[tuple[str, float]] = []
        if src is not None and src.is_file():
            tags = classify_path(src, cache=cache, progress=progress)
        conn.execute("DELETE FROM media_scenes WHERE media_id=?", (media_id,))
        if tags:
            tagged += 1
            conn.executemany(
                "INSERT INTO media_scenes (media_id, tag, kind, score) VALUES (?,?,?,?)",
                [
                    (media_id, tag, SCENE_KIND.get(tag, "landscape"), float(score))
                    for tag, score in tags
                    if tag in SCENE_KIND
                ],
            )
        else:
            skipped += 1
        conn.execute("UPDATE media SET scene_scanned=1 WHERE id=?", (media_id,))
        if i % 20 == 0:
            conn.commit()
        report(i, Path(row["relpath"]).name)
    conn.commit()
    report(
        total,
        f"Scènes : {tagged} photo(s) étiquetée(s)",
        "prog.scenesDone",
        {"n": tagged},
    )
    engine = "mobilenet" if _onnx_session is not None else "heuristique"
    return {
        "scanned": total,
        "tagged": tagged,
        "untagged": skipped,
        "engine": engine,
        "year": year,
        "place": place or None,
    }
