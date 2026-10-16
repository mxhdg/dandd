#!/usr/bin/env python3
"""Create or level up a codex character (data/<id>.yaml), interactively.

Run from anywhere with PyYAML installed (the codex venv already has it):

    python scripts/character.py               asks what you want to do
    python scripts/character.py --new         create a character
    python scripts/character.py --level-up [ID]   advance an existing character
    python scripts/character.py --edit [ID]       change anything on one
                                              (ID is asked for if omitted)

Level-up validates the file first, asks for the class that rises, hit points,
any ability score improvement or feat, new features and spell changes, shows
every changed field and asks before saving. Edit is a menu of sections (identity,
ability scores, combat, attacks, gear, features, spells, story, proficiencies)
showing each current value: Enter keeps it, - clears it. Either way the previous
file is kept as <id>.yaml.bak; state/<id>.yaml is never touched.

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
import copy
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))  # character_schema.py
from character_schema import validate_character  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_DIR = Path(__file__).parent.parent / "state"

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
ASI_LEVELS = {4, 8, 12, 16, 19}
ACTION_NAMES = ["new", "level-up", "edit"]
CLASS_PART = re.compile(r"\s*(.+?)\s+(\d+)\s*(?:\((.*)\))?\s*")
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


def _names_hint(choices, current):
    if current is not None:
        shown = ", ".join(sorted(current)) or "none"
        return f"comma-separated; blank keeps: {shown}; - for none"
    example = ", ".join(choices[:2])
    hint = f"comma-separated, e.g. {example}" if example else "comma-separated"
    return f"{hint}; blank for none"


def _ask_names(prompt_text, valid_names, current=None):
    choices = sorted(valid_names)
    hint = _names_hint(choices, current)
    while True:
        raw = _ask(f"{prompt_text} ({hint})")
        if current is not None and raw in ("", "-"):
            return set() if raw == "-" else set(current)
        chosen, unknown = _parse_names(raw, choices)
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
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--new", action="store_true", help="create a new character")
    actions.add_argument(
        "--level-up",
        nargs="?",
        const="",
        metavar="ID",
        help="level up an existing character (asks which one if ID is omitted)",
    )
    actions.add_argument(
        "--edit",
        nargs="?",
        const="",
        metavar="ID",
        help="change anything on an existing character (asks which if ID is omitted)",
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


def _ask_edition(default="2014"):
    while True:
        edition = _ask("Rules edition (2014 or 2024)", default)
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


# --- level-up: pure helpers --------------------------------------------------


def _parse_class_level(text):
    """'Fighter 3 (Champion) / Ranger 1' as class entries, or None if unreadable."""
    classes = []
    for part in text.split("/"):
        match = CLASS_PART.fullmatch(part)
        if not match:
            return None
        name, level, subclass = match.groups()
        die = HIT_DIE.get(name.lower())
        classes.append(
            {"name": name, "level": int(level), "subclass": subclass or "", "die": die}
        )
    return classes


def _scores_of(char):
    return {a["name"]: a["score"] for a in char["abilities"]}


def _proficiency_inputs(char):
    saves = {s["name"] for s in char["saves"] if s["prof"]}
    skills = {s["name"] for s in char["skills"] if s["prof"]}
    expertise = {s["name"] for s in char["skills"] if s["prof"] == "expertise"}
    return saves, skills, expertise


def _apply_asi(scores, abilities):
    """+2 to one ability, or +1 to each of two; never above 20."""
    bonus = 2 if len(abilities) == 1 else 1
    return {n: min(20, s + bonus) if n in abilities else s for n, s in scores.items()}


def _shift(existing, old_formula, new_formula):
    """Move a stored modifier by the change in its formula, keeping custom bonuses."""
    if old_formula is None or new_formula is None:
        return existing
    try:
        delta = int(existing) - int(old_formula)
    except ValueError:
        return existing
    return _fmt_mod(int(new_formula) + delta)


def _shift_entries(existing, old_formula, new_formula):
    old_by = {e["name"]: e["mod"] for e in old_formula}
    new_by = {e["name"]: e["mod"] for e in new_formula}
    return [
        {**e, "mod": _shift(e["mod"], old_by.get(e["name"]), new_by.get(e["name"]))}
        for e in existing
    ]


def _inputs_of(char, level):
    """What the derived values are computed from: scores, level, proficiencies."""
    saves, skills, expertise = _proficiency_inputs(char)
    scores = _scores_of(char)
    return {
        "scores": scores,
        "level": level,
        "saves": saves,
        "skills": skills,
        "expertise": expertise,
    }


def _formulas_of(inputs):
    return _compute_abilities_saves_skills(
        inputs["scores"],
        _proficiency_bonus(inputs["level"]),
        inputs["saves"],
        inputs["skills"],
        inputs["expertise"],
    )


def _with_prof_flags(entries, flag_of):
    return [{**entry, "prof": flag_of(entry["name"])} for entry in entries]


def _recomputed_stats(old, old_inputs, new_inputs):
    """Derived values after a change, shifted so custom bonuses are kept."""
    old_f, new_f = _formulas_of(old_inputs), _formulas_of(new_inputs)
    abilities = _shift_entries(old["abilities"], old_f[0], new_f[0])
    for entry in abilities:
        entry["score"] = new_inputs["scores"][entry["name"]]
    saves = _shift_entries(old["saves"], old_f[1], new_f[1])
    skills = _shift_entries(old["skills"], old_f[2], new_f[2])
    dex_old, dex_new = old_f[0][1]["mod"], new_f[0][1]["mod"]
    return {
        "proficiency_bonus": _fmt_mod(new_f[3]),
        "abilities": abilities,
        "saves": _with_prof_flags(saves, lambda n: n in new_inputs["saves"]),
        "skills": _with_prof_flags(
            skills,
            lambda n: _skill_proficiency(
                n, new_inputs["skills"], new_inputs["expertise"]
            ),
        ),
        "passive_perception": old["passive_perception"] + new_f[4] - old_f[4],
        "initiative": _shift(old["combat"]["initiative"], dex_old, dex_new),
    }


def _apply_stats(char, stats):
    stats = dict(stats)
    char["combat"]["initiative"] = stats.pop("initiative")
    char.update(stats)


def _level_up_character(old, choices):
    """The character after one level, from the player's choices (pure)."""
    new = copy.deepcopy(old)
    old_inputs = _inputs_of(old, choices["old_level"])
    new_inputs = {
        **old_inputs,
        "scores": choices["scores"],
        "level": _total_level(choices["classes"]),
    }
    _apply_stats(new, _recomputed_stats(old, old_inputs, new_inputs))
    new["class_level"] = _format_class_level(choices["classes"])
    new["hit_dice"]["total"] = _format_hit_dice(choices["classes"])
    new["hp"]["max"] += choices["hp_gain"]
    new["features"] = list(old["features"]) + choices["features"]
    if choices["spellcasting"] is not None:
        new["spellcasting"] = choices["spellcasting"]
    return new


def _hp_gain(roll, con_mod, con_shift, level_before):
    """New hit die plus CON (at least 1); a CON modifier change counts retroactively."""
    return max(1, roll + con_mod) + con_shift * level_before


def _flatten(value, path=""):
    if isinstance(value, dict):
        children = [(f"{path}.{k}" if path else str(k), v) for k, v in value.items()]
    elif isinstance(value, list):
        children = [(f"{path}[{i}]", v) for i, v in enumerate(value)]
    else:
        return {path: value}
    flat = {}
    for child_path, child in children:
        flat.update(_flatten(child, child_path))
    return flat


def _diff_lines(old, new):
    before, after = _flatten(old), _flatten(new)
    lines = []
    for path in before.keys() | after.keys():
        if before.get(path) != after.get(path):
            lines.append(f"  {path}: {before.get(path, '(none)')} -> {after.get(path)}")
    return sorted(lines)


def _review_warnings(old, new):
    """Things levelling cannot recalculate, so the player should check them."""
    warnings = []
    changed = any(old[k] != new[k] for k in ("proficiency_bonus", "abilities"))
    if changed and old["attacks"]:
        names = ", ".join(a["name"] for a in old["attacks"])
        warnings.append(f"Attack bonuses and damage are not recalculated: {names}")
    if _scores_of(old)["Dexterity"] != _scores_of(new)["Dexterity"]:
        warnings.append("Dexterity changed: check Armor Class")
    return warnings


def _state_warnings(state, new):
    """Spell slots marked used in state/<id>.yaml that no longer fit."""
    totals = {
        str(s["level"]): s["total"]
        for s in new.get("spellcasting", {}).get("slots", [])
    }
    warnings = []
    for level, used in (state.get("slot_used") or {}).items():
        if used and used > totals.get(str(level), 0):
            total = totals.get(str(level), 0)
            warnings.append(f"State: {used} {level} slots used, new total is {total}")
    return warnings


def _has_comments(text):
    return any(
        line.lstrip().startswith("#") or " #" in line for line in text.splitlines()
    )


# --- level-up: prompts -------------------------------------------------------


def _ask_choice(count):
    """A 1-based menu choice, asked until it is in range; returned 0-based."""
    choice = _ask_int("Choice", 1)
    while not 1 <= choice <= count:
        print("  please pick one of the numbers above")
        choice = _ask_int("Choice", 1)
    return choice - 1


def _ask_required(prompt_text):
    value = _ask(prompt_text)
    while not value:
        value = _ask(f"{prompt_text} (required)")
    return value


def _character_ids():
    return sorted(path.stem for path in DATA_DIR.glob("*.yaml"))


def _pick_character(ids):
    _section("Which character?", "Pick a number.")
    for number, char_id in enumerate(ids, 1):
        print(f"  {number}) {char_id}")
    return ids[_ask_choice(len(ids))]


def _resolve_existing_id(raw):
    ids = _character_ids()
    if not ids:
        print("No characters found in data/. Create one first.")
        sys.exit(1)
    chosen = _match_name(raw, ids) if raw else _pick_character(ids)
    if chosen is None:
        print(f"No character matches '{raw}'. Available: {', '.join(ids)}")
        sys.exit(1)
    return chosen


def _refuse(path, problems):
    print(f"\n{path.name} has problems, so it can't be changed yet:")
    for problem in problems:
        print(f"  - {problem}")
    print("Fix them in the file (see data/character_template.yaml.example).")
    sys.exit(1)


def _load_character_file(path):
    """(data, original text) of a valid character file; otherwise exits."""
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        _refuse(path, [f"not valid YAML: {' '.join(str(err).split())}"])
    problems = validate_character(data)
    if problems:
        _refuse(path, problems)
    return data, text


def _ask_new_class():
    name = _ask_required("New class name")
    return {
        "name": name,
        "level": 1,
        "subclass": _ask("  Subclass (optional)"),
        "die": _ask_int("  Hit die size (10 = d10)", HIT_DIE.get(name.lower(), 8)),
    }


def _ask_advance_class(classes):
    """The class list after one level, and the index of the class that rose."""
    classes = [dict(c) for c in classes]
    _section("Which class gains a level?", "Pick a number, or add a new class.")
    for number, c in enumerate(classes, 1):
        print(f"  {number}) {c['name']} {c['level']}")
    print(f"  {len(classes) + 1}) a new class (multiclass)")
    index = _ask_choice(len(classes) + 1)
    if index == len(classes):
        classes.append(_ask_new_class())
    else:
        classes[index]["level"] += 1
    return classes, index


def _ask_class_details(entry):
    """Fill in a hit die the class table doesn't know, and a subclass at level 3+."""
    if entry["die"] is None:
        entry["die"] = _ask_int("  Hit die size (10 = d10)", 8)
    if entry["level"] >= 3 and not entry["subclass"]:
        entry["subclass"] = _ask("  Subclass (optional)")


def _resolve_classes(char):
    classes = _parse_class_level(char["class_level"])
    if classes is None:
        print("  Could not read the class and level; please enter them.")
        classes = _ask_classes()
    return classes


def _ask_asi_abilities():
    prompt = "Ability to raise (one name = +2, two names = +1 each)"
    chosen = _ask_names(prompt, ABILITIES)
    while len(chosen) not in (1, 2):
        print("  please name one or two abilities")
        chosen = _ask_names(prompt, ABILITIES)
    return chosen


def _ask_asi_or_feat(class_level):
    """(abilities to raise, feat entry or None); at most one is used."""
    if not _ask_yn("Ability score improvement or feat?", class_level in ASI_LEVELS):
        return set(), None
    if _ask_yn("Take a feat instead of raising ability scores?", False):
        feat = {"name": _ask_required("Feat name"), "text": _ask("What it does")}
        return set(), feat
    return _ask_asi_abilities(), None


def _ask_hp_roll(die):
    average = die // 2 + 1
    return _ask_int(
        f"Hit die roll (d{die}; Enter uses the average, {average})", average
    )


def _format_slots(slots):
    return ", ".join(f"{s['level']}: {s['total']}" for s in slots) or "none"


def _ask_slots_and_dc(spellcasting, mods, prof_bonus):
    print(f"Current spell slots: {_format_slots(spellcasting.get('slots', []))}")
    if _ask_yn("Change spell slots?", True):
        spellcasting["slots"] = _ask_spell_slots()
    ability_mod = mods.get(spellcasting.get("ability"))
    if ability_mod is not None:
        base = prof_bonus + ability_mod
        spellcasting["save_dc"] = _ask_int("Spell save DC", 8 + base)
        spellcasting["attack_bonus"] = _ask("Spell attack bonus", _fmt_mod(base))
    return spellcasting


def _ask_spellcasting_update(spellcasting, mods, prof_bonus):
    spellcasting = copy.deepcopy(spellcasting)
    for key, label in (("cantrips", "New cantrips"), ("prepared", "New spells")):
        spellcasting[key] = list(spellcasting.get(key, [])) + _ask_comma_list(
            f"{label} (comma-separated, blank for none)"
        )
    return _ask_slots_and_dc(spellcasting, mods, prof_bonus)


def _ask_hp_gain(old, scores, die, old_level):
    con_old = _ability_mod(_scores_of(old)["Constitution"])
    con_new = _ability_mod(scores["Constitution"])
    if con_new != con_old:
        print(
            "  Constitution modifier changed: max HP also adjusts for earlier levels."
        )
    return _hp_gain(_ask_hp_roll(die), con_new, con_new - con_old, old_level)


def _ask_level_features(feat):
    features = _ask_features()
    return features + ([feat] if feat else [])


def _ask_spells_if_any(old, scores, classes):
    if "spellcasting" not in old:
        return None
    mods = {name: _ability_mod(score) for name, score in scores.items()}
    prof_bonus = _proficiency_bonus(_total_level(classes))
    return _ask_spellcasting_update(old["spellcasting"], mods, prof_bonus)


def _gather_choices(old):
    classes, index = _ask_advance_class(_resolve_classes(old))
    entry = classes[index]
    _ask_class_details(entry)
    old_level = _total_level(classes) - 1
    abilities, feat = _ask_asi_or_feat(entry["level"])
    scores = _apply_asi(_scores_of(old), abilities)
    return {
        "classes": classes,
        "scores": scores,
        "old_level": old_level,
        "hp_gain": _ask_hp_gain(old, scores, entry["die"], old_level),
        "features": _ask_level_features(feat),
        "spellcasting": _ask_spells_if_any(old, scores, classes),
    }


# --- level-up: review and save ----------------------------------------------


def _load_state(char_id):
    path = STATE_DIR / f"{char_id}.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _print_review(old, new, state):
    print("\nChanges:")
    for line in _diff_lines(old, new):
        print(line)
    for warning in _review_warnings(old, new) + _state_warnings(state, new):
        print(f"\nCheck: {warning}")
    if state:
        print("\n(state/ is not touched: current HP, slots used and conditions stay.)")


def _save_with_backup(path, text, new):
    backup = path.with_name(path.name + ".bak")
    backup.write_text(text, encoding="utf-8")
    _write_character(path, new)
    return backup


def _review_and_save(path, old, new, text):
    _print_review(old, new, _load_state(path.stem))
    if _has_comments(text):
        print("\nNote: comments in the file are not kept when it is saved.")
    if not _ask_yn("Save these changes?", True):
        print("Aborted. Nothing was changed.")
        sys.exit(1)
    backup = _save_with_backup(path, text, new)
    print(f"\nSaved {path}\nThe previous version is kept as {backup.name}.")


# --- edit: prompts with the current value shown ------------------------------

IDENTITY_LABELS = {
    "name": "Name",
    "class_level": "Class and level (use --level-up to gain a level)",
    "background": "Background",
    "player_name": "Player name",
    "race": "Race or species",
    "alignment": "Alignment",
    "xp": "Experience points",
}
PERSONALITY_LABELS = {
    "traits": "Personality traits",
    "ideals": "Ideals",
    "bonds": "Bonds",
    "flaws": "Flaws",
}
PROFICIENCY_LABELS = {
    "languages": "Languages",
    "armor": "Armor proficiencies",
    "weapons": "Weapon proficiencies",
    "tools": "Tool proficiencies",
}
APPEARANCE_LABELS = {key: text for key, text in APPEARANCE_PROMPTS.items()}
EDIT_HINT = "Enter keeps the value shown in [brackets]; type - to clear it."


def _ask_value(label, current):
    """Prompt showing the current value: Enter keeps it, '-' clears it."""
    raw = _ask(label, str(current)) if current != "" else _ask(label)
    if raw == "-":
        return ""
    if raw == str(current):
        return current
    numeric = raw.lstrip("+-").isdigit()
    return int(raw) if isinstance(current, int) and numeric else raw


def _ask_fields(section, labels):
    """A copy of section with each labelled field asked; unset blanks stay unset."""
    updated = dict(section)
    for key, label in labels.items():
        value = _ask_value(label, section.get(key, ""))
        if key in section or value != "":
            updated[key] = value
    return updated


def _item_name(item):
    if isinstance(item, dict):
        return str(item.get("name") or item.get("text") or "")
    return str(item)


def _ask_removals(count):
    """0-based positions to remove, typed as comma-separated 1-based numbers."""
    while True:
        raw = _ask("Remove which numbers? (comma-separated, blank for none)")
        numbers = [token.strip() for token in raw.split(",") if token.strip()]
        if all(n.isdigit() and 1 <= int(n) <= count for n in numbers):
            return {int(n) - 1 for n in numbers}
        print("  please use the numbers shown")


def _edit_list(label, items, add_items):
    """Show the numbered items, drop the ones named, then add new ones."""
    print(f"\n{label}:")
    for number, item in enumerate(items, 1):
        print(f"  {number}) {_item_name(item)}")
    if not items:
        print("  (none yet)")
    removed = _ask_removals(len(items)) if items else set()
    kept = [item for position, item in enumerate(items) if position not in removed]
    return kept + add_items()


def _treasure_as_list(raw):
    if isinstance(raw, dict):
        item = {"name": raw.get("title") or "", "text": raw.get("text") or ""}
        return [item] if item["name"] or item["text"] else []
    return [raw] if isinstance(raw, str) else list(raw or [])


# --- edit: sections ----------------------------------------------------------


def _edit_identity(char):
    char = _ask_fields(char, IDENTITY_LABELS)
    char["edition"] = _ask_edition(char.get("edition", "2014"))
    return char


def _ask_ability_edits(inputs):
    _section("Ability scores", "Enter keeps the number shown.")
    scores = {a: _ask_int(f"  {a}", inputs["scores"][a]) for a in ABILITIES}
    skill_names = [name for name, _ in SKILLS]
    saves = _ask_names("Proficient saving throws", ABILITIES, inputs["saves"])
    skills = _ask_names("Proficient skills", skill_names, inputs["skills"])
    expertise = _ask_names(
        "Skills with expertise", skills, inputs["expertise"] & skills
    )
    return {
        **inputs,
        "scores": scores,
        "saves": saves,
        "skills": skills,
        "expertise": expertise,
    }


def _edit_abilities(char):
    level = _total_level(_resolve_classes(char))
    old_inputs = _inputs_of(char, level)
    new_inputs = _ask_ability_edits(old_inputs)
    _apply_stats(char, _recomputed_stats(char, old_inputs, new_inputs))
    return char


def _edit_combat(char):
    char["combat"] = _ask_fields(
        char["combat"], {"initiative": "Initiative", "speed": "Speed"}
    )
    char["combat"]["ac"] = _ask_int("Armor Class", char["combat"]["ac"])
    char["hp"]["max"] = _ask_int("Max HP", char["hp"]["max"])
    char["hit_dice"]["total"] = _ask_value("Hit dice", char["hit_dice"]["total"])
    return char


def _edit_attacks(char):
    char["attacks"] = _edit_list("Attacks", char["attacks"], _ask_attacks)
    char["attack_note"] = _ask_value("Attack note", char.get("attack_note", ""))
    return char


def _edit_gear(char):
    add_gear = lambda: _collect_simple_list("Add equipment")  # noqa: E731
    add_loot = lambda: _collect_simple_list("Add treasure")  # noqa: E731
    char["equipment"] = _edit_list("Equipment", char["equipment"], add_gear)
    treasure = _treasure_as_list(char.get("treasure"))
    char["treasure"] = _edit_list("Treasure", treasure, add_loot)
    char["currency"] = _ask_fields(
        char["currency"], {k: f"Currency: {k}" for k in CURRENCY_KEYS}
    )
    return char


def _edit_features(char):
    char["features"] = _edit_list("Features", char["features"], _ask_features)
    char["allies"] = _edit_list("Allies", char["allies"], _ask_allies)
    return char


def _edit_spell_lists(spells):
    for key, label in (("cantrips", "Cantrips"), ("prepared", "Prepared spells")):
        add = lambda label=label: _ask_comma_list(  # noqa: E731
            f"Add to {label} (comma-separated, blank for none)"
        )
        spells[key] = _edit_list(label, list(spells.get(key, [])), add)
    return spells


def _edit_spellcasting(char):
    if "spellcasting" not in char:
        spellcasting = _build_spellcasting()
        if spellcasting is not None:
            char["spellcasting"] = spellcasting
        return char
    spells = _edit_spell_lists(char["spellcasting"])
    mods = {name: _ability_mod(score) for name, score in _scores_of(char).items()}
    prof_bonus = _proficiency_bonus(_total_level(_resolve_classes(char)))
    char["spellcasting"] = _ask_slots_and_dc(spells, mods, prof_bonus)
    return char


def _edit_story(char):
    char["personality"] = _ask_fields(char["personality"], PERSONALITY_LABELS)
    char["appearance"] = _ask_fields(char["appearance"], APPEARANCE_LABELS)
    for key, label in (("backstory", "Backstory"), ("additional_features", "Notes")):
        char[key] = _ask_value(label, char.get(key, ""))
    return char


def _edit_proficiencies(char):
    char["other_proficiencies"] = _ask_fields(
        char["other_proficiencies"], PROFICIENCY_LABELS
    )
    return char


EDIT_SECTIONS = [
    ("Identity and background", _edit_identity),
    ("Ability scores and proficiencies", _edit_abilities),
    ("Combat: AC, initiative, speed, HP, hit dice", _edit_combat),
    ("Attacks", _edit_attacks),
    ("Equipment, treasure and money", _edit_gear),
    ("Features and allies", _edit_features),
    ("Spellcasting", _edit_spellcasting),
    ("Personality, appearance and backstory", _edit_story),
    ("Languages and other proficiencies", _edit_proficiencies),
]


# --- edit: menu and run ------------------------------------------------------


def _apply_section(char, handler):
    """The character after one section, or unchanged if the result is invalid."""
    candidate = handler(copy.deepcopy(char))
    problems = validate_character(candidate)
    if problems:
        print("\n  That change was not kept, because the file would be invalid:")
        for problem in problems:
            print(f"    - {problem}")
        return char
    return candidate


def _print_edit_menu():
    _section("What would you like to change?", "Pick a number, or press Enter if done.")
    for number, (label, _) in enumerate(EDIT_SECTIONS, 1):
        print(f"  {number}) {label}")


def _edit_loop(char):
    print(f"\n{EDIT_HINT}")
    while True:
        _print_edit_menu()
        choice = _ask_int("Section", 0)
        if choice == 0:
            return char
        if 1 <= choice <= len(EDIT_SECTIONS):
            char = _apply_section(char, EDIT_SECTIONS[choice - 1][1])
        else:
            print("  please pick one of the numbers above")


def _run_edit(args):
    path = DATA_DIR / f"{_resolve_existing_id(args.edit)}.yaml"
    old, text = _load_character_file(path)
    new = _edit_loop(old)
    if not _diff_lines(old, new):
        print("\nNo changes were made.")
        return
    _review_and_save(path, old, new, text)


def _run_level_up(args):
    path = DATA_DIR / f"{_resolve_existing_id(args.level_up)}.yaml"
    old, text = _load_character_file(path)
    new = _level_up_character(old, _gather_choices(old))
    problems = validate_character(new)
    if problems:
        _refuse(path, problems)
    _review_and_save(path, old, new, text)


def _ask_action():
    _section(
        "What would you like to do?",
        "new = create a character; level-up = advance one you already have; "
        "edit = change anything on one you already have.",
    )
    while True:
        answer = _ask("New, level-up or edit (N/L/E)", "new").replace(" ", "-")
        choice = _match_name(answer, ACTION_NAMES)
        if choice:
            return choice
        print("  please type new, level-up or edit")


def _resolve_action(args):
    if args.new:
        return "new"
    if args.level_up is not None:
        return "level-up"
    if args.edit is not None:
        return "edit"
    return _ask_action()


def _print_welcome():
    print("Character tool. Answer each question and press Enter.")
    print("Enter on its own keeps the [default] or skips the question.")
    print("Everything can be edited in the file afterward.")


def _print_guide(edition):
    print(f"New to D&D? Step-by-step guide for the {edition} rules:")
    print(f"  {GUIDE_URLS[edition]}")


def _print_next_steps(out_path):
    print(f"\nSaved your character to {out_path}")
    print("Next: open that file in any text editor to fill in anything you skipped.")
    print("Real characters are private; do not commit them to git.")


def _run_new(args):
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


def _run():
    args = _parse_args()
    _print_welcome()
    handlers = {"new": _run_new, "level-up": _run_level_up, "edit": _run_edit}
    handlers[_resolve_action(args)](args)


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
