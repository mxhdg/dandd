"""Tests for character_schema.py: the checker, the schema, and drift guards."""

import copy
from pathlib import Path

import yaml

import character_schema as schema

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "data" / "sample_character.yaml"
TEMPLATE = ROOT / "data" / "character_template.yaml.example"


def _sample():
    return yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))


def _problems(data):
    return schema.validate_character(data)


# --- the checker ------------------------------------------------------------


def test_scalar_kinds_accept_and_reject_the_right_values(cli):
    cases = [
        ("str", "x", True),
        ("str", 3, False),
        ("filled", "x", True),
        ("filled", "  ", False),
        ("int", 3, True),
        ("int", True, False),
        ("int", "3", False),
        ("bool", False, True),
        ("bool", 0, False),
        ("text_or_int", "+2", True),
        ("text_or_int", 2, True),
        ("text_or_int", True, False),
        ("text_or_int", [], False),
        ("any", object(), True),
    ]
    for kind, value, ok in cases:
        assert (schema._check(kind, value, "f") == []) is ok, (kind, value)


def test_problem_messages_name_the_path_expected_and_found(cli):
    [message] = schema._check("int", "ten", "file.hp.max")
    assert message == "file.hp.max: expected a whole number, found str 'ten'"
    [long_found] = schema._check("int", "x" * 90, "f")
    assert "..." in long_found and len(long_found) < 100


def test_list_dict_and_nesting_report_every_problem_with_paths(cli):
    spec = ("list", ("dict", {"n": ("filled", True), "v": ("int", False)}))
    problems = schema._check(spec, [{"n": "a"}, {"v": "x"}, "no", {"n": "ok"}], "L")
    assert problems == [
        "L[1].n: required but missing",
        "L[1].v: expected a whole number, found str 'x'",
        "L[2]: expected a mapping, found str 'no'",
    ]
    assert schema._check(spec, "not a list", "L") == [
        "L: expected a list, found str 'not a list'"
    ]


def test_dict_ignores_unknown_keys_and_skips_missing_optional_keys(cli):
    spec = ("dict", {"a": ("int", False)})
    assert schema._check(spec, {"extra": object()}, "d") == []


def test_enum_and_any_of(cli):
    enum = ("enum", ["2014", "2024"])
    assert schema._check(enum, "2024", "e") == []
    [problem] = schema._check(enum, 2024, "e")
    assert "expected one of '2014', '2024', found int 2024" in problem
    either = ("any_of", ["bool", ("enum", ["expertise"])])
    assert schema._check(either, True, "p") == []
    assert schema._check(either, "expertise", "p") == []
    [problem] = schema._check(either, "yes", "p")
    assert "expected true or false or one of 'expertise'" in problem


def test_named_list_requires_each_name_exactly_once(cli):
    spec = ("named_list", "any", ["A", "B", "C"])
    assert schema._check(spec, [{"name": "A"}, {"name": "B"}, {"name": "C"}], "x") == []
    problems = schema._check(spec, [{"name": "A"}, {"name": "A"}, "stray"], "x")
    assert problems == ["x: missing B, C", "x: listed more than once: A"]
    assert schema._check(spec, "nope", "x") == ["x: expected a list, found str 'nope'"]


# --- the character schema ---------------------------------------------------


def test_sample_character_is_valid():
    assert _problems(_sample()) == []


def test_template_is_valid_once_id_and_name_are_filled():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert {p.split(":")[0] for p in _problems(data)} == {"file.id", "file.name"}
    data.update(id="blank", name="Blank")
    assert _problems(data) == []


def test_real_world_spell_group_entries_are_valid():
    data = _sample()
    data["spellcasting"] = {
        "class": "Wizard",
        "ability": "Intelligence",
        "save_dc": 14,
        "attack_bonus": "+6",
        "note": "",
        "cantrips": ["Light"],
        "slots": [{"level": "1st", "total": 2}],
        "prepared": ["Shield"],
        "always_prepared": [{"spells": "Detect Magic", "note": "(racial)"}],
        "cannon_modes": [{"anything": "goes"}],
        "cannon_stats": {"anything": "goes"},
    }
    assert _problems(data) == []


def test_every_raw_treasure_shape_in_real_files_is_valid():
    shapes = [
        [],
        ["Jade ring", {"name": "Mug", "text": "Tin"}],
        {"title": "Staff of Frost", "text": "5 charges"},
        {"title": "", "text": ""},
    ]
    for treasure in shapes:
        data = _sample()
        data["treasure"] = treasure
        assert _problems(data) == [], treasure
    data = _sample()
    data["treasure"] = 5
    [problem] = _problems(data)
    assert problem.startswith("file.treasure: expected a list or a mapping")


def test_a_bad_spell_entry_says_what_shapes_are_accepted():
    data = _sample()
    data["spellcasting"] = {"prepared": [True], "always_prepared": [["nested"]]}
    problems = _problems(data)
    assert problems == [
        "file.spellcasting.prepared[0]: expected text or a number or a mapping, "
        "found bool True",
        "file.spellcasting.always_prepared[0]: expected text or a number or a "
        "mapping, found list ['nested']",
    ]


def test_every_problem_in_a_broken_file_is_reported_at_once(cli):
    data = _sample()
    data["edition"] = 2024
    data["hp"]["max"] = "ten"
    data["abilities"].pop()
    data["skills"][0]["prof"] = "yes"
    del data["combat"]
    problems = _problems(data)
    joined = "\n".join(problems)
    for expected in (
        "file.edition: expected one of '2014', '2024', found int 2024",
        "file.hp.max: expected a whole number, found str 'ten'",
        "file.abilities: missing Charisma",
        "file.skills[0].prof: expected true or false or one of 'expertise'",
        "file.combat: required but missing",
    ):
        assert expected in joined, expected
    assert len(problems) == 5


def test_a_file_that_is_not_a_mapping_is_one_clear_problem():
    for data in (None, [], "text", 3):
        [problem] = _problems(data)
        assert problem.startswith("file: expected a mapping"), data


def test_extra_fields_never_make_a_character_invalid():
    data = _sample()
    data["homebrew_note"] = {"anything": [1, 2, 3]}
    data["appearance"]["tattoos"] = "many"
    assert _problems(data) == []


# --- drift guards -----------------------------------------------------------


def test_schema_constants_match_the_script(cli):
    assert schema.ABILITIES == cli.ABILITIES
    assert schema.SKILL_NAMES == [name for name, _ in cli.SKILLS]


def test_script_output_always_passes_the_schema(cli, respond):
    for mode in ("skeleton", "full"):
        respond({"Class (": ["Rogue", ""], "Max HP": "9", "Spellcasting": "n"})
        char = cli._build_character("t", "Tess", mode, "2014")
        assert _problems(copy.deepcopy(char)) == [], mode
        assert yaml.safe_load(yaml.safe_dump(char)) == char
