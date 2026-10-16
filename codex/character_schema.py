"""Table-driven validation for data/<id>.yaml character files.

The format lives in SCHEMA below as plain data, so supporting a new field is
one added line, not new code. A spec is one of:

  "str" "filled" "int" "bool" "text_or_int" "any"   a scalar kind
  ("list", item_spec)                                a list of item_spec
  ("named_list", item_spec, names)                   a list that must contain
                                                     one entry per name
  ("dict", {key: (spec, required)})                  a mapping; unknown keys
                                                     are allowed and ignored
  ("enum", [values])                                 one of the values
  ("any_of", [specs])                                the first spec that fits

validate_character() returns a list of problem strings (empty when valid),
each naming the field path, what was expected and what was found. It reports
every problem it finds, not just the first.
"""

ABILITIES = [
    "Strength",
    "Dexterity",
    "Constitution",
    "Intelligence",
    "Wisdom",
    "Charisma",
]
SKILL_NAMES = [
    "Acrobatics",
    "Animal Handling",
    "Arcana",
    "Athletics",
    "Deception",
    "History",
    "Insight",
    "Intimidation",
    "Investigation",
    "Medicine",
    "Nature",
    "Perception",
    "Performance",
    "Persuasion",
    "Religion",
    "Sleight of Hand",
    "Stealth",
    "Survival",
]

_REQ = True
_OPT = False
_TEXT_FIELDS = ("str", _OPT)

_SCALARS = {
    "str": (lambda v: isinstance(v, str), "text"),
    "filled": (lambda v: isinstance(v, str) and bool(v.strip()), "non-empty text"),
    "int": (lambda v: isinstance(v, int) and not isinstance(v, bool), "a whole number"),
    "bool": (lambda v: isinstance(v, bool), "true or false"),
    "text_or_int": (
        lambda v: isinstance(v, (str, int)) and not isinstance(v, bool),
        "text or a number",
    ),
    "any": (lambda v: True, "anything"),
}

_PROF = ("any_of", ["bool", ("enum", ["expertise"])])
_ENTRY_NAME_TEXT = ("dict", {"name": ("filled", _REQ), "text": ("str", _OPT)})
_TREASURE_ENTRY = ("dict", {"name": ("str", _OPT), "text": ("str", _OPT)})
# Treasure as written in a file: a list of text or {name, text} items, or the
# older single {title, text} box (the app normalizes either to a list).
_TREASURE_RAW = (
    "any_of",
    [
        ("list", ("any_of", ["str", _TREASURE_ENTRY])),
        ("dict", {"title": ("text_or_int", _OPT), "text": ("text_or_int", _OPT)}),
    ],
)
_SPELL_GROUP = ("dict", {"spells": ("text_or_int", _REQ), "note": ("str", _OPT)})
_SPELL_LIST = ("list", ("any_of", ["text_or_int", _SPELL_GROUP]))


def _text_dict(*keys):
    return ("dict", {key: ("text_or_int", _OPT) for key in keys})


_SCHEMA_FIELDS = {
    "id": ("filled", _REQ),
    "name": ("filled", _REQ),
    "class_level": ("str", _REQ),
    "background": _TEXT_FIELDS,
    "player_name": _TEXT_FIELDS,
    "edition": (("enum", ["2014", "2024"]), _OPT),
    "race": _TEXT_FIELDS,
    "alignment": _TEXT_FIELDS,
    "xp": ("text_or_int", _OPT),
    "inspiration": ("bool", _OPT),
    "proficiency_bonus": ("text_or_int", _REQ),
    "abilities": (
        (
            "named_list",
            (
                "dict",
                {
                    "name": ("filled", _REQ),
                    "score": ("int", _REQ),
                    "mod": ("text_or_int", _REQ),
                },
            ),
            ABILITIES,
        ),
        _REQ,
    ),
    "saves": (
        (
            "named_list",
            (
                "dict",
                {
                    "name": ("filled", _REQ),
                    "mod": ("text_or_int", _REQ),
                    "prof": ("bool", _REQ),
                },
            ),
            ABILITIES,
        ),
        _REQ,
    ),
    "skills": (
        (
            "named_list",
            (
                "dict",
                {
                    "name": ("filled", _REQ),
                    "ability": ("str", _REQ),
                    "mod": ("text_or_int", _REQ),
                    "prof": (_PROF, _REQ),
                },
            ),
            SKILL_NAMES,
        ),
        _REQ,
    ),
    "passive_perception": ("int", _REQ),
    "other_proficiencies": (
        _text_dict("languages", "armor", "weapons", "tools"),
        _REQ,
    ),
    "combat": (
        (
            "dict",
            {
                "ac": ("int", _REQ),
                "initiative": ("text_or_int", _REQ),
                "speed": ("text_or_int", _REQ),
            },
        ),
        _REQ,
    ),
    "hp": (
        (
            "dict",
            {
                "max": ("int", _REQ),
                "current": ("text_or_int", _OPT),
                "temp": ("text_or_int", _OPT),
            },
        ),
        _REQ,
    ),
    "hit_dice": (("dict", {"total": ("filled", _REQ)}), _REQ),
    "attacks": (
        (
            "list",
            (
                "dict",
                {
                    "name": ("filled", _REQ),
                    "bonus": ("text_or_int", _OPT),
                    "damage": ("text_or_int", _OPT),
                    "range": ("text_or_int", _OPT),
                    "notes": ("text_or_int", _OPT),
                },
            ),
        ),
        _REQ,
    ),
    "attack_note": _TEXT_FIELDS,
    "equipment": (("list", "text_or_int"), _REQ),
    "currency": (_text_dict("cp", "sp", "ep", "gp", "pp"), _REQ),
    "personality": (_text_dict("traits", "ideals", "bonds", "flaws"), _REQ),
    "features": (("list", _ENTRY_NAME_TEXT), _REQ),
    "appearance": (
        _text_dict(
            "age", "height", "weight", "eyes", "skin", "hair", "gender", "faith"
        ),
        _REQ,
    ),
    "backstory": _TEXT_FIELDS,
    "allies": (("list", _ENTRY_NAME_TEXT), _REQ),
    "treasure": (_TREASURE_RAW, _OPT),
    "additional_features": _TEXT_FIELDS,
}

_SPELLCASTING = (
    "dict",
    {
        "class": ("str", _OPT),
        "ability": ("str", _OPT),
        "save_dc": ("int", _OPT),
        "attack_bonus": ("text_or_int", _OPT),
        "note": ("str", _OPT),
        "cantrips": (_SPELL_LIST, _OPT),
        "slots": (
            (
                "list",
                (
                    "dict",
                    {
                        "level": ("text_or_int", _REQ),
                        "total": ("int", _REQ),
                    },
                ),
            ),
            _OPT,
        ),
        "prepared": (_SPELL_LIST, _OPT),
        "always_prepared": (_SPELL_LIST, _OPT),
        "cannon_modes": ("any", _OPT),
        "cannon_stats": ("any", _OPT),
    },
)

SCHEMA = ("dict", {**_SCHEMA_FIELDS, "spellcasting": (_SPELLCASTING, _OPT)})


def _found(value):
    shown = repr(value)
    if len(shown) > 40:
        shown = shown[:37] + "..."
    return f"{type(value).__name__} {shown}"


def _describe(spec):
    if isinstance(spec, str):
        return _SCALARS[spec][1]
    kind = spec[0]
    if kind == "enum":
        return "one of " + ", ".join(repr(v) for v in spec[1])
    if kind == "any_of":
        return " or ".join(_describe(s) for s in spec[1])
    return {"list": "a list", "named_list": "a list", "dict": "a mapping"}[kind]


def _check_scalar(spec, value, path):
    if _SCALARS[spec][0](value):
        return []
    return [f"{path}: expected {_describe(spec)}, found {_found(value)}"]


def _check_enum(spec, value, path):
    if value in spec[1]:
        return []
    return [f"{path}: expected {_describe(spec)}, found {_found(value)}"]


def _check_any_of(spec, value, path):
    if any(not _check(sub, value, path) for sub in spec[1]):
        return []
    return [f"{path}: expected {_describe(spec)}, found {_found(value)}"]


def _check_list(spec, value, path):
    if not isinstance(value, list):
        return [f"{path}: expected a list, found {_found(value)}"]
    problems = []
    for index, item in enumerate(value):
        problems += _check(spec[1], item, f"{path}[{index}]")
    return problems


def _check_named_list(spec, value, path):
    problems = _check_list(spec, value, path)
    if problems:
        return problems
    present = [item.get("name") for item in value if isinstance(item, dict)]
    missing = [name for name in spec[2] if name not in present]
    repeated = sorted({name for name in present if present.count(name) > 1})
    if missing:
        problems.append(f"{path}: missing {', '.join(missing)}")
    if repeated:
        problems.append(f"{path}: listed more than once: {', '.join(repeated)}")
    return problems


def _check_dict_field(key, field, value, path):
    spec, required = field
    if key not in value:
        return [f"{path}.{key}: required but missing"] if required else []
    return _check(spec, value[key], f"{path}.{key}")


def _check_dict(spec, value, path):
    if not isinstance(value, dict):
        return [f"{path}: expected a mapping, found {_found(value)}"]
    problems = []
    for key, field in spec[1].items():
        problems += _check_dict_field(key, field, value, path)
    return problems


_CHECKERS = {
    "list": _check_list,
    "named_list": _check_named_list,
    "dict": _check_dict,
    "enum": _check_enum,
    "any_of": _check_any_of,
}


def _check(spec, value, path):
    if isinstance(spec, str):
        return _check_scalar(spec, value, path)
    return _CHECKERS[spec[0]](spec, value, path)


def validate_character(data):
    """Problems found in a parsed character file, as readable strings."""
    return _check(SCHEMA, data, "file")
