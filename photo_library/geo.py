"""Coordonnées des dossiers lieu (pins de la carte), sans relire 90 000 EXIF."""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from photo_library.place_groups import cluster_places

# Pays visités en priorité quand plusieurs villes portent le même nom (Paris, Laval…).
_CC_RANK = {
    "CA": 0,
    "FR": 1,
    "IT": 2,
    "ES": 3,
    "US": 4,
    "GB": 5,
    "BE": 6,
    "CH": 7,
    "DE": 8,
    "PT": 9,
    "NL": 10,
    "IE": 11,
    "MA": 12,
    "TN": 13,
    "GR": 14,
    "HR": 15,
    "AT": 16,
    "MX": 17,
    "BR": 18,
    "AR": 19,
    "CL": 20,
    "JP": 21,
    "TH": 22,
    "AU": 23,
    "NZ": 24,
    "RE": 25,
    "GP": 26,
    "MQ": 27,
}

# Dossiers d’événements → ville réelle (fête à domicile, pas une ville homonyme).
# Les fautes de frappe restent des lieux : elles ne sont pas dans EVENT_ALIASES.
FOLDER_ALIASES = {
    "fete jardin": "paris",
    "soiree terrasse": "paris",
    "pique nique": "paris",
    "marseiile": "marseille",
    "marseile": "marseille",
    "marsielle": "marseille",
}

# Alias d’événement (Moment + ville), distinct des fautes de frappe de lieu.
EVENT_ALIASES = frozenset({"fete jardin", "soiree terrasse", "pique nique"})

# Lieux où le fichier villes se trompe (Rome GA) ou n’a pas le nom français (Floride).
FIXED_PLACES: dict[str, tuple[float, float, str]] = {
    "montreal": (45.50884, -73.58781, "CA"),
    "rome": (41.90278, 12.49636, "IT"),
    "roma": (41.90278, 12.49636, "IT"),
    "paris": (48.8566, 2.3522, "FR"),
    "marseille": (43.2965, 5.3698, "FR"),
    "londres": (51.5074, -0.1278, "GB"),
    "london": (51.5074, -0.1278, "GB"),
    "tunis": (36.8065, 10.1815, "TN"),
    "floride": (27.6648, -81.5158, "US"),
    "florida": (27.6648, -81.5158, "US"),
    "new york": (40.7128, -74.006, "US"),
    "nyc": (40.7128, -74.006, "US"),
    "manhattan": (40.7128, -74.006, "US"),
    "manhattan ny": (40.7128, -74.006, "US"),
    "manhattan new york": (40.7128, -74.006, "US"),
    "manhattan kansas": (39.1836, -96.5717, "US"),
    "manhattan ks": (39.1836, -96.5717, "US"),
    "californie": (36.7783, -119.4179, "US"),
    "california": (36.7783, -119.4179, "US"),
    "texas": (31.0, -100.0, "US"),
    "arizona": (34.0489, -111.0937, "US"),
    "las vegas": (36.1699, -115.1398, "US"),
    "vegas": (36.1699, -115.1398, "US"),
    "jamaique": (18.1096, -77.2975, "JM"),
    "jamaica": (18.1096, -77.2975, "JM"),
    "nicaragua": (12.8654, -85.2072, "NI"),
    "cuba": (21.5218, -77.7812, "CU"),
    "mexique": (23.6345, -102.5528, "MX"),
    "toscane": (43.7711, 11.2486, "IT"),
    "sicile": (37.6, 14.0154, "IT"),
    "san jose california": (37.3382, -121.8863, "US"),
    "san jose californie": (37.3382, -121.8863, "US"),
    "san jose usa": (37.3382, -121.8863, "US"),
    "san jose etats unis": (37.3382, -121.8863, "US"),
    "portugal": (39.55, -8.0, "PT"),
    "lisbonne": (38.71667, -9.13333, "PT"),
    "lisbon": (38.71667, -9.13333, "PT"),
    "france": (46.603354, 1.888334, "FR"),
    "var": (43.4167, 6.2667, "FR"),
}

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_CC_FR = {
    "AR": "Argentine",
    "AT": "Autriche",
    "AU": "Australie",
    "BE": "Belgique",
    "BR": "Brésil",
    "CA": "Canada",
    "CH": "Suisse",
    "CL": "Chili",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "DE": "Allemagne",
    "ES": "Espagne",
    "FR": "France",
    "GB": "Royaume-Uni",
    "GR": "Grèce",
    "HR": "Croatie",
    "IE": "Irlande",
    "IT": "Italie",
    "JM": "Jamaïque",
    "JP": "Japon",
    "MA": "Maroc",
    "MX": "Mexique",
    "NI": "Nicaragua",
    "NL": "Pays-Bas",
    "NZ": "Nouvelle-Zélande",
    "PH": "Philippines",
    "PT": "Portugal",
    "TH": "Thaïlande",
    "TN": "Tunisie",
    "US": "États-Unis",
}
_CC_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("etats unis", "united states", "usa"), "US"),
    (("californie", "california"), "US"),
    (("floride", "florida"), "US"),
    (("espagne", "spain"), "ES"),
    (("italie", "italy"), "IT"),
    (("france",), "FR"),
    (("canada",), "CA"),
    (("mexique", "mexico"), "MX"),
    (("angleterre", "royaume uni", "united kingdom"), "GB"),
    (("allemagne", "germany"), "DE"),
    (("portugal",), "PT"),
    (("belgique", "belgium"), "BE"),
    (("suisse", "switzerland"), "CH"),
    (("jamaique", "jamaica"), "JM"),
    (("costa rica",), "CR"),
    (("philippines",), "PH"),
    (("cuba",), "CU"),
    (("nicaragua",), "NI"),
    (("australie", "australia"), "AU"),
]
_ADMIN_HINTS = {
    "californie": "california",
    "california": "california",
    "floride": "florida",
    "florida": "florida",
    "texas": "texas",
    "arizona": "arizona",
    "nevada": "nevada",
    "quebec": "quebec",
    "ontario": "ontario",
    "kansas": "kansas",
    "new york": "new york",
}
_GEO_STRIP = {
    "allemagne",
    "arizona",
    "australia",
    "australie",
    "belgique",
    "belgium",
    "californie",
    "california",
    "canada",
    "costa",
    "cuba",
    "espagne",
    "etats",
    "etatsunis",
    "floride",
    "florida",
    "france",
    "germany",
    "italie",
    "italy",
    "jamaique",
    "jamaica",
    "kingdom",
    "mexique",
    "mexico",
    "nevada",
    "nicaragua",
    "ontario",
    "philippines",
    "portugal",
    "quebec",
    "rica",
    "royaume",
    "spain",
    "states",
    "suisse",
    "switzerland",
    "texas",
    "uk",
    "unis",
    "united",
    "usa",
}
_SKIP_CITY = {
    "album",
    "anniversaire",
    "famille",
    "fete",
    "mariage",
    "soiree",
    "sortie",
    "vacances",
    "visite",
    "voyage",
    "weekend",
}
_PRETTY = {
    "montreal": "Montréal",
    "rome": "Rome",
    "paris": "Paris",
    "marseille": "Marseille",
    "londres": "Londres",
    "london": "Londres",
    "tunis": "Tunis",
    "floride": "Floride",
    "florida": "Floride",
    "new york": "New York",
    "nyc": "New York",
    "manhattan": "New York",
    "portugal": "Portugal",
    "lisbonne": "Lisbonne",
    "lisbon": "Lisbonne",
    "californie": "Californie",
    "california": "Californie",
    "arizona": "Arizona",
    "texas": "Texas",
    "jamaique": "Jamaïque",
    "jamaica": "Jamaïque",
    "nicaragua": "Nicaragua",
    "france": "France",
    "canada": "Canada",
    "italie": "Italie",
    "mexique": "Mexique",
    "cuba": "Cuba",
    "var": "Var",
    "vegas": "Las Vegas",
    "las vegas": "Las Vegas",
}


def fold_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().replace("-", " ").replace("'", " ").split())


def strip_years(folded: str) -> str:
    return " ".join(_YEAR_RE.sub(" ", folded).split())


def _cc_rank(cc: str) -> int:
    return _CC_RANK.get((cc or "").upper(), 80)


def _point(lat: float, lon: float, cc: str) -> dict:
    return {"lat": lat, "lon": lon, "cc": cc}


@lru_cache(maxsize=1)
def _city_index() -> dict[str, list[tuple[float, float, str, str, str]]]:
    index: dict[str, list[tuple[float, float, str, str, str]]] = {}
    try:
        import reverse_geocoder as rg
    except ImportError:
        return index
    csv_path = Path(rg.__file__).resolve().parent / "rg_cities1000.csv"
    if not csv_path.is_file():
        return index
    with csv_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 6:
                continue
            try:
                lat = float(row[0])
                lon = float(row[1])
            except ValueError:
                continue
            name = row[2]
            admin = row[3] if len(row) > 3 else ""
            cc = row[5] if len(row) > 5 else ""
            key = fold_name(name)
            if len(key) < 2:
                continue
            index.setdefault(key, []).append((lat, lon, cc, name, admin))
    return index


def _from_fixed(key: str) -> dict | None:
    if key in FIXED_PLACES:
        lat, lon, cc = FIXED_PLACES[key]
        return _point(lat, lon, cc)
    aliased = FOLDER_ALIASES.get(key)
    if aliased and aliased in FIXED_PLACES:
        lat, lon, cc = FIXED_PLACES[aliased]
        return _point(lat, lon, cc)
    return None


def _city_hits(key: str) -> list[tuple[float, float, str, str, str]]:
    if not key:
        return []
    hits = _city_index().get(key)
    if not hits and " " in key:
        hits = _city_index().get(key.replace(" ", ""))
    return list(hits or [])


def _from_cities(
    key: str,
    prefer_cc: str | None = None,
    prefer_admin: str | None = None,
) -> dict | None:
    hits = _city_hits(key)
    if not hits:
        return None
    if prefer_cc:
        filtered = [h for h in hits if (h[2] or "").upper() == prefer_cc.upper()]
        if filtered:
            hits = filtered
    if prefer_admin:
        admined = [h for h in hits if fold_name(h[4]) == prefer_admin]
        if admined:
            hits = admined
    hits = sorted(hits, key=lambda h: (_cc_rank(h[2]), h[0], h[1]))
    lat, lon, cc, _name, _admin = hits[0]
    return _point(lat, lon, cc)


def _detect_hints(folded: str) -> tuple[str | None, str | None]:
    blob = f" {strip_years(folded)} "
    cc: str | None = None
    for needles, code in _CC_HINTS:
        if any(f" {n} " in blob for n in needles):
            cc = code
            break
    admin: str | None = None
    for needle, admin_fold in _ADMIN_HINTS.items():
        if f" {needle} " in blob:
            admin = admin_fold
            if cc is None and needle in {
                "californie",
                "california",
                "floride",
                "florida",
                "texas",
                "arizona",
                "nevada",
            }:
                cc = "US"
            if cc is None and needle in {"quebec", "ontario"}:
                cc = "CA"
            break
    return cc, admin


def _strip_geo_tokens(folded: str) -> str:
    parts = [p for p in strip_years(folded).split() if p not in _GEO_STRIP]
    return " ".join(parts)


def _lookup_keys(folded: str) -> list[str]:
    stripped = strip_years(folded)
    city = _strip_geo_tokens(folded)
    out: list[str] = []
    for cand in (folded, stripped, city):
        if cand and cand not in out:
            out.append(cand)
    parts = city.split()
    for i in range(len(parts), 0, -1):
        chunk = " ".join(parts[:i])
        if i == 1 and (len(chunk) < 4 or chunk in _SKIP_CITY):
            continue
        if chunk and chunk not in out:
            out.append(chunk)
    return out


def country_flag(cc: str) -> str:
    code = (cc or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code)


def _display_place(name: str, admin: str, cc: str) -> str:
    """Ville et région, puis le drapeau du pays à la place de son nom."""
    country = _CC_FR.get((cc or "").upper(), "")
    country_key = fold_name(country) if country else ""
    bits: list[str] = []
    if name and name.strip() and fold_name(name) != country_key:
        bits.append(name.strip())
    if admin and fold_name(admin) not in {fold_name(name or ""), country_key}:
        bits.append(admin.strip())
    flag = country_flag(cc)
    if flag:
        bits.append(flag)
    elif country:
        bits.append(country)
    return " · ".join(bits)


def contained_fixed_key(folded: str) -> str | None:
    """« Floride 2017 », « Soiree a Lisbonne » : un lieu connu dans le titre."""
    blob = f" {strip_years(folded)} "
    best: str | None = None
    for key in FIXED_PLACES:
        if len(key) < 4:
            continue
        if f" {key} " in blob or blob.strip() == key:
            if best is None or len(key) > len(best):
                best = key
    for fr in _CC_FR.values():
        key = fold_name(fr)
        if len(key) < 4:
            continue
        if f" {key} " in blob:
            if best is None or len(key) > len(best):
                best = key
    return best


def _contained_fixed(folded: str) -> dict | None:
    """« Floride 2017 », « Vacances Rome » : le nom du lieu est dans le dossier."""
    key = contained_fixed_key(folded)
    if not key:
        return None
    found = _from_fixed(key)
    if found:
        return found
    hits = _city_hits(key)
    if hits:
        lat, lon, cc, _name, _admin = hits[0]
        return _point(lat, lon, cc)
    return None


def city_index_available() -> bool:
    return bool(_city_index())


def exact_place_key(folded: str) -> str | None:
    """Clé si le nom plié est exactement un lieu (ville, pays), pas un événement."""
    if not folded or folded in _SKIP_CITY:
        return None
    dest = FOLDER_ALIASES.get(folded)
    if dest and folded not in EVENT_ALIASES:
        return dest
    if folded in FIXED_PLACES:
        return folded
    if len(folded) >= 3 and _city_hits(folded):
        return folded
    return None


def display_place_key(key: str, original: str | None = None) -> str:
    pretty = _PRETTY.get(key)
    if pretty:
        return pretty
    if original and fold_name(original) == key:
        return original
    small = {"de", "des", "du", "la", "le", "les", "sur", "en"}
    bits = []
    for word in key.split():
        bits.append(word if word in small else word[:1].upper() + word[1:])
    return " ".join(bits)


def resolve_folder_place(folder: str | None, extra: dict[str, str] | None = None) -> str | None:
    """Nom de lieu affiché : alias utilisateur (chemin), alias d’événement, ou dossier tel quel."""
    if not folder or not str(folder).strip():
        return None
    extra = extra or {}
    is_path = "/" in str(folder).replace("\\", "/")
    folded = fold_name(folder)
    stripped = strip_years(folded)
    for key in (folded, stripped):
        if not key:
            continue
        # Alias = chemin de dossier (`Annee 2020/Fete jardin`), pas un nom de ville nu
        # (une ville homonyme ne doit pas avaler le filtre ni le clic sur la carte).
        if is_path and key in extra:
            return extra[key]
        dest = FOLDER_ALIASES.get(key)
        if dest:
            return _PRETTY.get(dest) or dest
    return folder


def geocode_place(name: str) -> dict | None:
    """Une coordonnée pour un nom de dossier lieu, ou None."""
    key = fold_name(name)
    if len(key) < 2:
        return None
    stripped = strip_years(key)
    cc_hint, admin_hint = _detect_hints(key)
    for candidate in (key, stripped, FOLDER_ALIASES.get(key, ""), FOLDER_ALIASES.get(stripped, "")):
        if not candidate:
            continue
        found = _from_fixed(candidate)
        if found:
            return found
    city = _strip_geo_tokens(key)
    for candidate in (key, stripped, city):
        if not candidate or candidate in _SKIP_CITY:
            continue
        found = _from_fixed(candidate)
        if found:
            return found
        found = _from_cities(candidate, prefer_cc=cc_hint, prefer_admin=admin_hint)
        if found:
            return found
    found = _contained_fixed(key)
    if found:
        return found
    parts = city.split()
    if len(parts) >= 2:
        for i in range(len(parts) - 1, 1, -1):
            chunk = " ".join(parts[:i])
            if chunk in _SKIP_CITY:
                continue
            found = _from_cities(chunk, prefer_cc=cc_hint, prefer_admin=admin_hint)
            if found:
                return found
    for candidate in (key, stripped):
        if not candidate or candidate in _SKIP_CITY:
            continue
        found = _from_cities(candidate)
        if found:
            return found
    return None


def search_places(
    query: str,
    *,
    limit: int = 12,
    overrides: dict[str, dict] | None = None,
) -> list[dict]:
    """Villes candidates pour le dialogue Lieu (Espagne vs Californie, etc.)."""
    raw = (query or "").strip()
    key = fold_name(raw)
    if len(key) < 2:
        return []
    cc_hint, admin_hint = _detect_hints(key)
    results: list[dict] = []
    seen: set[tuple[float, float]] = set()

    def add(lat: float, lon: float, cc: str, label: str, admin: str = "", source: str = "city") -> None:
        bucket = (round(float(lat), 3), round(float(lon), 3))
        if bucket in seen:
            return
        seen.add(bucket)
        results.append(
            {
                "label": label,
                "display": _display_place(label, admin, cc),
                "lat": float(lat),
                "lon": float(lon),
                "cc": cc or "",
                "source": source,
            }
        )

    if overrides:
        ov = overrides.get(key)
        if ov and ov.get("lat") is not None and ov.get("lon") is not None:
            add(ov["lat"], ov["lon"], ov.get("cc") or "", ov.get("place") or raw, source="user")

    for cand in _lookup_keys(key):
        found = _from_fixed(cand)
        if found:
            pretty = _PRETTY.get(cand) or raw
            add(found["lat"], found["lon"], found["cc"], pretty, source="fixed")
        for hit in _city_hits(cand):
            lat, lon, cc, name, admin = hit
            add(lat, lon, cc, name, admin, source="city")

    needle = _strip_geo_tokens(key) or strip_years(key)
    if len(needle) >= 4:
        for fkey, coords in FIXED_PLACES.items():
            if needle == fkey or f" {needle} " in f" {fkey} " or needle in fkey:
                lat, lon, cc = coords
                pretty = _PRETTY.get(fkey) or fkey.title()
                add(lat, lon, cc, pretty, source="fixed")

    named = geocode_place(raw) if raw else None

    def rank(item: dict) -> tuple:
        far_user = (
            item["source"] == "user"
            and named
            and abs(item["lat"] - named["lat"]) + abs(item["lon"] - named["lon"]) > 4
        )
        if item["source"] == "user" and not far_user:
            src = 0
        elif item["source"] == "fixed":
            src = 1
        elif item["source"] == "user":
            src = 4
        else:
            src = 2
        hint = 0 if cc_hint and (item["cc"] or "").upper() == cc_hint else 1
        admin_m = 0 if admin_hint and admin_hint in fold_name(item.get("display") or "") else 1
        exact = 0 if fold_name(item.get("label") or "") in {key, strip_years(key)} else 1
        return (src, exact, hint, admin_m, _cc_rank(item["cc"]), -item["lat"])

    results.sort(key=rank)
    return results[: max(1, min(int(limit), 24))]


def reverse_place(lat: float, lon: float) -> dict:
    """Ville proche d’un clic sur la carte."""
    display = f"{float(lat):.4f}, {float(lon):.4f}"
    out = {
        "label": "",
        "display": display,
        "lat": float(lat),
        "lon": float(lon),
        "cc": "",
        "admin": "",
    }
    try:
        import reverse_geocoder as rg
    except ImportError:
        return out
    hits = rg.search([(float(lat), float(lon))])
    if not hits:
        return out
    hit = hits[0]
    name = str(hit.get("name") or "")
    admin = str(hit.get("admin1") or "")
    cc = str(hit.get("cc") or "")
    label = _pretty_reverse_label(name, admin, cc)
    out.update(
        {
            "label": label,
            "display": _display_place(label, admin, cc) or display,
            "cc": cc,
            "admin": admin,
        }
    )
    return out


def _pretty_reverse_label(name: str, admin: str, cc: str) -> str:
    n = fold_name(name)
    a = fold_name(admin)
    if (cc or "").upper() == "US" and a == "new york" and n in {
        "manhattan",
        "new york",
        "new york city",
        "nyc",
    }:
        return "New York"
    return _PRETTY.get(n) or name


def preferred_city_label(fold_key: str, names: list[str], counts: dict[str, int]) -> str:
    cands = [n for n in names if fold_name(n) == fold_key]
    if not cands:
        return _PRETTY.get(fold_key, fold_key.title())

    def score(n: str) -> tuple:
        has_year = 1 if _YEAR_RE.search(n) else 0
        accent = 0 if any(ord(c) > 127 for c in n) else 1
        return (has_year, -counts.get(n, 0), accent, len(n))

    return min(cands, key=score)


def apply_folder_aliases(
    mapping: dict[str, str],
    names: list[str],
    counts: dict[str, int] | None = None,
    extra: dict[str, str] | None = None,
    skip_keys: set[str] | None = None,
) -> dict[str, str]:
    """Rattache les dossiers d’événements (Fête jardin, Soirée terrasse…) à la ville."""
    counts = counts or {}
    extra = extra or {}
    skip = {fold_name(k) for k in (skip_keys or []) if k}
    out = dict(mapping)
    for name in names:
        if fold_name(name) in skip:
            continue
        label = resolve_folder_place(name, extra)
        if label and label != name:
            out[name] = label
        elif fold_name(name) in FOLDER_ALIASES:
            dest = FOLDER_ALIASES[fold_name(name)]
            out[name] = preferred_city_label(dest, names, counts)
    return out


def _trust_user_geo(place: str, user_geo: dict | None, named_geo: dict | None) -> dict | None:
    """Ignore une pastille utilisateur absurde (0°, Sahara) si le nom a des coords connues."""
    if not user_geo:
        return None
    try:
        lat = float(user_geo["lat"])
        lon = float(user_geo["lon"])
    except (TypeError, ValueError, KeyError):
        return None
    if not str(user_geo.get("cc") or "").strip() and abs(lon) < 1e-6:
        return None
    if (
        named_geo
        and fold_name(place) in FIXED_PLACES
        and abs(lat - named_geo["lat"]) + abs(lon - named_geo["lon"]) > 4
    ):
        return None
    return user_geo


def map_places(conn) -> dict:
    rows = conn.execute(
        """
        SELECT place, COUNT(*) AS c,
               MIN(year) AS y0, MAX(year) AS y1
        FROM media
        WHERE present=1 AND place IS NOT NULL AND place != ''
        GROUP BY place
        """
    ).fetchall()
    names = [r["place"] for r in rows if r["place"]]
    counts = {r["place"]: int(r["c"] or 0) for r in rows if r["place"]}
    from photo_library.places import user_alias_map, user_coord_map

    coords = user_coord_map(conn)
    from photo_library.gps import gps_centroids

    photo_gps = gps_centroids(conn)
    mapping = apply_folder_aliases(
        cluster_places(names, counts),
        names,
        counts,
        extra=user_alias_map(conn),
        skip_keys=set(coords.keys()),
    )

    buckets: dict[tuple[float, float], list[dict]] = defaultdict(list)
    unknown: list[dict] = []
    for row in rows:
        place = row["place"]
        if not place:
            continue
        label = mapping.get(place, place)
        user_geo = coords.get(fold_name(place)) or coords.get(fold_name(label))
        named_geo = geocode_place(place) or geocode_place(label)
        user_geo = _trust_user_geo(place, user_geo, named_geo)
        gps_geo = photo_gps.get(place)
        if user_geo:
            geo = user_geo
            label = place
        elif gps_geo:
            geo = {
                "lat": gps_geo["lat"],
                "lon": gps_geo["lon"],
                "cc": (named_geo or {}).get("cc") or "",
            }
        else:
            geo = named_geo
        item = {
            "place": place,
            "label": label,
            "count": int(row["c"] or 0),
            "year_min": row["y0"],
            "year_max": row["y1"],
        }
        if not geo:
            unknown.append(item)
            continue
        item.update(geo)
        key = (round(geo["lat"], 2), round(geo["lon"], 2))
        buckets[key].append(item)

    pins = []
    for members in buckets.values():
        total = sum(m["count"] for m in members)
        years = [y for m in members for y in (m["year_min"], m["year_max"]) if y]
        labels = list({m["label"] for m in members})
        title = preferred_city_label(
            fold_name(labels[0]),
            labels,
            {lab: sum(m["count"] for m in members if m["label"] == lab) for lab in labels},
        )
        # Préférer le libellé ville (Paris) à l’événement (Fête jardin) si les deux sont au même point.
        cityish = [
            m["label"]
            for m in members
            if fold_name(m["label"]) not in FOLDER_ALIASES
            and fold_name(m["place"]) not in FOLDER_ALIASES
        ]
        if cityish:
            title = preferred_city_label(
                fold_name(max(cityish, key=lambda n: counts.get(n, 0))),
                cityish,
                counts,
            )
        pretty = _PRETTY.get(strip_years(fold_name(title)))
        if pretty:
            title = pretty
        sample = members[0]
        filter_place = title
        for member in sorted(members, key=lambda m: -m["count"]):
            if fold_name(member["place"]) == fold_name(title) or fold_name(
                member["label"]
            ) == fold_name(title):
                filter_place = member["place"]
                break
        else:
            filter_place = max(members, key=lambda m: m["count"])["place"]
        pins.append(
            {
                "place": title,
                "filter_place": filter_place,
                "count": total,
                "year_min": min(years) if years else None,
                "year_max": max(years) if years else None,
                "lat": sample["lat"],
                "lon": sample["lon"],
                "cc": sample["cc"],
            }
        )
    pins.sort(key=lambda p: p["count"], reverse=True)
    unknown.sort(key=lambda p: p["count"], reverse=True)
    return {
        "pins": pins,
        "unknown": [
            {"place": u["place"], "count": u["count"], "year_min": u["year_min"], "year_max": u["year_max"]}
            for u in unknown[:80]
        ],
        "unknown_count": len(unknown),
        "pin_count": len(pins),
        "photo_count": sum(p["count"] for p in pins),
    }
