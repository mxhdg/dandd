"""Opt-in lookups of free rules content from the Open5e API (SRD only).

Only the System Reference Document is requested (srd-2014 or srd-2024, both
licensed CC BY 4.0), never the other publishers' books Open5e also serves, so
what ends up in a character file is covered by the attribution in ATTRIBUTION.

Nothing here runs unless a player agrees to it. Every failure (offline,
timeout, an unexpected answer) raises SrdUnavailable so callers can fall back
to typing things by hand. Answers are cached as JSON for 30 days.
"""

import contextlib
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.open5e.com/v2/"
DOCUMENTS = {"2014": "srd-2014", "2024": "srd-2024"}
USER_AGENT = "dandd-codex/1.4 (character creation script; github.com/mxhdg/dandd)"
CACHE_DIR = Path(__file__).parent / ".cache" / "srd"
CACHE_SECONDS = 30 * 24 * 3600
TIMEOUT_SECONDS = 10
MAX_BYTES = 8_000_000
ATTRIBUTION = (
    "This work includes material from the System Reference Document (SRD) by "
    "Wizards of the Coast LLC, available at "
    "https://dnd.wizards.com/resources/systems-reference-document. The SRD is "
    "licensed under the Creative Commons Attribution 4.0 International License "
    "available at https://creativecommons.org/licenses/by/4.0/legalcode."
)

# Entries that describe the rules around a class or species rather than an
# ability the player would write on a sheet.
_SKIPPED_FEATURES = {
    "Ability Score Improvement",
    "Equipment",
    "Hit Points",
    "Proficiencies",
    "Proficiency Bonus",
    "Core Traits",
}
_SKIPPED_TRAITS = {
    "Ability Score Increase",
    "Age",
    "Alignment",
    "Creature Type",
    "Language",
    "Languages",
    "Size",
    "Speed",
    "Type",
}


class SrdUnavailable(Exception):
    """The SRD could not be reached or understood; type things by hand instead."""


def _fetch_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read(MAX_BYTES))
    except OSError as err:
        raise SrdUnavailable(f"could not reach the SRD ({err})") from err
    except ValueError as err:
        raise SrdUnavailable("the SRD answered with something unreadable") from err


def _read_cache(path):
    fresh = path.is_file() and time.time() - path.stat().st_mtime < CACHE_SECONDS
    if not fresh:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _write_cache(path, data):
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")


def _next_page(page):
    if not isinstance(page, dict) or not isinstance(page.get("results"), list):
        raise SrdUnavailable("the SRD answered with an unexpected shape")
    url = page.get("next")
    if url and not url.startswith(API):
        raise SrdUnavailable("the SRD pointed somewhere unexpected")
    return page["results"], url


def _all_results(resource, edition, fields, document=None):
    key = document or DOCUMENTS[edition]
    url = f"{API}{resource}/?document__key={key}&limit=500&fields={fields}"
    results = []
    while url:
        page_results, url = _next_page(_fetch_json(url))
        results += page_results
    return results


def _cached_results(resource, edition, fields, document=None, refresh=False):
    tag = hashlib.sha1(f"{fields}|{document}".encode()).hexdigest()[:8]
    path = CACHE_DIR / f"{resource}-{edition}-{tag}.json"
    cached = None if refresh else _read_cache(path)
    if cached is not None:
        return cached
    results = _all_results(resource, edition, fields, document)
    _write_cache(path, results)
    return results


def _first_sentence(text, limit=240):
    plain = re.sub(r"[*_#|>`]+", "", text or "")
    plain = " ".join(plain.split())
    sentence = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 3] + "..."


def _die_size(hit_dice):
    match = re.search(r"\d+", str(hit_dice or ""))
    return int(match.group()) if match else None


def _class_features(raw_features):
    features = []
    for feature in raw_features or []:
        if feature["name"] in _SKIPPED_FEATURES:
            continue
        levels = sorted({g["level"] for g in feature.get("gained_at") or []})
        text = _first_sentence(feature.get("desc"))
        features.append({"name": feature["name"], "text": text, "levels": levels})
    return features


def _class_entries(raw):
    bases = [r for r in raw if not r.get("subclass_of")]
    subclasses = {}
    for entry in raw:
        parent = (entry.get("subclass_of") or {}).get("key")
        if parent:
            subclasses.setdefault(parent, []).append(entry["name"])
    return [
        {
            "name": r["name"],
            "die": _die_size(r.get("hit_dice")),
            "saves": [s["name"] for s in r.get("saving_throws") or []],
            "features": _class_features(r.get("features")),
            "subclasses": sorted(subclasses.get(r["key"], [])),
        }
        for r in sorted(bases, key=lambda r: r["name"])
    ]


def _traits(raw_traits):
    return [
        {"name": t["name"], "text": _first_sentence(t.get("desc"))}
        for t in raw_traits or []
        if t["name"] not in _SKIPPED_TRAITS
    ]


def _species_entries(raw):
    subs = {}
    for entry in raw:
        if entry.get("is_subspecies"):
            sub = {"name": entry["name"], "traits": _traits(entry.get("traits"))}
            subs.setdefault(entry.get("subspecies_of"), []).append(sub)
    return [
        {
            "name": r["name"],
            "traits": _traits(r.get("traits")),
            "subspecies": sorted(subs.get(r["key"], []), key=lambda s: s["name"]),
        }
        for r in sorted(raw, key=lambda r: r["name"])
        if not r.get("is_subspecies")
    ]


def _spell_entries(raw):
    return [
        {
            "name": r["name"],
            "level": r["level"],
            "classes": [c["name"] for c in r.get("classes") or []],
        }
        for r in sorted(raw, key=lambda r: (r["level"], r["name"]))
    ]


def slugify(name):
    """A stable url-safe id for a rules name: "Hunter's Mark" -> 'hunters-mark'."""
    plain = str(name).lower().replace("'", "").replace("\u2019", "")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def _casting_time(raw):
    return _capitalized(
        re.sub(r"(?<=\d)(?=[a-z])", " ", str(raw or "")).replace("-", " ")
    )


def _capitalized(text):
    text = str(text or "")
    return text[:1].upper() + text[1:]


def _components(raw):
    letters = (("V", "verbal"), ("S", "somatic"))
    parts = [letter for letter, key in letters if raw.get(key)]
    if raw.get("material"):
        what = (raw.get("material_specified") or "").strip().rstrip(".")
        parts.append(f"M ({what})" if what else "M")
    return ", ".join(parts)


def _spell_detail(raw):
    return {
        "slug": slugify(raw["name"]),
        "name": raw["name"],
        "level": raw["level"],
        "school": (raw.get("school") or {}).get("name", ""),
        "casting_time": _casting_time(raw.get("casting_time")),
        "range": raw.get("range_text") or "",
        "components": _components(raw),
        "duration": _capitalized(raw.get("duration")),
        "concentration": bool(raw.get("concentration")),
        "ritual": bool(raw.get("ritual")),
        "classes": [c["name"] for c in raw.get("classes") or []],
        "text": raw.get("desc") or "",
        "higher": raw.get("higher_level") or "",
    }


def _condition_entries(raw, edition):
    entries = []
    for condition in raw:
        texts = [
            d["desc"]
            for d in condition.get("descriptions") or []
            if d.get("document") == DOCUMENTS[edition]
        ]
        if texts:
            slug = slugify(condition["name"])
            entries.append({"slug": slug, "name": condition["name"], "text": texts[0]})
    return sorted(entries, key=lambda e: e["name"])


def load_classes(edition):
    """Base classes: name, hit die size, saving throws, features, subclass names."""
    fields = "name,key,hit_dice,saving_throws,features,subclass_of"
    return _class_entries(_cached_results("classes", edition, fields))


def load_species(edition):
    """Species with their notable traits and any subspecies."""
    fields = "name,key,is_subspecies,subspecies_of,traits"
    return _species_entries(_cached_results("species", edition, fields))


def load_spells(edition):
    """Spells as name, level (0 = cantrip) and the classes that can learn them."""
    return _spell_entries(_cached_results("spells", edition, "name,level,classes"))


def load_spell_details(edition, refresh=False):
    """Full spell text (casting time, range, components, duration, description)."""
    fields = (
        "name,level,school,casting_time,range_text,duration,verbal,somatic,"
        "material,material_specified,concentration,ritual,desc,higher_level,classes"
    )
    raw = _cached_results("spells", edition, fields, refresh=refresh)
    return sorted((_spell_detail(r) for r in raw), key=lambda s: s["name"])


def load_conditions(edition, refresh=False):
    """The standard conditions as worded in the chosen edition's SRD."""
    fields = "name,key,descriptions"
    raw = _cached_results("conditions", edition, fields, "core", refresh)
    return _condition_entries(raw, edition)
