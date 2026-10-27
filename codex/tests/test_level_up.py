"""Tests for the level-up flow in scripts/character.py (and its action flags)."""

import copy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SAMPLE_TEXT = (ROOT / "data" / "sample_character.yaml").read_text(encoding="utf-8")


def _sample():
    return yaml.safe_load(SAMPLE_TEXT)


@pytest.fixture
def dirs(cli, tmp_path, monkeypatch):
    """Isolated data/ and state/ directories for the script."""
    data, state = tmp_path / "data", tmp_path / "state"
    data.mkdir()
    state.mkdir()
    monkeypatch.setattr(cli, "DATA_DIR", data)
    monkeypatch.setattr(cli, "STATE_DIR", state)
    return data, state


def _choices(cli, **overrides):
    classes = [{"name": "Fighter", "level": 4, "subclass": "", "die": 10}]
    base = {
        "classes": classes,
        "scores": cli._scores_of(_sample()),
        "old_level": 3,
        "hp_gain": 8,
        "features": [],
        "spellcasting": None,
    }
    return {**base, **overrides}


# --- pure helpers -----------------------------------------------------------


def test_parse_class_level_reads_classes_subclasses_and_dice(cli):
    parsed = cli._parse_class_level("Fighter 3 (Champion) / Ranger 1")
    assert parsed == [
        {"name": "Fighter", "level": 3, "subclass": "Champion", "die": 10},
        {"name": "Ranger", "level": 1, "subclass": "", "die": 10},
    ]
    assert cli._parse_class_level("Homebrewer 2")[0]["die"] is None
    for unreadable in ("", "Fighter", "Fighter three", "Fighter 3 / "):
        assert cli._parse_class_level(unreadable) is None, unreadable


def test_scores_and_proficiency_inputs_come_from_the_file(cli):
    char = _sample()
    char["skills"][3]["prof"] = "expertise"
    assert cli._scores_of(char)["Strength"] == 16
    saves, skills, expertise = cli._proficiency_inputs(char)
    assert saves == {"Strength", "Constitution"}
    assert {"Athletics", "Perception"} <= skills and expertise == {"Athletics"}


def test_apply_asi_gives_plus_two_or_two_plus_ones_and_caps_at_twenty(cli):
    scores = {"Strength": 15, "Dexterity": 19, "Wisdom": 10}
    assert cli._apply_asi(scores, {"Strength"})["Strength"] == 17
    two = cli._apply_asi(scores, {"Strength", "Wisdom"})
    assert (two["Strength"], two["Wisdom"], two["Dexterity"]) == (16, 11, 19)
    assert cli._apply_asi(scores, {"Dexterity"})["Dexterity"] == 20
    assert cli._apply_asi(scores, set()) == scores


def test_shift_moves_a_modifier_by_the_formula_change_and_keeps_custom_bonuses(cli):
    cases = [
        ("+3", "+3", "+4", "+4"),
        ("+5", "+3", "+4", "+6"),
        (3, "+3", "+2", "+2"),
        ("+3", None, "+4", "+3"),
        ("+3", "+3", None, "+3"),
        ("-", "+3", "+4", "-"),
    ]
    for existing, old, new, expected in cases:
        assert cli._shift(existing, old, new) == expected, (existing, old, new)


def test_shift_entries_leaves_entries_the_formula_does_not_know(cli):
    existing = [{"name": "Athletics", "mod": "+5"}, {"name": "Custom", "mod": "+9"}]
    old = [{"name": "Athletics", "mod": "+3"}]
    new = [{"name": "Athletics", "mod": "+4"}]
    assert cli._shift_entries(existing, old, new) == [
        {"name": "Athletics", "mod": "+6"},
        {"name": "Custom", "mod": "+9"},
    ]


def test_recomputed_stats_follow_level_and_scores_but_keep_custom_bonuses(cli):
    char = _sample()
    char["skills"][11]["mod"] = "+4"  # Perception: +3 formula, +1 item bonus
    scores = cli._apply_asi(cli._scores_of(char), {"Dexterity"})
    old_inputs = cli._inputs_of(char, 3)
    new_inputs = {**old_inputs, "scores": scores, "level": 5}
    stats = cli._recomputed_stats(char, old_inputs, new_inputs)
    assert stats["proficiency_bonus"] == "+3"
    by_skill = {s["name"]: s["mod"] for s in stats["skills"]}
    assert by_skill["Athletics"] == "+6" and by_skill["Perception"] == "+5"
    by_save = {s["name"]: s["mod"] for s in stats["saves"]}
    assert by_save["Strength"] == "+6" and by_save["Dexterity"] == "+3"
    dex = next(a for a in stats["abilities"] if a["name"] == "Dexterity")
    assert (dex["score"], dex["mod"]) == (16, "+3")
    assert stats["initiative"] == "+3" and stats["passive_perception"] == 14


def test_level_up_character_applies_every_choice_and_stays_valid(cli):
    char = _sample()
    spells = {"class": "Wizard", "ability": "Intelligence", "slots": []}
    feature = {"name": "Action Surge", "text": "extra action"}
    choices = _choices(
        cli, features=[feature], spellcasting=spells, hp_gain=9, old_level=3
    )
    new = cli._level_up_character(char, choices)
    assert new["class_level"] == "Fighter 4" and new["hit_dice"]["total"] == "4d10"
    assert new["hp"]["max"] == char["hp"]["max"] + 9
    assert new["features"][-1] == feature and new["spellcasting"] == spells
    assert char["hp"]["max"] == 28  # the input is not modified
    assert cli.validate_character(new) == []
    plain = cli._level_up_character(char, _choices(cli))
    assert "spellcasting" not in plain


def test_hp_gain_uses_roll_plus_con_with_a_floor_and_a_retroactive_con_bonus(cli):
    assert cli._hp_gain(5, 2, 0, 3) == 7
    assert cli._hp_gain(1, -3, 0, 3) == 1
    assert cli._hp_gain(6, 3, 1, 4) == 9 + 4


def test_flatten_and_diff_lines_show_old_and_new_values(cli):
    assert cli._flatten({"a": {"b": [1, {"c": 2}]}, "d": 3}) == {
        "a.b[0]": 1,
        "a.b[1].c": 2,
        "d": 3,
    }
    old = {"hp": {"max": 28}, "x": 1}
    new = {"hp": {"max": 36}, "x": 1, "y": 2}
    assert cli._diff_lines(old, new) == [
        "  hp.max: 28 -> 36",
        "  y: (none) -> 2",
    ]
    assert cli._diff_lines(old, old) == []


def test_review_warnings_flag_what_levelling_cannot_recalculate(cli):
    old = _sample()
    unchanged = copy.deepcopy(old)
    assert cli._review_warnings(old, unchanged) == []
    stronger = cli._level_up_character(
        old, _choices(cli, scores=cli._apply_asi(cli._scores_of(old), {"Strength"}))
    )
    [warning] = cli._review_warnings(old, stronger)
    assert warning.startswith("Attack bonuses") and "Longsword" in warning
    nimble = cli._level_up_character(
        old, _choices(cli, scores=cli._apply_asi(cli._scores_of(old), {"Dexterity"}))
    )
    assert any("Armor Class" in w for w in cli._review_warnings(old, nimble))
    old["attacks"] = []
    assert cli._review_warnings(old, stronger) == []


def test_state_warnings_flag_used_slots_that_no_longer_fit(cli):
    new = {"spellcasting": {"slots": [{"level": "1st", "total": 2}]}}
    state = {"slot_used": {"1st": 3, "2nd": 1, "3rd": 0}}
    assert cli._state_warnings(state, new) == [
        "State: 3 1st slots used, new total is 2",
        "State: 1 2nd slots used, new total is 0",
    ]
    assert cli._state_warnings({}, new) == []
    assert cli._state_warnings({"slot_used": None}, {}) == []


def test_has_comments_detects_full_line_and_trailing_comments(cli):
    assert cli._has_comments("# top\nname: x") is True
    assert cli._has_comments("name: x  # trailing") is True
    assert cli._has_comments("name: x\nhp: 3") is False


# --- prompts ----------------------------------------------------------------


def test_ask_choice_returns_a_zero_based_index_and_reprompts(cli, respond, capsys):
    respond({"Choice": ["0", "9", "2"]})
    assert cli._ask_choice(3) == 1
    assert "pick one of the numbers" in capsys.readouterr().out
    respond({})
    assert cli._ask_choice(3) == 0


def test_ask_required_repeats_until_answered(cli, respond):
    prompts = respond({"Feat name": ["", "Tough"]})
    assert cli._ask_required("Feat name") == "Tough"
    assert prompts[1] == "Feat name (required): "


def test_resolve_existing_id_matches_picks_and_refuses(cli, respond, dirs, capsys):
    data, _ = dirs
    with pytest.raises(SystemExit):
        cli._resolve_existing_id("")
    assert "No characters found" in capsys.readouterr().out
    for name in ("alice", "bob"):
        (data / f"{name}.yaml").write_text("x")
    assert cli._resolve_existing_id("ALI") == "alice"
    with pytest.raises(SystemExit):
        cli._resolve_existing_id("zed")
    assert "Available: alice, bob" in capsys.readouterr().out
    respond({"Choice": "2"})
    assert cli._resolve_existing_id("") == "bob"


def test_load_character_file_returns_data_or_lists_every_problem(cli, dirs, capsys):
    data, _ = dirs
    path = data / "ok.yaml"
    path.write_text(SAMPLE_TEXT)
    char, text = cli._load_character_file(path)
    assert char["name"] == "Sample Character" and text == SAMPLE_TEXT
    broken = _sample()
    broken["hp"]["max"] = "ten"
    del broken["combat"]
    path.write_text(yaml.safe_dump(broken))
    with pytest.raises(SystemExit):
        cli._load_character_file(path)
    out = capsys.readouterr().out
    assert "ok.yaml has problems" in out and "file.hp.max" in out
    assert "file.combat: required but missing" in out
    path.write_text("name: [unclosed")
    with pytest.raises(SystemExit):
        cli._load_character_file(path)
    assert "not valid YAML" in capsys.readouterr().out


def test_ask_new_class_defaults_the_die_from_the_class_name(cli, respond):
    respond({"New class name": ["", "Wizard"], "Subclass": "Evoker"})
    assert cli._ask_new_class() == {
        "name": "Wizard",
        "level": 1,
        "subclass": "Evoker",
        "die": 6,
    }
    respond({"New class name": "Homebrewer", "Hit die": "12"})
    assert cli._ask_new_class()["die"] == 12
    respond({"New class name": "Homebrewer"})
    assert cli._ask_new_class()["die"] == 8


def test_ask_advance_class_raises_a_level_or_adds_a_class(cli, respond):
    classes = cli._parse_class_level("Fighter 3 / Ranger 1")
    respond({"Choice": "2"})
    raised, index = cli._ask_advance_class(classes)
    assert index == 1 and raised[1]["level"] == 2 and classes[1]["level"] == 1
    respond({"Choice": "3", "New class name": "Rogue"})
    added, index = cli._ask_advance_class(classes)
    assert index == 2 and added[2]["name"] == "Rogue" and len(classes) == 2


def test_ask_class_details_fills_a_missing_die_and_a_missing_subclass(cli, respond):
    entry = {"name": "Homebrewer", "level": 3, "subclass": "", "die": None}
    respond({"Hit die size": "6", "Subclass": "Sparks"})
    cli._ask_class_details(entry)
    assert (entry["die"], entry["subclass"]) == (6, "Sparks")
    known = {"name": "Fighter", "level": 2, "subclass": "", "die": 10}
    prompts = respond({})
    cli._ask_class_details(known)
    assert prompts == [] and known["subclass"] == ""


def test_resolve_classes_parses_or_asks_when_unreadable(cli, respond, capsys):
    assert cli._resolve_classes({"class_level": "Fighter 3"})[0]["level"] == 3
    respond({"Class (": ["Wizard", ""], "Level in": "2"})
    classes = cli._resolve_classes({"class_level": "???"})
    assert classes[0]["name"] == "Wizard"
    assert "Could not read the class" in capsys.readouterr().out


def test_ask_asi_abilities_needs_one_or_two_known_names(cli, respond, capsys):
    prompts = respond(
        {"Ability to raise": ["", "Strength, Dexterity, Wisdom", "str, dex"]}
    )
    assert cli._ask_asi_abilities() == {"Strength", "Dexterity"}
    assert "please name one or two abilities" in capsys.readouterr().out
    # One parenthetical, and no misleading "blank for none" (blank is rejected).
    assert prompts[0].count("(") == 1
    assert "one name for +2, or two for +1 each" in prompts[0]
    assert "blank for none" not in prompts[0]


def test_ask_asi_or_feat_defaults_to_asking_only_at_asi_levels(cli, respond):
    prompts = respond({"Ability score improvement": ["n", ""]})
    assert cli._ask_asi_or_feat(4) == (set(), None)
    assert "[Y/n]" in prompts[0]
    assert cli._ask_asi_or_feat(5) == (set(), None)
    assert "[y/N]" in prompts[1]


def test_ask_asi_or_feat_takes_a_feat_or_raises_scores(cli, respond):
    respond(
        {
            "Ability score improvement": "y",
            "Take a feat": "y",
            "Feat name": "Tough",
            "What it does": "+2 HP per level",
        }
    )
    assert cli._ask_asi_or_feat(4) == (
        set(),
        {"name": "Tough", "text": "+2 HP per level"},
    )
    respond({"Ability score improvement": "y", "Take a feat": "n", "Ability": "wis"})
    assert cli._ask_asi_or_feat(4) == ({"Wisdom"}, None)


def test_hp_prompts_default_to_the_average_and_explain_con_changes(
    cli, respond, capsys
):
    respond({})
    assert cli._ask_hp_roll(10) == 6 and cli._ask_hp_roll(8) == 5
    respond({"Hit die roll": "9"})
    assert cli._ask_hp_roll(10) == 9
    respond({})
    old = _sample()
    scores = cli._apply_asi(cli._scores_of(old), {"Constitution"})
    assert cli._ask_hp_gain(old, scores, 10, 3) == max(1, 6 + 3) + 1 * 3
    assert "adjusts for earlier levels" in capsys.readouterr().out
    assert cli._ask_hp_gain(old, cli._scores_of(old), 10, 3) == 8


def test_ask_spellcasting_update_recomputes_dc_and_attack_when_ability_known(
    cli, respond
):
    spells = {"ability": "Intelligence", "cantrips": ["Light"], "prepared": []}
    mods = {"Intelligence": 4}
    respond(
        {
            "Change spell slots": "y",
            "slot level": ["1st", ""],
            "total slots": "4",
            "New cantrips": "Mage Hand",
            "New spells": "Shield, Fireball",
        }
    )
    updated = cli._ask_spellcasting_update(spells, mods, 3)
    assert updated["slots"] == [{"level": "1st", "total": 4}]
    assert updated["cantrips"] == ["Light", "Mage Hand"]
    assert updated["prepared"] == ["Shield", "Fireball"]
    assert (updated["save_dc"], updated["attack_bonus"]) == (15, "+7")
    assert spells["cantrips"] == ["Light"]  # the input is not modified


def test_ask_spellcasting_update_skips_dc_for_an_unknown_ability_and_keeps_slots(
    cli, respond
):
    spells = {"ability": "Piety", "slots": [{"level": "1st", "total": 2}]}
    respond({"Change spell slots": "n"})
    updated = cli._ask_spellcasting_update(spells, {"Wisdom": 3}, 2)
    assert updated["slots"] == [{"level": "1st", "total": 2}]
    assert "save_dc" not in updated


def test_format_slots_reads_like_a_sentence_not_a_python_list(cli):
    slots = [{"level": "1st", "total": 4}, {"level": "2nd", "total": 3}]
    assert cli._format_slots(slots) == "1st: 4, 2nd: 3"
    assert cli._format_slots([]) == "none"


def test_ask_spells_if_any_is_none_without_spellcasting(cli, respond):
    old = _sample()
    classes = [{"name": "Fighter", "level": 4, "subclass": "", "die": 10}]
    assert cli._ask_spells_if_any(old, cli._scores_of(old), classes) is None
    old["spellcasting"] = {"ability": "Wisdom", "slots": []}
    respond({"Change spell slots": "n"})
    result = cli._ask_spells_if_any(old, cli._scores_of(old), classes)
    assert result["save_dc"] == 8 + 2 + 1


def test_ask_level_features_appends_the_feat(cli, respond):
    respond({"name:": ["Action Surge", ""], "text:": "extra action"})
    feat = {"name": "Tough", "text": "hp"}
    features = cli._ask_level_features(feat)
    assert [f["name"] for f in features] == ["Action Surge", "Tough"]
    respond({})
    assert cli._ask_level_features(None) == []


# --- review and save --------------------------------------------------------


def test_load_state_reads_the_state_file_or_returns_nothing(cli, dirs):
    _, state = dirs
    assert cli._load_state("tess") == {}
    (state / "tess.yaml").write_text("hp_current: 5\n")
    assert cli._load_state("tess") == {"hp_current": 5}
    (state / "empty.yaml").write_text("")
    assert cli._load_state("empty") == {}


def test_print_review_lists_changes_warnings_and_the_state_note(cli, capsys):
    old = _sample()
    new = cli._level_up_character(
        old, _choices(cli, scores=cli._apply_asi(cli._scores_of(old), {"Strength"}))
    )
    cli._print_review(old, new, {"hp_current": 3})
    out = capsys.readouterr().out
    assert "class_level: Fighter 3 -> Fighter 4" in out
    assert "Check: Attack bonuses" in out and "state/ is not touched" in out
    cli._print_review(old, old, {})
    assert "state/" not in capsys.readouterr().out


def test_save_with_backup_keeps_the_previous_text(cli, dirs):
    data, _ = dirs
    path = data / "tess.yaml"
    path.write_text("old text")
    backup = cli._save_with_backup(path, "old text", {"id": "tess", "name": "Tess"})
    assert backup.name == "tess.yaml.bak" and backup.read_text() == "old text"
    assert yaml.safe_load(path.read_text()) == {"id": "tess", "name": "Tess"}
    assert [p.name for p in data.glob("*.yaml")] == ["tess.yaml"]


def test_review_and_save_mentions_comments_and_can_be_declined(
    cli, respond, dirs, capsys
):
    data, _ = dirs
    path = data / "tess.yaml"
    text = "# my notes\n" + SAMPLE_TEXT
    path.write_text(text)
    old, new = _sample(), cli._level_up_character(_sample(), _choices(cli))
    respond({"Save these changes": "n"})
    with pytest.raises(SystemExit) as exit_info:
        cli._review_and_save(path, old, new, text)
    assert exit_info.value.code == 1 and path.read_text() == text
    out = capsys.readouterr().out
    assert "comments in the file are not kept" in out and "Aborted" in out
    assert not (data / "tess.yaml.bak").exists()
    respond({"Save these changes": "y"})
    cli._review_and_save(path, old, new, text)
    assert (data / "tess.yaml.bak").read_text() == text
    assert yaml.safe_load(path.read_text())["class_level"] == "Fighter 4"
    assert "kept as tess.yaml.bak" in capsys.readouterr().out


# --- actions and the whole flow ---------------------------------------------


def test_action_flags_are_mutually_exclusive(cli, argv):
    cases = [
        ((), (False, None)),
        (("--new",), (True, None)),
        (("--level-up",), (False, "")),
        (("--level-up", "bob"), (False, "bob")),
    ]
    for flags, expected in cases:
        argv(*flags)
        args = cli._parse_args()
        assert (args.new, args.level_up) == expected, flags
    argv("--new", "--level-up", "bob")
    with pytest.raises(SystemExit):
        cli._parse_args()


def test_resolve_action_uses_flags_or_asks(cli, argv, respond, capsys):
    argv("--new")
    assert cli._resolve_action(cli._parse_args()) == "new"
    argv("--level-up")
    assert cli._resolve_action(cli._parse_args()) == "level-up"
    argv()
    for reply, expected in (("", "new"), ("n", "new"), ("L", "level-up")):
        respond({"New, level-up or edit": reply})
        assert cli._resolve_action(cli._parse_args()) == expected, reply
    respond({"New, level-up or edit": ["what", "level up"]})
    assert cli._resolve_action(cli._parse_args()) == "level-up"
    assert "please type new, level-up or edit" in capsys.readouterr().out


def test_new_flag_skips_the_action_question(cli, argv, respond, dirs):
    argv("--new", "--id", "tess", "--name", "Tess", "--mode", "skeleton")
    prompts = respond({"Class (": ["Rogue", ""]})
    cli.main()
    assert not any("New, level-up or edit" in p for p in prompts)
    assert (dirs[0] / "tess.yaml").exists()


def _level_up_answers(**overrides):
    answers = {
        "Choice": "1",
        "Ability score improvement": "y",
        "Take a feat": "n",
        "Ability to raise": "Strength",
        "Hit die roll": "",
        "Save these changes": "y",
    }
    return {**answers, **overrides}


def test_level_up_end_to_end_updates_the_file_keeps_a_backup_and_spares_state(
    cli, argv, respond, dirs, capsys
):
    data, state = dirs
    original = "# my notes\n" + SAMPLE_TEXT
    (data / "tess.yaml").write_text(original)
    (state / "tess.yaml").write_text("hp_current: 7\n")
    argv("--level-up", "tess")
    respond(_level_up_answers())
    cli.main()
    new = yaml.safe_load((data / "tess.yaml").read_text())
    assert new["class_level"] == "Fighter 4" and new["hit_dice"]["total"] == "4d10"
    assert new["hp"]["max"] == 28 + 6 + 2
    strength = next(a for a in new["abilities"] if a["name"] == "Strength")
    assert (strength["score"], strength["mod"]) == (18, "+4")
    assert next(s for s in new["saves"] if s["name"] == "Strength")["mod"] == "+6"
    assert cli.validate_character(new) == []
    assert (data / "tess.yaml.bak").read_text() == original
    assert (state / "tess.yaml").read_text() == "hp_current: 7\n"
    out = capsys.readouterr().out
    assert "Longsword" in out and "comments in the file are not kept" in out


def test_level_up_with_no_id_lists_characters_and_can_multiclass(
    cli, argv, respond, dirs
):
    data, _ = dirs
    (data / "tess.yaml").write_text(SAMPLE_TEXT)
    argv("--level-up")
    respond(
        _level_up_answers(
            **{
                "Which character": "",
                "Choice": ["1", "2"],
                "New class name": "Rogue",
                "Ability score improvement": "n",
            }
        )
    )
    cli.main()
    new = yaml.safe_load((data / "tess.yaml").read_text())
    assert new["class_level"] == "Fighter 3 / Rogue 1"
    assert new["hit_dice"]["total"] == "3d10 + 1d8"
    assert new["proficiency_bonus"] == "+2"


def test_level_up_refuses_to_save_a_result_that_fails_validation(
    cli, argv, respond, dirs, monkeypatch, capsys
):
    data, _ = dirs
    (data / "tess.yaml").write_text(SAMPLE_TEXT)
    results = iter([[], ["file.hp.max: expected a whole number, found str 'x'"]])
    monkeypatch.setattr(cli, "validate_character", lambda _data: next(results))
    argv("--level-up", "tess")
    respond(_level_up_answers())
    with pytest.raises(SystemExit):
        cli.main()
    assert (data / "tess.yaml").read_text() == SAMPLE_TEXT
    assert not (data / "tess.yaml.bak").exists()
    assert "file.hp.max" in capsys.readouterr().out


def test_level_up_of_an_invalid_character_file_lists_the_problems(
    cli, argv, respond, dirs, capsys
):
    data, _ = dirs
    broken = _sample()
    broken["edition"] = 2024
    (data / "tess.yaml").write_text(yaml.safe_dump(broken))
    argv("--level-up", "tess")
    respond({})
    with pytest.raises(SystemExit):
        cli.main()
    assert "file.edition" in capsys.readouterr().out
