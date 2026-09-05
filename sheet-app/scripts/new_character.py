#!/usr/bin/env python3
"""Interactively generate a new sheet-app data/<id>.yaml character file.

Run from anywhere with PyYAML installed (the sheet-app venv already has it):

    python scripts/new_character.py

Two modes:
  skeleton  - prompts for identity fields only, fills the rest with valid
              defaults (10 in every ability, no proficiencies, empty lists)
              so the sheet renders immediately; hand-edit the rest afterward.
  full      - prompts for ability scores, proficiencies, hp, equipment,
              features, backstory, etc. and computes all the derived
              modifiers/DCs, producing a much more complete file up front.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).parent.parent / "data"

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

ABILITIES = [
    "Strength",
    "Dexterity",
    "Constitution",
    "Intelligence",
    "Wisdom",
    "Charisma",
]
ABILITY_ABBR = {
    "Strength": "Str",
    "Dexterity": "Dex",
    "Constitution": "Con",
    "Intelligence": "Int",
    "Wisdom": "Wis",
    "Charisma": "Cha",
}
SKILLS = [
    ("Acrobatics", "Dexterity"),
    ("Animal Handling", "Wisdom"),
    ("Arcana", "Intelligence"),
    ("Athletics", "Strength"),
    ("Deception", "Charisma"),
    ("History", "Intelligence"),
    ("Insight", "Wisdom"),
    ("Intimidation", "Charisma"),
    ("Investigation", "Intelligence"),
    ("Medicine", "Wisdom"),
    ("Nature", "Intelligence"),
    ("Perception", "Wisdom"),
    ("Performance", "Charisma"),
    ("Persuasion", "Charisma"),
    ("Religion", "Intelligence"),
    ("Sleight of Hand", "Dexterity"),
    ("Stealth", "Dexterity"),
    ("Survival", "Wisdom"),
]
CURRENCY_KEYS = ["cp", "sp", "ep", "gp", "pp"]


def _slugify(name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_")
    return slug or "character"


def _ability_mod(score):
    return (score - 10) // 2


def _fmt_mod(n):
    return f"+{n}" if n >= 0 else str(n)


def _proficiency_bonus(level):
    return 2 + (max(level, 1) - 1) // 4


def _ask(prompt_text, default=""):
    suffix = f" [{default}]" if default else ""
    return input(f"{prompt_text}{suffix}: ").strip() or default


def _ask_int(prompt_text, default=0):
    try:
        return int(_ask(prompt_text, str(default)))
    except ValueError:
        return default


def _ask_yn(prompt_text, default=False):
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt_text} [{suffix}]: ").strip().lower()
    return value.startswith("y") if value else default


def _ask_names(prompt_text, valid_names):
    raw = _ask(f"{prompt_text} (comma-separated, blank for none)")
    if not raw:
        return set()
    valid = set(valid_names)
    chosen = {n.strip() for n in raw.split(",") if n.strip()}
    unknown = chosen - valid
    if unknown:
        print(f"  ignoring unrecognized: {', '.join(sorted(unknown))}")
    return chosen & valid


def _collect_simple_list(label):
    print(f"{label} (blank line to finish):")
    items = []
    while True:
        item = input("  - ").strip()
        if not item:
            break
        items.append(item)
    return items


def _collect_named_list(label, fields):
    print(f"{label} (blank name to finish):")
    items = []
    while True:
        name = input("  name: ").strip()
        if not name:
            break
        entry = {"name": name}
        for field in fields:
            entry[field] = input(f"    {field}: ").strip()
        items.append(entry)
    return items


def _skeleton_abilities_saves_skills():
    abilities = [{"name": a, "score": 10, "mod": "+0"} for a in ABILITIES]
    saves = [{"name": a, "mod": "+0", "prof": False} for a in ABILITIES]
    skills = [
        {"name": s, "ability": ABILITY_ABBR[a], "mod": "+0", "prof": False}
        for s, a in SKILLS
    ]
    return abilities, saves, skills, 2, 10


def _full_abilities_saves_skills():
    print("\nAbility scores:")
    scores = {a: _ask_int(f"  {a}", 10) for a in ABILITIES}
    level = _ask_int("Character level (for proficiency bonus)", 1)
    prof_bonus = _proficiency_bonus(level)
    print(f"  proficiency bonus: {_fmt_mod(prof_bonus)}")
    prof_saves = _ask_names("Proficient saving throws", ABILITIES)
    prof_skills = _ask_names("Proficient skills", [s for s, _ in SKILLS])

    mods = {a: _ability_mod(scores[a]) for a in ABILITIES}
    abilities = [
        {"name": a, "score": scores[a], "mod": _fmt_mod(mods[a])} for a in ABILITIES
    ]
    saves = [
        {
            "name": a,
            "mod": _fmt_mod(mods[a] + (prof_bonus if a in prof_saves else 0)),
            "prof": a in prof_saves,
        }
        for a in ABILITIES
    ]
    skills = [
        {
            "name": s,
            "ability": ABILITY_ABBR[a],
            "mod": _fmt_mod(mods[a] + (prof_bonus if s in prof_skills else 0)),
            "prof": s in prof_skills,
        }
        for s, a in SKILLS
    ]
    perception_mod = int(next(sk["mod"] for sk in skills if sk["name"] == "Perception"))
    return abilities, saves, skills, prof_bonus, 10 + perception_mod


def _build_spellcasting():
    if not _ask_yn("Include spellcasting section?", False):
        return None
    print("Spell slots (blank level to finish):")
    slots = []
    while True:
        level = input("  level (e.g. 1st): ").strip()
        if not level:
            break
        slots.append({"level": level, "total": _ask_int("    total slots", 1)})
    return {
        "class": _ask("Spellcasting class"),
        "ability": _ask("Spellcasting ability (e.g. Intelligence)"),
        "save_dc": _ask_int("Spell save DC", 10),
        "attack_bonus": _ask("Spell attack bonus (e.g. +5)", "+0"),
        "note": _ask("Note (optional)"),
        "cantrips": [
            c.strip()
            for c in _ask("Cantrips (comma-separated)").split(",")
            if c.strip()
        ],
        "slots": slots,
        "prepared": [
            s.strip()
            for s in _ask("Prepared spells (comma-separated)").split(",")
            if s.strip()
        ],
        "always_prepared": [],
    }


def _parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--id", help="character id / filename (data/<id>.yaml)")
    parser.add_argument("--name", help="character name")
    parser.add_argument(
        "--mode", choices=["skeleton", "full"], help="how much detail to prompt for"
    )
    return parser.parse_args()


def _resolve_name(args):
    name = args.name or _ask("Character name")
    while not name:
        name = _ask("Character name (required)")
    return name


def _resolve_character_id(args, name):
    default_id = _slugify(name)
    char_id = args.id or _ask("Character id (used as filename)", default_id)
    while not ID_RE.fullmatch(char_id):
        print("  id must match ^[A-Za-z0-9_-]+$ (letters, numbers, underscore, hyphen)")
        char_id = _ask("Character id (used as filename)", default_id)
    return char_id


def _confirm_overwrite(out_path):
    return not out_path.exists() or _ask_yn(
        f"{out_path} already exists, overwrite?", False
    )


def _resolve_mode(args):
    mode = args.mode
    while mode not in ("skeleton", "full"):
        mode = _ask(
            "Mode ('skeleton' = core fields + defaults, "
            "'full' = prompt for everything)",
            "skeleton",
        )
    return mode


def _ask_identity_fields():
    return {
        "class_level": _ask("Class & level (e.g. 'Artificer 5 (Artillerist)')"),
        "background": _ask("Background"),
        "player_name": _ask("Player name"),
        "race": _ask("Race"),
        "alignment": _ask("Alignment"),
    }


def _build_full_details(abilities):
    dex_mod = next(a["mod"] for a in abilities if a["name"] == "Dexterity")
    details = {
        "other_proficiencies": {
            "languages": _ask("Languages", "Common"),
            "armor": _ask("Armor proficiencies"),
            "weapons": _ask("Weapon proficiencies"),
            "tools": _ask("Tool proficiencies"),
        },
        "combat": {
            "ac": _ask_int("Armor Class", 10),
            "initiative": _ask("Initiative", dex_mod),
            "speed": _ask("Speed", "30 ft"),
        },
        "hp": {"max": _ask_int("Max HP", 10), "current": "", "temp": ""},
        "hit_dice": {"total": _ask("Hit dice (e.g. 1d8)", "1d8")},
        "attacks": _collect_named_list("Attacks", ["bonus", "damage", "range"]),
        "attack_note": _ask("Attack note (optional)"),
        "equipment": _collect_simple_list("Equipment"),
        "currency": {k: _ask(f"Currency: {k}") for k in CURRENCY_KEYS},
        "personality": {
            "traits": _ask("Personality traits"),
            "ideals": _ask("Ideals"),
            "bonds": _ask("Bonds"),
            "flaws": _ask("Flaws"),
        },
        "features": _collect_named_list("Features", ["text"]),
        "appearance": {
            f: _ask(f"Appearance: {f}")
            for f in ["age", "height", "weight", "eyes", "skin", "hair"]
        },
        "backstory": _ask("Backstory"),
        "allies": _collect_named_list("Allies", ["text"]),
        "treasure": {
            "title": _ask("Treasure title (optional)"),
            "text": _ask("Treasure text (optional)"),
        },
        "additional_features": _ask("Additional features/notes (optional)"),
    }
    spellcasting = _build_spellcasting()
    if spellcasting is not None:
        details["spellcasting"] = spellcasting
    return details


def _build_skeleton_details():
    return {
        "other_proficiencies": {
            "languages": "",
            "armor": "",
            "weapons": "",
            "tools": "",
        },
        "combat": {"ac": 10, "initiative": "+0", "speed": "30 ft"},
        "hp": {"max": 10, "current": "", "temp": ""},
        "hit_dice": {"total": "1d8"},
        "attacks": [],
        "attack_note": "",
        "equipment": [],
        "currency": {k: "" for k in CURRENCY_KEYS},
        "personality": {"traits": "", "ideals": "", "bonds": "", "flaws": ""},
        "features": [],
        "appearance": {
            f: "" for f in ["age", "height", "weight", "eyes", "skin", "hair"]
        },
        "backstory": "",
        "allies": [],
        "treasure": {"title": "", "text": ""},
        "additional_features": "",
    }


def _write_character(out_path, char):
    DATA_DIR.mkdir(exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(char, f, sort_keys=False, allow_unicode=True)


def main():
    args = _parse_args()

    name = _resolve_name(args)
    char_id = _resolve_character_id(args, name)
    out_path = DATA_DIR / f"{char_id}.yaml"
    if not _confirm_overwrite(out_path):
        print("Aborted.")
        sys.exit(1)
    mode = _resolve_mode(args)

    char = {"id": char_id, "name": name, **_ask_identity_fields(), "xp": ""}

    if mode == "full":
        abilities, saves, skills, prof_bonus, passive_perception = (
            _full_abilities_saves_skills()
        )
    else:
        abilities, saves, skills, prof_bonus, passive_perception = (
            _skeleton_abilities_saves_skills()
        )

    char.update(
        inspiration=False,
        proficiency_bonus=_fmt_mod(prof_bonus),
        abilities=abilities,
        saves=saves,
        skills=skills,
        passive_perception=passive_perception,
    )
    char.update(
        _build_full_details(abilities) if mode == "full" else _build_skeleton_details()
    )

    _write_character(out_path, char)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
