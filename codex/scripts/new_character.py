#!/usr/bin/env python3
"""Interactively generate a new codex data/<id>.yaml character file.

Run from anywhere with PyYAML installed (the codex venv already has it):

    python scripts/new_character.py

Answers are forgiving: Enter keeps the [default], names are matched without
regard to case (and by unique first letters, e.g. "ath" for Athletics), and a
typo is explained and asked again instead of being dropped.

Two modes (asked as "quick" or "detailed"; --mode takes skeleton or full):
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

# 2014 PHB (plus Artificer) hit die size per class, used as the prompt default.
HIT_DIE = {
    "barbarian": 12,
    "bard": 8,
    "cleric": 8,
    "druid": 8,
    "fighter": 10,
    "monk": 8,
    "paladin": 10,
    "ranger": 10,
    "rogue": 8,
    "sorcerer": 6,
    "warlock": 8,
    "wizard": 6,
    "artificer": 8,
}

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
APPEARANCE_PROMPTS = {
    "age": "Age",
    "height": "Height",
    "weight": "Weight",
    "eyes": "Eyes",
    "skin": "Skin",
    "hair": "Hair",
    "gender": "Gender (optional, shown on the sheet only if set)",
    "faith": "Faith (optional, shown on the sheet only if set)",
}
GUIDE_URLS = {
    "2014": (
        "https://www.dndbeyond.com/sources/dnd/basic-rules-2014/"
        "step-by-step-characters"
    ),
    "2024": "https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character",
}
MODE_NAMES = {
    "quick": "skeleton",
    "detailed": "full",
    "skeleton": "skeleton",
    "full": "full",
}


def _slugify(name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_")
    return slug or "character"


def _ability_mod(score):
    return (score - 10) // 2


def _fmt_mod(n):
    return f"+{n}" if n >= 0 else str(n)


def _proficiency_bonus(level):
    return 2 + (max(level, 1) - 1) // 4


def _section(title, hint):
    print(f"\n=== {title} ===\n  {hint}")


def _ask(prompt_text, default=""):
    suffix = f" [{default}]" if default else ""
    return input(f"{prompt_text}{suffix}: ").strip() or default


def _ask_int(prompt_text, default=0):
    while True:
        try:
            return int(_ask(prompt_text, str(default)))
        except ValueError:
            print("  please type a whole number, like 12")


def _ask_yn(prompt_text, default=False):
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt_text} [{suffix}]: ").strip().lower()
    return value.startswith("y") if value else default


def _match_name(token, valid_names):
    wanted = token.strip().lower()
    for name in valid_names:
        if name.lower() == wanted:
            return name
    starts = [n for n in valid_names if n.lower().startswith(wanted)]
    return starts[0] if wanted and len(starts) == 1 else None


def _parse_names(raw, valid_names):
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    matches = {t: _match_name(t, valid_names) for t in tokens}
    unknown = [t for t, name in matches.items() if name is None]
    return {name for name in matches.values() if name}, unknown


def _ask_names(prompt_text, valid_names):
    choices = sorted(valid_names)
    example = ", ".join(choices[:2])
    hint = f"comma-separated, e.g. {example}" if example else "comma-separated"
    while True:
        chosen, unknown = _parse_names(
            _ask(f"{prompt_text} ({hint}; blank for none)"), choices
        )
        if not unknown:
            return chosen
        print(f"  not recognized: {', '.join(unknown)}")
        print(f"  choices: {', '.join(choices)}")


def _collect_simple_list(label):
    print(f"{label} (blank line to finish):")
    items = []
    while True:
        item = input("  - ").strip()
        if not item:
            break
        items.append(item)
    return items


def _print_example(fields, example):
    print("  Example entry, as the prompts will ask:")
    for field, value in zip(["name", *fields], example):
        print(f"    {field}: {value}")
    print("  Your entries:")


def _collect_named_list(label, fields, example=(), explain=""):
    print(f"{label} (blank name to finish):")
    if explain:
        print(f"  {explain}")
    if example:
        _print_example(fields, example)
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


def _skeleton_abilities_saves_skills(level=1):
    abilities = [{"name": a, "score": 10, "mod": "+0"} for a in ABILITIES]
    saves = [{"name": a, "mod": "+0", "prof": False} for a in ABILITIES]
    skills = [
        {"name": s, "ability": ABILITY_ABBR[a], "mod": "+0", "prof": False}
        for s, a in SKILLS
    ]
    return abilities, saves, skills, _proficiency_bonus(level), 10


def _ask_ability_inputs(level):
    _section("Ability scores", "Press Enter to keep 10.")
    scores = {a: _ask_int(f"  {a}", 10) for a in ABILITIES}
    prof_bonus = _proficiency_bonus(level)
    _section(
        "Proficiencies",
        f"Total level {level}, proficiency bonus {_fmt_mod(prof_bonus)}.",
    )
    prof_saves = _ask_names("Proficient saving throws", ABILITIES)
    prof_skills = _ask_names("Proficient skills", [s for s, _ in SKILLS])
    expertise = _ask_names("Skills with expertise (must be proficient)", prof_skills)
    return scores, prof_bonus, prof_saves, prof_skills, expertise


def _skill_proficiency(skill, prof_skills, expertise):
    if skill in prof_skills and skill in expertise:
        return "expertise"
    return skill in prof_skills


def _compute_skill(skill, ability, mods, prof_bonus, prof_skills, expertise):
    prof = _skill_proficiency(skill, prof_skills, expertise)
    multiplier = {"expertise": 2, True: 1, False: 0}[prof]
    return {
        "name": skill,
        "ability": ABILITY_ABBR[ability],
        "mod": _fmt_mod(mods[ability] + prof_bonus * multiplier),
        "prof": prof,
    }


def _compute_abilities_saves_skills(
    scores, prof_bonus, prof_saves, prof_skills, expertise=frozenset()
):
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
        _compute_skill(s, a, mods, prof_bonus, prof_skills, expertise)
        for s, a in SKILLS
    ]
    perception_mod = int(next(sk["mod"] for sk in skills if sk["name"] == "Perception"))
    return abilities, saves, skills, prof_bonus, 10 + perception_mod


def _full_abilities_saves_skills(level=1):
    return _compute_abilities_saves_skills(*_ask_ability_inputs(level))


def _ask_spell_slots():
    print("Spell slots (blank level to finish):")
    print("  e.g. level 1st, then total slots 4")
    slots = []
    while True:
        level = input("  slot level: ").strip()
        if not level:
            break
        slots.append({"level": level, "total": _ask_int("    total slots", 1)})
    return slots


def _ask_comma_list(prompt_text):
    return [i.strip() for i in _ask(prompt_text).split(",") if i.strip()]


def _build_spellcasting():
    if not _ask_yn("Include spellcasting section?", False):
        return None
    slots = _ask_spell_slots()
    return {
        "class": _ask("Spellcasting class (or classes, e.g. 'Wizard / Cleric')"),
        "ability": _ask("Spellcasting ability (e.g. Intelligence)"),
        "save_dc": _ask_int("Spell save DC", 10),
        "attack_bonus": _ask("Spell attack bonus (e.g. +5)", "+0"),
        "note": _ask("Note (optional)"),
        "cantrips": _ask_comma_list("Cantrips (comma-separated)"),
        "slots": slots,
        "prepared": _ask_comma_list("Prepared spells (comma-separated)"),
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
    char_id = args.id or default_id
    while not ID_RE.fullmatch(char_id):
        print("  id must match ^[A-Za-z0-9_-]+$ (letters, numbers, underscore, hyphen)")
        char_id = _ask("File name for this character (no extension)", default_id)
    return char_id


def _confirm_overwrite(out_path):
    return not out_path.exists() or _ask_yn(
        f"{out_path} already exists, overwrite?", False
    )


def _resolve_mode(args):
    if args.mode:
        return args.mode
    _section(
        "How much detail?",
        "quick = basics now, fill in the rest later; "
        "detailed = walk through scores, gear, spells and backstory.",
    )
    while True:
        choice = _match_name(_ask("Quick or detailed (Q/D)", "quick"), list(MODE_NAMES))
        if choice:
            return MODE_NAMES[choice]
        print("  please type quick or detailed")


def _ask_edition():
    while True:
        edition = _ask("Rules edition (2014 or 2024)", "2014")
        if edition in ("2014", "2024"):
            return edition
        print("  please enter 2014 or 2024")


def _ask_class():
    name = _ask("Class (blank to finish)")
    if not name:
        return None
    return {
        "name": name,
        "level": max(_ask_int("  Level in this class", 1), 1),
        "subclass": _ask("  Subclass (optional)"),
        "die": _ask_int("  Hit die size (10 = d10)", HIT_DIE.get(name.lower(), 8)),
    }


def _ask_classes():
    _section("Classes", "Add one class at a time; multiclass = add several.")
    classes = []
    while (entry := _ask_class()) or not classes:
        if entry:
            classes.append(entry)
        else:
            print("  at least one class is required")
    return classes


def _total_level(classes):
    return sum(c["level"] for c in classes)


def _format_class_level(classes):
    return " / ".join(
        f"{c['name']} {c['level']}" + (f" ({c['subclass']})" if c["subclass"] else "")
        for c in classes
    )


def _format_hit_dice(classes):
    counts = {}
    for c in classes:
        counts[c["die"]] = counts.get(c["die"], 0) + c["level"]
    return " + ".join(f"{n}d{die}" for die, n in counts.items())


def _ask_identity_fields(edition):
    return {
        "background": _ask("Background"),
        "player_name": _ask("Player name"),
        "edition": edition,
        "race": _ask("Species" if edition == "2024" else "Race"),
        "alignment": _ask("Alignment"),
    }


def _ask_other_proficiencies():
    _section("Other proficiencies", "Free text, e.g. armor: Light, Medium, Shields.")
    return {
        "languages": _ask("Languages", "Common"),
        "armor": _ask("Armor proficiencies"),
        "weapons": _ask("Weapon proficiencies"),
        "tools": _ask("Tool proficiencies"),
    }


def _ask_combat(dex_mod):
    _section("Combat", "Enter keeps the default shown in [brackets].")
    return {
        "ac": _ask_int("Armor Class", 10),
        "initiative": _ask("Initiative", dex_mod),
        "speed": _ask("Speed", "30 ft"),
    }


def _ask_personality():
    _section("Personality", "One line each; blank to skip.")
    return {
        "traits": _ask("Personality traits"),
        "ideals": _ask("Ideals"),
        "bonds": _ask("Bonds"),
        "flaws": _ask("Flaws"),
    }


def _ask_appearance():
    _section("Appearance", "One line each; blank to skip.")
    return {
        key: _ask(f"Appearance: {text}") for key, text in APPEARANCE_PROMPTS.items()
    }


def _ask_attacks():
    return _collect_named_list(
        "Attacks",
        ["bonus", "damage", "range", "notes"],
        ("Longsword", "+5", "1d8+3 slashing", "5 ft"),
        "Weapons and other attacks. Bonus is your to-hit number; notes are optional.",
    )


def _ask_features():
    return _collect_named_list(
        "Features and traits",
        ["text"],
        ("Second Wind", "Heal 1d10+3 once per rest"),
        "Special abilities from your class, race or species, background or "
        "feats that aren't attacks or spells.\n  Look them up in your "
        "character's book pages.",
    )


def _ask_allies():
    return _collect_named_list(
        "Allies",
        ["text"],
        ("Marta", "Innkeeper who owes me a favor"),
        "Friends, companions or groups you can call on.",
    )


def _build_full_details(abilities):
    dex_mod = next(a["mod"] for a in abilities if a["name"] == "Dexterity")
    details = {
        "other_proficiencies": _ask_other_proficiencies(),
        "combat": _ask_combat(dex_mod),
        "hp": {"max": _ask_int("Max HP", 10), "current": "", "temp": ""},
        "hit_dice": {"total": "1d8"},
        "attacks": _ask_attacks(),
        "attack_note": _ask("Attack note (optional)"),
        "equipment": _collect_simple_list("Equipment"),
        "currency": {k: _ask(f"Currency: {k}") for k in CURRENCY_KEYS},
        "personality": _ask_personality(),
        "features": _ask_features(),
        "appearance": _ask_appearance(),
        "backstory": _ask("Backstory"),
        "allies": _ask_allies(),
        "treasure": _collect_simple_list("Treasure, one item per line"),
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
        "appearance": {key: "" for key in APPEARANCE_PROMPTS},
        "backstory": "",
        "allies": [],
        "treasure": [],
        "additional_features": "",
    }


_MODE_HANDLERS = {
    "full": (_full_abilities_saves_skills, _build_full_details),
    "skeleton": (
        _skeleton_abilities_saves_skills,
        lambda abilities: _build_skeleton_details(),
    ),
}


def _write_character(out_path, char):
    DATA_DIR.mkdir(exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(char, f, sort_keys=False, allow_unicode=True)


def _build_character(char_id, name, mode, edition):
    classes = _ask_classes()
    char = {
        "id": char_id,
        "name": name,
        "class_level": _format_class_level(classes),
        **_ask_identity_fields(edition),
        "xp": "",
    }

    stats_fn, details_fn = _MODE_HANDLERS[mode]
    abilities, saves, skills, prof_bonus, passive_perception = stats_fn(
        _total_level(classes)
    )

    char.update(
        inspiration=False,
        proficiency_bonus=_fmt_mod(prof_bonus),
        abilities=abilities,
        saves=saves,
        skills=skills,
        passive_perception=passive_perception,
    )
    char.update(details_fn(abilities))
    char["hit_dice"]["total"] = _format_hit_dice(classes)
    return char


def _print_welcome():
    print("New character. Answer each question and press Enter.")
    print("Enter on its own keeps the [default] or skips the question.")
    print("Everything can be edited in the file afterward.")


def _print_guide(edition):
    print(f"New to D&D? Step-by-step guide for the {edition} rules:")
    print(f"  {GUIDE_URLS[edition]}")


def _print_next_steps(out_path):
    print(f"\nSaved your character to {out_path}")
    print("Next: open that file in any text editor to fill in anything you skipped.")
    print("Real characters are private; do not commit them to git.")


def _run():
    args = _parse_args()
    _print_welcome()

    edition = _ask_edition()
    _print_guide(edition)
    mode = _resolve_mode(args)
    name = _resolve_name(args)
    char_id = _resolve_character_id(args, name)
    out_path = DATA_DIR / f"{char_id}.yaml"
    if not _confirm_overwrite(out_path):
        print("Aborted.")
        sys.exit(1)

    _write_character(out_path, _build_character(char_id, name, mode, edition))
    _print_next_steps(out_path)


def _cancel():
    print("\n\nCancelled. Nothing was saved.")
    sys.exit(130)


def main():
    # Separate clauses: Black targets py314 and would rewrite a tuple except
    # into syntax that older Pythons (friends running the script) cannot parse.
    try:
        _run()
    except KeyboardInterrupt:
        _cancel()
    except EOFError:
        _cancel()


if __name__ == "__main__":
    main()
