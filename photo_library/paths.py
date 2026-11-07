from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from photo_library.config import SKIP_DIR_NAMES, YEAR_DIR_RE

_YEAR_RE = re.compile(YEAR_DIR_RE, re.IGNORECASE)
_MONTHS = {
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
}


def skip_dir_name(name: str) -> bool:
    if name.startswith("."):
        return True
    low = name.lower()
    if low in SKIP_DIR_NAMES:
        return True
    if low.startswith("backup-") or low.startswith("backup=") or low.startswith("backup_"):
        return True
    return False


def year_from_folder(name: str) -> int | None:
    match = _YEAR_RE.match(name)
    return int(match.group(1)) if match else None


def _fold(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def is_month_folder(name: str) -> bool:
    """Dossiers type « Janvier 2006 » / « aout 2008 » : ce n'est pas un lieu."""
    match = re.fullmatch(r"([a-z]+)\s+(\d{4})", _fold(name))
    return bool(match and match.group(1) in _MONTHS)


# Enveloppes techniques (appareil, export) : ni lieu ni moment.
_TECHNICAL_FOLDERS = {
    "camera",
    "dcim",
    "export",
    "exports",
    "image",
    "images",
    "photo",
    "photos",
    "video",
    "videos",
}

# « Vacances Londres », « Croisiere anniversaire » : moment, le lieu est le sous-dossier.
_TRIP_PREFIXES = frozenset(
    {
        "vacances",
        "voyage",
        "voyages",
        "croisiere",
        "croisieres",
        "cruise",
        "cruises",
    }
)

_EVENT_WORDS = frozenset(
    {
        "album",
        "anniv",
        "anniversaire",
        "artifices",
        "bapteme",
        "baptemes",
        "bal",
        "camping",
        "championnat",
        "concert",
        "diner",
        "diners",
        "divers",
        "ecole",
        "famille",
        "festival",
        "fete",
        "fetes",
        "fiancailles",
        "fondue",
        "gala",
        "gastronomie",
        "gastronomes",
        "halloween",
        "hommage",
        "jardinage",
        "kayak",
        "mariage",
        "mariages",
        "natation",
        "noel",
        "paques",
        "party",
        "piscine",
        "randonneur",
        "randonneurs",
        "reveillon",
        "reunion",
        "soiree",
        "soirees",
        "sortie",
        "sorties",
        "tournoi",
        "visite",
        "weekend",
    }
)

_ANS_RE = re.compile(r"\b\d+\s*(?:ans|eme|er)\b")
_JOUR_AN_RE = re.compile(r"\bjour de l[' ]?an\b|\bnouvel an\b|\breveillon\b")
_KM_RE = re.compile(r"\b\d+\s*(?:km|kms|kilometres|kilometre)\b")

# Ancien ensemble : technique + préfixe de voyage exact.
_GENERIC_PLACE_FOLDERS = _TECHNICAL_FOLDERS | set(_TRIP_PREFIXES)


def is_technical_folder(name: str) -> bool:
    """DCIM / Photos / Camera : dump d’appareil, pas un lieu ni un moment."""
    return _fold(name) in _TECHNICAL_FOLDERS


def is_generic_place_folder(name: str) -> bool:
    """Vrai si le dossier est seulement une enveloppe (Vacances, Photos…), pas un lieu."""
    return _fold(name) in _GENERIC_PLACE_FOLDERS


def is_trip_title(name: str) -> bool:
    """Vacances, Voyage, Croisiere, ou « Vacances Portugal » / « Croisiere 2026 »."""
    from photo_library.geo import fold_name

    folded = fold_name(name)
    if folded in _TRIP_PREFIXES:
        return True
    parts = name.split(None, 1)
    return len(parts) == 2 and fold_name(parts[0]) in _TRIP_PREFIXES


def is_event_title(name: str) -> bool:
    """Anniversaire, mariage, soirée, N ans… — pas une ville."""
    from photo_library.geo import EVENT_ALIASES, fold_name

    if not name or is_technical_folder(name) or is_month_folder(name):
        return False
    if is_trip_title(name):
        return True
    folded = fold_name(name)
    if folded in EVENT_ALIASES:
        return True
    words = set(folded.replace("week end", "weekend").split())
    if words & _EVENT_WORDS:
        return True
    if _ANS_RE.search(folded) or _JOUR_AN_RE.search(folded) or _KM_RE.search(folded):
        return True
    return False


def geographic_core(name: str) -> str | None:
    """Clé de lieu si ce dossier est (ou contient) une géographie. None pour un voyage."""
    from photo_library.geo import (
        EVENT_ALIASES,
        city_index_available,
        contained_fixed_key,
        exact_place_key,
        fold_name,
        strip_years,
    )

    if not name or is_month_folder(name) or is_technical_folder(name):
        return None
    key = fold_name(name)
    if is_trip_title(name):
        return None
    if is_event_title(name):
        return contained_fixed_key(key)
    stripped = strip_years(key)
    for cand in (key, stripped):
        if not cand:
            continue
        found = exact_place_key(cand)
        if found and found not in EVENT_ALIASES:
            return found
    contained = contained_fixed_key(key)
    if contained:
        return contained
    # Sans index de villes (tests / pack incomplet) : un nom non-événement reste un lieu.
    if not city_index_available() and (stripped or key):
        return stripped or key
    return None


def is_moment_folder(name: str) -> bool:
    """Tout dossier sous l’année qui n’est pas un lieu (ni mois, ni DCIM/Photos)."""
    if not name or is_month_folder(name) or is_technical_folder(name):
        return False
    if is_event_title(name):
        return True
    return geographic_core(name) is None


def is_trip_envelope_folder(name: str) -> bool:
    """Vacances, Croisiere, Photos… ou tout moment. Une enveloppe est ignorée s’il reste un sous-dossier."""
    if is_generic_place_folder(name) or is_technical_folder(name):
        return True
    return is_moment_folder(name)


def _extra_beyond_place(name: str, core: str) -> bool:
    from photo_library.geo import FOLDER_ALIASES, fold_name, strip_years

    folded = fold_name(name)
    stripped = strip_years(folded)
    ckey = fold_name(core)
    if folded == ckey or stripped == ckey:
        return stripped != folded
    if FOLDER_ALIASES.get(folded) == ckey:
        return False
    return True


def _confirmed_geo(name: str, core: str | None) -> bool:
    from photo_library.geo import contained_fixed_key, exact_place_key, fold_name, strip_years

    if not core:
        return False
    key = fold_name(name)
    if exact_place_key(key) or exact_place_key(strip_years(key)) or contained_fixed_key(key):
        return True
    return bool(exact_place_key(fold_name(core)))


def folder_labels(folders: tuple[str, ...] | list[str]) -> tuple[str | None, str | None]:
    """Lieu (géographie) + moment (tout le reste) d’après les dossiers sous l’année."""
    from photo_library.geo import (
        EVENT_ALIASES,
        FOLDER_ALIASES,
        city_index_available,
        display_place_key,
        fold_name,
    )

    remaining = [part for part in folders if part]
    i = 0
    n = len(remaining)
    while i < n and is_month_folder(remaining[i]):
        i += 1
    moment = None
    place = None
    while i < n:
        name = remaining[i]
        last = i == n - 1
        if is_month_folder(name):
            i += 1
            continue
        if is_technical_folder(name) and not last:
            i += 1
            continue
        core = geographic_core(name)
        confirmed = _confirmed_geo(name, core)
        if (
            core
            and not confirmed
            and not is_event_title(name)
            and (
                (moment and is_trip_title(moment))
                or (moment is None and not city_index_available())
            )
        ):
            confirmed = True
        if core and confirmed:
            extra = _extra_beyond_place(name, core)
            if place is None:
                place = name if not extra else display_place_key(core)
            if extra and moment is None:
                moment = name
        elif not is_technical_folder(name) and moment is None:
            moment = name
        i += 1
    if place is None and moment:
        dest = FOLDER_ALIASES.get(fold_name(moment))
        if dest and fold_name(moment) in EVENT_ALIASES:
            place = display_place_key(dest)
    elif place:
        dest = FOLDER_ALIASES.get(fold_name(place))
        if dest and fold_name(place) not in EVENT_ALIASES:
            place = display_place_key(dest, place)
    return place, moment


def place_from_folder_chain(folders: tuple[str, ...] | list[str]) -> str | None:
    """Premier lieu utile : les mois sont ignorés, puis les enveloppes s’il reste un sous-dossier."""
    place, _moment = folder_labels(folders)
    return place


def list_years(library: Path) -> list[int]:
    """Années présentes sur le disque (dossiers Annee YYYY), pas l'index SQLite."""
    if not library.is_dir():
        return []
    found: set[int] = set()
    for child in library.iterdir():
        if not child.is_dir() or skip_dir_name(child.name):
            continue
        year = year_from_folder(child.name)
        if year is not None:
            found.add(year)
    return sorted(found, reverse=True)


def year_dir(library: Path, year: int) -> Path | None:
    for child in library.iterdir():
        if child.is_dir() and year_from_folder(child.name) == year:
            return child
    return None


def pair_key_of(relpath: str | None) -> str:
    """Clé Live Photo : dossier + nom, sans extension ni suffixe _hevc."""
    raw = str(relpath or "").replace("\\", "/").strip()
    if not raw:
        return ""
    path = Path(raw)
    stem = path.stem.lower()
    if stem.endswith("_hevc"):
        stem = stem[: -len("_hevc")]
    parent = str(path.parent).replace("\\", "/").lower()
    if parent in {".", ""}:
        return stem
    return f"{parent}/{stem}"


def parent_dir(relpath: str) -> str:
    """Dossier immédiat du fichier (`Annee 2026/Lieu`), sans les sous-dossiers."""
    parts = Path(str(relpath).replace("\\", "/")).parts
    if len(parts) < 2:
        return ""
    return "/".join(parts[:-1])


def parse_path_labels(relpath: str) -> tuple[int | None, str | None, str | None]:
    """Année, lieu (ville) et moment (voyage) d’après le chemin relatif."""
    parts = Path(relpath).parts
    if not parts:
        return None, None, None
    year = year_from_folder(parts[0])
    folders = parts[1:-1] if year is not None else parts[:-1]
    place, moment = folder_labels(folders)
    return year, place, moment


def parse_relpath(relpath: str) -> tuple[int | None, str | None]:
    """Année + lieu d'après le chemin relatif (Annee YYYY/Lieu/fichier)."""
    year, place, _moment = parse_path_labels(relpath)
    return year, place
