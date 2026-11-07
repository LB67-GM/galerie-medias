from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_STOP = {
    "a",
    "au",
    "aux",
    "avec",
    "d",
    "de",
    "des",
    "du",
    "en",
    "et",
    "l",
    "la",
    "le",
    "les",
    "pour",
    "sur",
    "un",
    "une",
}
# Pays / région : « San Jose Californie » ne doit pas coller à « San Jose » (Espagne).
_GEO_HINT = {
    "allemagne",
    "arizona",
    "australia",
    "australie",
    "belgique",
    "belgium",
    "californie",
    "california",
    "canada",
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
    "mexique",
    "mexico",
    "nevada",
    "nicaragua",
    "ontario",
    "portugal",
    "quebec",
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

# Un seul mot trop générique : ne pas y rattacher tous les « Anniversaire … ».
_GENERIC_HEAD = {
    "album",
    "anniversaire",
    "bingo",
    "camping",
    "canal",
    "centre",
    "competition",
    "concert",
    "coupe",
    "famille",
    "fete",
    "gala",
    "halloween",
    "ile",
    "jour",
    "maison",
    "mariage",
    "mont",
    "natation",
    "parc",
    "party",
    "randonee",
    "randonnee",
    "repas",
    "saint",
    "sainte",
    "ski",
    "soiree",
    "sortie",
    "spectacle",
    "st",
    "tour",
    "vacances",
    "velo",
    "visite",
    "voyage",
    "weekend",
}


def fold(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_ = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    ascii_ = ascii_.replace("œ", "oe").replace("æ", "ae")
    ascii_ = re.sub(r"[._/'’\-]+", " ", ascii_)
    ascii_ = re.sub(r"[^a-z0-9 ]+", " ", ascii_)
    return re.sub(r"\s+", " ", ascii_).strip()


def tokens(name: str) -> tuple[str, ...]:
    cleaned = _YEAR_RE.sub(" ", fold(name))
    return tuple(p for p in cleaned.split() if p and p not in _STOP)


def _pick_label(names: list[str], counts: dict[str, int]) -> str:
    def score(n: str) -> tuple:
        has_year = 1 if _YEAR_RE.search(n) else 0
        return (has_year, len(n), -counts.get(n, 0), fold(n))

    return min(names, key=score)


def cluster_places(
    names: list[str], counts: dict[str, int] | None = None
) -> dict[str, str]:
    """Associe chaque nom brut au libellé consolidé (lieux et événements)."""
    counts = counts or {}
    by_sig: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for name in names:
        if not name or not str(name).strip():
            continue
        sig = tokens(name)
        if not sig:
            by_sig[("__", fold(name) or name)].append(name)
            continue
        by_sig[sig].append(name)

    sigs = sorted(by_sig.keys(), key=lambda s: (len(s), s))
    root_of: dict[tuple[str, ...], tuple[str, ...]] = {}
    for sig in sigs:
        root = sig
        for cand in sigs:
            if len(cand) >= len(sig):
                continue
            if sig[: len(cand)] != cand:
                continue
            if len(cand) == 1 and cand[0] in _GENERIC_HEAD:
                continue
            extra = sig[len(cand) :]
            if any(t in _GEO_HINT for t in extra):
                continue
            root = cand
            break
        root_of[sig] = root

    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for sig, originals in by_sig.items():
        groups[root_of[sig]].extend(originals)

    mapping: dict[str, str] = {}
    for members in groups.values():
        label = _pick_label(members, counts)
        for name in members:
            mapping[name] = label
    return mapping


def aliases_for(canonical: str, mapping: dict[str, str]) -> list[str]:
    found: list[str] = []
    folded = fold(canonical)
    for name, label in mapping.items():
        if label == canonical or fold(name) == folded or fold(label) == folded:
            if name not in found:
                found.append(name)
    if canonical not in found:
        found.append(canonical)
    return found
