"""Parsing local des films/séries/clips et enrichissement Open Data Wikidata / Wikipédia (CC0)."""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

MEDIA_TYPES = ("movie", "series", "clip", "documentary", "other")

CATEGORIES = (
    "policier",
    "drame",
    "comedie",
    "action",
    "thriller",
    "sf",
    "fantastique",
    "horreur",
    "aventure",
    "animation",
    "romance",
    "documentaire",
    "historique",
    "guerre",
    "western",
    "musical",
    "biopic",
    "famille",
    "espionnage",
    "mystere",
    "clip",
)

_USER_AGENT = "GalerieMedias/4.0 (Open Source MIT; Wikidata metadata lookup)"

_SERIES_RE = re.compile(r"(?i)\bS(\d{1,2})[\s._-]*E(\d{1,3})\b|\b(\d{1,2})x(\d{2})\b")
_LEADING_YEAR_RE = re.compile(r"^\s*((?:19|20)\d{2})\s*[-–._]+\s*(.+)$")
_TRAILING_YEAR_RE = re.compile(r"^(.+?)\s*(?:[-–]\s*|\(\s*|\[\s*)((?:19|20)\d{2})\s*(?:\)|\])?\s*$")
_ANY_YEAR_RE = re.compile(r"(?:^|[\s._(\[-])((?:19|20)\d{2})(?:$|[\s._)\]-])")
_RELEASE_NOISE_RE = re.compile(
    r"(?i)\b("
    r"french|truefrench|vff|vfq|vostfr|vost\s*fr|vost|subfrench|multi|"
    r"dvdrip|bdrip|brrip|bluray|blu-ray|webrip|web-dl|webdl|hdtv|hdrip|hdlight|"
    r"repack|proper|remastered|extended|unrated|directors\.?cut|"
    r"xvid|divx|x264|h264|x265|h265|hevc|avc|ac3|dts|aac|mp3|"
    r"1080p|720p|2160p|4k|uhd|1cd|2cd|cd\d+|part\d+|"
    r"lyrics|official\s+video|clip\s+officiel|hd|hq"
    r")\b.*$"
)
_BRACKET_NOISE_RE = re.compile(r"(?i)\[(?:[^\]]{1,40})\]")
_CLIP_HINTS_RE = re.compile(r"(?i)\b(lyrics|official\s+video|music\s+video|clip)\b")

# Correspondances QID Wikidata P31 (nature de l'élément) -> type
_WIKIDATA_TYPE_MAP = {
    "Q11424": "movie",  # film
    "Q24862": "movie",  # court métrage
    "Q202866": "movie",  # film d'animation
    "Q506240": "movie",  # téléfilm
    "Q24856": "movie",  # série de films
    "Q539841": "series",  # série télévisée
    "Q117467246": "series",  # série télévisée d'animation
    "Q1259759": "series",  # mini-série
    "Q581714": "series",  # série d'animation
    "Q93204": "documentary",  # film documentaire
    "Q4164344": "documentary",  # série documentaire
    "Q193977": "clip",  # clip vidéo
}

# Correspondances QID Wikidata P136 (genre) -> catégorie normalisée
_WIKIDATA_GENRE_QID = {
    "Q959790": "policier",  # film policier
    "Q130232": "drame",  # film dramatique
    "Q21010853": "drame",  # série dramatique
    "Q157443": "comedie",  # film comique
    "Q859369": "comedie",  # comédie dramatique
    "Q40831": "comedie",  # comédie
    "Q188473": "action",  # film d'action
    "Q2484376": "thriller",  # thriller
    "Q1341051": "thriller",  # thriller psychologique
    "Q471839": "sf",  # film de science-fiction
    "Q157394": "fantastique",  # film fantastique
    "Q200092": "horreur",  # film d'horreur
    "Q319221": "aventure",  # film d'aventure
    "Q202866": "animation",  # film d'animation
    "Q1054574": "romance",  # film d'amour
    "Q860626": "romance",  # comédie romantique
    "Q93204": "documentaire",  # documentaire
    "Q17013749": "historique",  # film historique
    "Q369747": "guerre",  # film de guerre
    "Q172980": "western",  # western
    "Q842256": "musical",  # film musical
    "Q645928": "biopic",  # film biographique
    "Q1361932": "famille",  # film familial
    "Q2297927": "espionnage",  # film d'espionnage
    "Q1200678": "mystere",  # film à énigme / mystère
    "Q590103": "thriller",  # film noir
}

_GENRE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("policier", ("policier", "crime", "detective", "gangster", "noir", "polar", "krimi")),
    ("thriller", ("thriller", "suspense", "angoisse")),
    ("comedie", ("comedie", "comedy", "comique", "humour", "satire", "burlesque", "komodie")),
    ("drame", ("drame", "drama", "dramatique")),
    ("action", ("action", "arts martiaux", "super-heros", "superhero")),
    ("sf", ("science-fiction", "science fiction", "sci-fi", "cyberpunk", "dystopie", "anticipation")),
    ("fantastique", ("fantastique", "fantasy", "merveilleux", "surnaturel")),
    ("horreur", ("horreur", "horror", "epouvante", "slasher", "zombie")),
    ("aventure", ("aventure", "adventure", "cape et epee")),
    ("animation", ("animation", "anime", "dessin anime")),
    ("romance", ("romance", "romantique", "amour", "love")),
    ("documentaire", ("documentaire", "documentary")),
    ("historique", ("historique", "historical", "peplum", "epoque")),
    ("guerre", ("guerre", "war", "militaire")),
    ("western", ("western",)),
    ("musical", ("musical", "musique", "chanson", "concert", "opera")),
    ("biopic", ("biopic", "biographique", "biographical")),
    ("famille", ("famille", "familial", "family", "jeunesse", "enfants")),
    ("espionnage", ("espionnage", "spy", "espionage")),
    ("mystere", ("mystere", "mystery", "enigme")),
    ("clip", ("clip", "music video")),
)

_FOLDER_TYPE_HINTS = {
    "series": "series",
    "serie": "series",
    "tv": "series",
    "clips": "clip",
    "clip": "clip",
    "musique": "clip",
    "music": "clip",
    "documentaires": "documentary",
    "documentaire": "documentary",
    "docs": "documentary",
}


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(plain.lower().split())


def normalize_media_type(value: str | None) -> str:
    low = _fold(value or "")
    if low in MEDIA_TYPES:
        return low
    aliases = {
        "film": "movie",
        "films": "movie",
        "movies": "movie",
        "serie": "series",
        "series": "series",
        "tv": "series",
        "clip": "clip",
        "clips": "clip",
        "documentaire": "documentary",
        "doc": "documentary",
        "autre": "other",
    }
    return aliases.get(low, "movie")


def normalize_category(value: str | None) -> str | None:
    folded = _fold(value or "")
    if not folded:
        return None
    if folded in CATEGORIES:
        return folded
    for slug, needles in _GENRE_KEYWORDS:
        if any(needle in folded for needle in needles):
            return slug
    return None


def normalize_categories(values: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or ():
        slug = normalize_category(str(raw))
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def parse_local_metadata(
    relpath: str,
    *,
    duration_s: float | None = None,
    size: int | None = None,
    tags: dict[str, str] | None = None,
) -> dict:
    """Extrait titre propre, année, type (film/série/clip) et catégories depuis chemin + tags."""
    path = Path(relpath)
    raw_name = path.name if path.suffix == "" else path.stem
    parts = [p for p in path.parts[:-1] if p not in {".", ""}]

    media_type = "movie"
    season: int | None = None
    episode: int | None = None
    year: int | None = None
    director = ""
    categories: list[str] = []

    for folder in parts:
        f = _fold(folder)
        if f in _FOLDER_TYPE_HINTS:
            media_type = _FOLDER_TYPE_HINTS[f]
        cat = normalize_category(folder)
        if cat and cat not in categories:
            categories.append(cat)

    cleaned = raw_name.replace("_amp_", " & ").replace("_", " ")
    # Dot-separated filenames like "1946.-.Frank.Capra.-.La.Vie.Est.Belle"
    if cleaned.count(".") >= 2:
        cleaned = re.sub(r"(?<!\b[A-Z])\.(?=[A-Za-z0-9À-ÿ(\-])", " ", cleaned)
    cleaned = _BRACKET_NOISE_RE.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split())

    sm = _SERIES_RE.search(cleaned)
    if sm:
        media_type = "series"
        season = int(sm.group(1) or sm.group(3))
        episode = int(sm.group(2) or sm.group(4))
        cleaned = cleaned[: sm.start()].strip(" -._")

    has_clip_hint = bool(_CLIP_HINTS_RE.search(cleaned))

    lm = _LEADING_YEAR_RE.match(cleaned)
    if lm:
        year = int(lm.group(1))
        cleaned = lm.group(2).strip()
        # Pattern: "Frank Capra - La Vie Est Belle (It's A Wonderful Life)"
        segs = [s.strip() for s in re.split(r"\s+-\s+", cleaned) if s.strip()]
        if len(segs) >= 2 and 1 <= len(segs[0].split()) <= 3 and len(segs[1]) >= 3:
            director = segs[0]
            cleaned = " - ".join(segs[1:])
    else:
        tm = _TRAILING_YEAR_RE.match(cleaned)
        if tm:
            year = int(tm.group(2))
            cleaned = tm.group(1).strip()

    cleaned = _RELEASE_NOISE_RE.sub("", cleaned).strip(" -._")

    if year is None:
        ym = _ANY_YEAR_RE.search(cleaned)
        if ym:
            year = int(ym.group(1))
            cleaned = (cleaned[: ym.start()] + " " + cleaned[ym.end() :]).strip(" -._()")

    # Retire les mentions "(T. Browning)" ou "(It's A Wonderful Life)" en fin de titre si le titre principal reste long
    short = re.sub(r"\s*\([^)]{2,50}\)\s*$", "", cleaned).strip(" -._")
    if len(short) >= 3:
        cleaned = short

    cleaned = " ".join(cleaned.split()).strip(" -._")
    title = cleaned or raw_name

    # Métadonnées intégrées au conteneur (MP4/MKV)
    if tags:
        if year is None:
            for key in ("date", "creation_time", "year"):
                raw_d = tags.get(key) or ""
                m = re.search(r"\b((?:19|20)\d{2})\b", raw_d)
                if m:
                    year = int(m.group(1))
                    break
        if tags.get("genre"):
            for part in re.split(r"[,;/]+", tags["genre"]):
                c = normalize_category(part)
                if c and c not in categories:
                    categories.append(c)

    # Heuristique clip musical (courtes vidéos musicales < 10 min ou fichiers petits avec indice)
    is_short_dur = duration_s is not None and 20 <= duration_s <= 660
    is_small_clip = (
        duration_s is None
        and size is not None
        and 1_000_000 <= size <= 95_000_000
        and (has_clip_hint or " - " in title)
    )
    if media_type == "movie" and (has_clip_hint or is_short_dur or is_small_clip):
        media_type = "clip"
    if media_type == "clip":
        for c in ("clip", "musical"):
            if c not in categories:
                categories.append(c)
    elif media_type == "documentary" and "documentaire" not in categories:
        categories.append("documentaire")

    return {
        "title": title,
        "media_type": media_type,
        "year": year,
        "season": season,
        "episode": episode,
        "director": director,
        "categories": categories,
    }


def _http_get_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _claim_ids(entity: dict, prop: str) -> list[str]:
    out: list[str] = []
    for claim in (entity.get("claims") or {}).get(prop) or []:
        try:
            qid = claim["mainsnak"]["datavalue"]["value"]["id"]
            if isinstance(qid, str) and qid:
                out.append(qid)
        except (KeyError, TypeError):
            continue
    return out


def _claim_year(entity: dict, prop: str = "P577") -> int | None:
    years: list[int] = []
    for claim in (entity.get("claims") or {}).get(prop) or []:
        try:
            raw = str(claim["mainsnak"]["datavalue"]["value"]["time"])
            m = re.match(r"^[+-]?(\d{4})-", raw)
            if m:
                y = int(m.group(1))
                if 1890 <= y <= 2100:
                    years.append(y)
        except (KeyError, TypeError, ValueError):
            continue
    return min(years) if years else None


def _entity_label(entity: dict, lang: str) -> str:
    labels = entity.get("labels") or {}
    for code in (lang, "fr", "en"):
        item = labels.get(code)
        if isinstance(item, dict) and item.get("value"):
            return str(item["value"]).strip()
    return ""


def _entity_desc(entity: dict, lang: str) -> str:
    descs = entity.get("descriptions") or {}
    for code in (lang, "fr", "en"):
        item = descs.get(code)
        if isinstance(item, dict) and item.get("value"):
            return str(item["value"]).strip()
    return ""


def fetch_wikidata_metadata(
    title: str,
    *,
    year: int | None = None,
    lang: str = "fr",
    media_type: str = "movie",
    fetcher: Callable[[str], dict] | None = None,
) -> dict | None:
    """Interroge Wikidata (CC0) + résumé Wikipédia (sans clé API) pour un film ou une série."""
    query = (title or "").strip()
    if len(query) < 2:
        return None
    lang = lang if lang in {"fr", "en", "es", "de"} else "fr"
    get_json = fetcher or _http_get_json

    search_params = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "format": "json",
            "language": lang,
            "uselang": lang,
            "type": "item",
            "limit": "6",
            "search": query,
        }
    )
    try:
        search_res = get_json(f"https://www.wikidata.org/w/api.php?{search_params}")
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None

    hits = [h.get("id") for h in (search_res.get("search") or []) if h.get("id")]
    if not hits:
        return None

    ent_params = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "format": "json",
            "ids": "|".join(hits),
            "props": "labels|descriptions|claims|sitelinks",
            "languages": f"{lang}|fr|en",
        }
    )
    try:
        ent_res = get_json(f"https://www.wikidata.org/w/api.php?{ent_params}")
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None

    entities = ent_res.get("entities") or {}
    best_id: str | None = None
    best_score = -1
    best_type = media_type

    for qid in hits:
        ent = entities.get(qid)
        if not isinstance(ent, dict):
            continue
        p31 = _claim_ids(ent, "P31")
        detected = None
        for cid in p31:
            if cid in _WIKIDATA_TYPE_MAP:
                detected = _WIKIDATA_TYPE_MAP[cid]
                break
        if detected is None:
            continue
        score = 10
        if detected == media_type:
            score += 4
        ent_year = _claim_year(ent, "P577") or _claim_year(ent, "P580")
        if year is not None and ent_year is not None:
            diff = abs(ent_year - year)
            if diff == 0:
                score += 12
            elif diff <= 1:
                score += 8
            elif diff <= 3:
                score += 2
            else:
                score -= 6
        lbl = _fold(_entity_label(ent, lang))
        if lbl == _fold(query):
            score += 6
        if score > best_score:
            best_score = score
            best_id = qid
            best_type = detected

    if best_id is None:
        return None

    chosen = entities[best_id]
    found_year = _claim_year(chosen, "P577") or _claim_year(chosen, "P580") or year
    genre_qids = _claim_ids(chosen, "P136")
    director_qids = _claim_ids(chosen, "P57")[:2]

    categories: list[str] = []
    unresolved_genres: list[str] = []
    for gq in genre_qids:
        mapped = _WIKIDATA_GENRE_QID.get(gq)
        if mapped:
            if mapped not in categories:
                categories.append(mapped)
        else:
            unresolved_genres.append(gq)

    extra_ids = list(dict.fromkeys(unresolved_genres[:8] + director_qids))
    director = ""
    if extra_ids:
        ex_params = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(extra_ids),
                "props": "labels",
                "languages": f"{lang}|fr|en",
            }
        )
        try:
            ex_res = get_json(f"https://www.wikidata.org/w/api.php?{ex_params}")
            ex_ents = ex_res.get("entities") or {}
            for gq in unresolved_genres:
                ent = ex_ents.get(gq)
                if isinstance(ent, dict):
                    cat = normalize_category(_entity_label(ent, lang))
                    if cat and cat not in categories:
                        categories.append(cat)
            dir_names = [
                _entity_label(ex_ents[dq], lang)
                for dq in director_qids
                if isinstance(ex_ents.get(dq), dict) and _entity_label(ex_ents[dq], lang)
            ]
            director = ", ".join(dir_names)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            pass

    if best_type == "documentary" and "documentaire" not in categories:
        categories.append("documentaire")
    if best_type == "clip" and "clip" not in categories:
        categories.append("clip")

    overview = _entity_desc(chosen, lang)
    sitelinks = chosen.get("sitelinks") or {}
    wiki_entry = sitelinks.get(f"{lang}wiki") or sitelinks.get("frwiki") or sitelinks.get("enwiki")
    if isinstance(wiki_entry, dict) and wiki_entry.get("title"):
        wiki_lang = str(wiki_entry.get("site") or f"{lang}wiki").replace("wiki", "")
        wiki_title = urllib.parse.quote(str(wiki_entry["title"]).replace(" ", "_"), safe="")
        try:
            summary = get_json(
                f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"
            )
            extract = str(summary.get("extract") or "").strip()
            if extract:
                overview = extract[:480].rstrip()
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            pass

    return {
        "wikidata_id": best_id,
        "title": _entity_label(chosen, lang) or query,
        "media_type": best_type,
        "year": found_year,
        "director": director,
        "overview": overview,
        "categories": categories,
    }
