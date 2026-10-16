"""Tests for the --edit menu in scripts/character.py."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SAMPLE_TEXT = (ROOT / "data" / "sample_character.yaml").read_text(encoding="utf-8")


def _sample():
    return yaml.safe_load(SAMPLE_TEXT)


@pytest.fixture
def dirs(cli, tmp_path, monkeypatch):
    data, state = tmp_path / "data", tmp_path / "state"
    data.mkdir()
    state.mkdir()
    monkeypatch.setattr(cli, "DATA_DIR", data)
    monkeypatch.setattr(cli, "STATE_DIR", state)
    return data, state


# --- value prompts ----------------------------------------------------------


def test_ask_value_keeps_clears_replaces_and_keeps_numbers_numeric(cli, respond):
    cases = [
        ("Tess", "", "Tess"),
        ("Tess", "-", ""),
        ("Tess", "Bo", "Bo"),
        (16, "", 16),
        (16, "18", 18),
        (16, "-", ""),
        (16, "many", "many"),
        ("+2", "+3", "+3"),
        ("", "", ""),
        ("", "new", "new"),
    ]
    for current, reply, expected in cases:
        respond({"Label": reply})
        assert cli._ask_value("Label", current) == expected, (current, reply)


def test_ask_value_shows_the_current_value_as_the_default(cli, respond):
    prompts = respond({})
    cli._ask_value("Name", "Tess")
    cli._ask_value("Notes", "")
    assert prompts == ["Name [Tess]: ", "Notes: "]


def test_ask_fields_updates_known_fields_and_never_invents_blank_ones(cli, respond):
    section = {"age": "30", "hair": "red", "extra": "kept"}
    labels = {"age": "Age", "hair": "Hair", "gender": "Gender", "faith": "Faith"}
    respond({"Age": "31", "Hair": "-", "Faith": "Pelor"})
    updated = cli._ask_fields(section, labels)
    assert updated == {"age": "31", "hair": "", "extra": "kept", "faith": "Pelor"}
    assert section["age"] == "30"  # the input is not modified


def test_item_name_reads_names_text_and_plain_values(cli):
    assert cli._item_name({"name": "Mug", "text": "Tin"}) == "Mug"
    assert cli._item_name({"text": "Tin only"}) == "Tin only"
    assert cli._item_name({}) == ""
    assert cli._item_name("Rope") == "Rope" and cli._item_name(5) == "5"


def test_ask_removals_returns_valid_positions_and_reprompts(cli, respond, capsys):
    respond({"Remove which": ["9", "x", "1, 3"]})
    assert cli._ask_removals(3) == {0, 2}
    assert "please use the numbers shown" in capsys.readouterr().out
    respond({})
    assert cli._ask_removals(3) == set()


def test_edit_list_removes_numbered_items_then_adds_new_ones(cli, respond, capsys):
    respond({"Remove which": "2"})
    result = cli._edit_list("Gear", ["Rope", "Torch", "Map"], lambda: ["Lamp"])
    assert result == ["Rope", "Map", "Lamp"]
    assert "  2) Torch" in capsys.readouterr().out
    prompts = respond({})
    assert cli._edit_list("Gear", [], lambda: ["New"]) == ["New"]
    assert prompts == [] and "(none yet)" in capsys.readouterr().out


def test_treasure_as_list_accepts_every_stored_shape(cli):
    cases = [
        (None, []),
        ("A yoyo", ["A yoyo"]),
        (["a", {"name": "b"}], ["a", {"name": "b"}]),
        ({"title": "Staff", "text": "Frost"}, [{"name": "Staff", "text": "Frost"}]),
        ({"title": "", "text": ""}, []),
    ]
    for raw, expected in cases:
        assert cli._treasure_as_list(raw) == expected, raw


def test_ask_names_with_a_current_value_keeps_clears_or_replaces_it(cli, respond):
    prompts = respond({"Pick": ["", "-", "str"]})
    current = {"Dexterity"}
    assert cli._ask_names("Pick", cli.ABILITIES, current) == {"Dexterity"}
    assert cli._ask_names("Pick", cli.ABILITIES, current) == set()
    assert cli._ask_names("Pick", cli.ABILITIES, current) == {"Strength"}
    assert "blank keeps: Dexterity; - for none" in prompts[0]
    assert "blank keeps: none" in cli._names_hint([], set())


def test_ask_edition_default_is_the_current_edition(cli, respond):
    prompts = respond({})
    assert cli._ask_edition("2024") == "2024"
    assert prompts == ["Rules edition (2014 or 2024) [2024]: "]


# --- sections ---------------------------------------------------------------


def test_edit_identity_changes_fields_and_edition(cli, respond):
    respond({"Name [": "Tessa", "Experience points": "-", "Rules edition": "2024"})
    char = cli._edit_identity(_sample())
    assert char["name"] == "Tessa" and char["edition"] == "2024"
    assert char["class_level"] == "Fighter 3" and char["xp"] == ""


def test_edit_abilities_shifts_derived_values_and_updates_proficiency_flags(
    cli, respond
):
    char = _sample()
    char["skills"][11]["mod"] = "+4"  # Perception with a +1 item bonus
    respond(
        {
            "  Strength": "18",
            "Proficient saving throws": "",
            "Proficient skills": "athletics, perception, stealth",
            "Skills with expertise": "athletics",
        }
    )
    edited = cli._edit_abilities(char)
    by_skill = {s["name"]: s for s in edited["skills"]}
    assert by_skill["Athletics"] == {
        "name": "Athletics",
        "ability": "Str",
        "mod": "+8",
        "prof": "expertise",
    }
    assert by_skill["Stealth"]["prof"] is True and by_skill["Stealth"]["mod"] == "+4"
    assert by_skill["Perception"]["mod"] == "+4"  # custom bonus kept
    strength = next(a for a in edited["abilities"] if a["name"] == "Strength")
    assert (strength["score"], strength["mod"]) == (18, "+4")
    assert next(s for s in edited["saves"] if s["name"] == "Strength")["mod"] == "+6"
    assert cli.validate_character(edited) == []


def test_edit_combat_changes_ac_hp_speed_and_hit_dice(cli, respond):
    respond({"Armor Class": "18", "Max HP": "40", "Speed": "35 ft", "Hit dice": "-"})
    char = cli._edit_combat(_sample())
    assert char["combat"]["ac"] == 18 and char["combat"]["speed"] == "35 ft"
    assert char["hp"]["max"] == 40 and char["hit_dice"]["total"] == ""


def test_edit_attacks_removes_and_adds(cli, respond):
    respond(
        {
            "Remove which": "1",
            "name:": ["Dagger", ""],
            "bonus:": "+5",
            "Attack note": "Finesse",
        }
    )
    char = cli._edit_attacks(_sample())
    assert [a["name"] for a in char["attacks"]] == ["Dagger"]
    assert char["attacks"][0]["bonus"] == "+5" and char["attack_note"] == "Finesse"


def test_edit_gear_converts_a_legacy_treasure_box_to_a_list(cli, respond):
    char = _sample()
    char["treasure"] = {"title": "Staff of Frost", "text": "5 charges"}
    char["equipment"] = ["Rope"]
    respond({"Remove which": "", "  - ": ["Lamp", "", "Gem", ""], "Currency: gp": "25"})
    edited = cli._edit_gear(char)
    assert edited["equipment"] == ["Rope", "Lamp"]
    assert edited["treasure"] == [
        {"name": "Staff of Frost", "text": "5 charges"},
        "Gem",
    ]
    assert edited["currency"]["gp"] == "25"
    assert cli.validate_character(edited) == []


def test_edit_features_removes_and_adds_features_and_allies(cli, respond):
    respond(
        {
            "Remove which": ["1", ""],
            "name:": ["Action Surge", "", "Marta", ""],
            "text:": ["extra action", "friend"],
        }
    )
    char = cli._edit_features(_sample())
    assert [f["name"] for f in char["features"]] == ["Action Surge"]
    assert [a["name"] for a in char["allies"]][-1] == "Marta"


def test_edit_spellcasting_adds_a_section_or_leaves_none(cli, respond):
    respond({"Include spellcasting": "n"})
    assert "spellcasting" not in cli._edit_spellcasting(_sample())
    respond({"Include spellcasting": "y", "Spellcasting class": "Wizard"})
    assert cli._edit_spellcasting(_sample())["spellcasting"]["class"] == "Wizard"


def test_edit_spellcasting_changes_spells_slots_and_dc(cli, respond):
    char = _sample()
    char["spellcasting"] = {
        "ability": "Wisdom",
        "cantrips": ["Light", "Guidance"],
        "prepared": ["Bless"],
        "slots": [{"level": "1st", "total": 2}],
    }
    respond(
        {
            "Remove which": ["1", ""],
            "Add to Cantrips": "Mending",
            "Add to Prepared spells": "Shield, Cure Wounds",
            "Change spell slots": "n",
            "Spell save DC": "13",
        }
    )
    spells = cli._edit_spellcasting(char)["spellcasting"]
    assert spells["cantrips"] == ["Guidance", "Mending"]
    assert spells["prepared"] == ["Bless", "Shield", "Cure Wounds"]
    assert spells["slots"] == [{"level": "1st", "total": 2}]
    assert spells["save_dc"] == 13 and spells["attack_bonus"] == "+3"


def test_edit_story_and_proficiencies(cli, respond):
    respond(
        {
            "Personality traits": "Curious",
            "Age [": "40",
            "Faith (optional": "Pelor",
            "Backstory": "Raised by wolves",
            "Notes": "-",
            "Languages": "Common, Dwarvish",
        }
    )
    char = cli._edit_proficiencies(cli._edit_story(_sample()))
    assert char["personality"]["traits"] == "Curious"
    assert char["appearance"]["age"] == "40" and char["appearance"]["faith"] == "Pelor"
    assert char["backstory"] == "Raised by wolves"
    assert char["other_proficiencies"]["languages"] == "Common, Dwarvish"
    assert cli.validate_character(char) == []


# --- menu and the whole flow ------------------------------------------------


def test_apply_section_keeps_a_valid_change_and_discards_an_invalid_one(
    cli, respond, capsys
):
    original = _sample()
    respond({"Name [": "-"})
    result = cli._apply_section(original, cli._edit_identity)
    assert result is original and result["name"] == "Sample Character"
    assert "That change was not kept" in capsys.readouterr().out
    respond({"Name [": "Tessa"})
    assert cli._apply_section(original, cli._edit_identity)["name"] == "Tessa"
    assert original["name"] == "Sample Character"


def test_edit_loop_offers_the_sections_and_ends_on_enter(cli, respond, capsys):
    respond({"Section": ["99", "1", ""], "Name [": "Tessa"})
    char = cli._edit_loop(_sample())
    out = capsys.readouterr().out
    assert char["name"] == "Tessa"
    assert "please pick one of the numbers" in out
    assert "1) Identity and background" in out and "9) Languages" in out


def _edit_answers(**overrides):
    answers = {"Section": ["3", ""], "Armor Class": "18", "Save these changes": "y"}
    return {**answers, **overrides}


def test_edit_end_to_end_saves_with_a_backup_and_spares_state(
    cli, argv, respond, dirs, capsys
):
    data, state = dirs
    (data / "tess.yaml").write_text(SAMPLE_TEXT)
    (state / "tess.yaml").write_text("hp_current: 7\n")
    argv("--edit", "tess")
    respond(_edit_answers())
    cli.main()
    assert yaml.safe_load((data / "tess.yaml").read_text())["combat"]["ac"] == 18
    assert (data / "tess.yaml.bak").read_text() == SAMPLE_TEXT
    assert (state / "tess.yaml").read_text() == "hp_current: 7\n"
    assert "combat.ac: 16 -> 18" in capsys.readouterr().out


def test_edit_with_nothing_changed_writes_nothing(cli, argv, respond, dirs, capsys):
    data, _ = dirs
    (data / "tess.yaml").write_text(SAMPLE_TEXT)
    argv("--edit")
    respond({"Choice": "1", "Section": "3"})
    cli.main()
    assert "No changes were made" in capsys.readouterr().out
    assert (data / "tess.yaml").read_text() == SAMPLE_TEXT
    assert not (data / "tess.yaml.bak").exists()


def test_edit_can_be_declined_at_the_review(cli, argv, respond, dirs):
    data, _ = dirs
    (data / "tess.yaml").write_text(SAMPLE_TEXT)
    argv("--edit", "tess")
    respond(_edit_answers(**{"Save these changes": "n"}))
    with pytest.raises(SystemExit):
        cli.main()
    assert (data / "tess.yaml").read_text() == SAMPLE_TEXT


def test_edit_flag_and_menu_choice_select_the_edit_action(cli, argv, respond):
    argv("--edit")
    args = cli._parse_args()
    assert args.edit == "" and cli._resolve_action(args) == "edit"
    argv("--edit", "bob")
    assert cli._parse_args().edit == "bob"
    argv()
    respond({"New, level-up or edit": "e"})
    assert cli._resolve_action(cli._parse_args()) == "edit"
    argv("--edit", "--new")
    with pytest.raises(SystemExit):
        cli._parse_args()
