"""Unit tests for scripts/new_character.py (prompt helpers and builders)."""

import pytest
import yaml


def _scores(nc, **overrides):
    return {**{a: 10 for a in nc.ABILITIES}, **overrides}


# --- pure helpers -----------------------------------------------------------


def test_slugify(nc):
    cases = [
        ("Tess Marigold", "Tess_Marigold"),
        ("  Élan  the Bold! ", "lan_the_Bold"),
        ("a--b", "a_b"),
        ("", "character"),
        ("!!!", "character"),
    ]
    for name, slug in cases:
        assert nc._slugify(name) == slug, name


def test_ability_mod_and_formatting(nc):
    for score, mod in [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (20, 5)]:
        assert nc._ability_mod(score) == mod, score
    assert nc._fmt_mod(3) == "+3"
    assert nc._fmt_mod(0) == "+0"
    assert nc._fmt_mod(-2) == "-2"


def test_proficiency_bonus_by_level(nc):
    for level, bonus in [(0, 2), (1, 2), (4, 2), (5, 3), (9, 4), (13, 5), (17, 6)]:
        assert nc._proficiency_bonus(level) == bonus, level


def test_compute_applies_proficiency_only_to_chosen_saves_and_skills(nc):
    abilities, saves, skills, prof_bonus, _ = nc._compute_abilities_saves_skills(
        _scores(nc, Strength=16, Wisdom=12), 2, {"Strength"}, {"Perception"}
    )
    assert prof_bonus == 2
    assert next(a for a in abilities if a["name"] == "Strength")["mod"] == "+3"
    by_save = {s["name"]: s for s in saves}
    assert by_save["Strength"] == {"name": "Strength", "mod": "+5", "prof": True}
    assert by_save["Dexterity"]["mod"] == "+0"
    by_skill = {s["name"]: s for s in skills}
    assert by_skill["Perception"]["mod"] == "+3"
    assert by_skill["Athletics"]["mod"] == "+3"
    assert by_skill["Stealth"]["prof"] is False


def test_compute_passive_perception_is_ten_plus_perception_mod(nc):
    *_, passive = nc._compute_abilities_saves_skills(
        _scores(nc, Wisdom=14), 3, set(), {"Perception"}
    )
    assert passive == 10 + 2 + 3


def test_skeleton_abilities_saves_skills_are_blank_but_complete(nc):
    abilities, saves, skills, prof_bonus, passive = (
        nc._skeleton_abilities_saves_skills()
    )
    assert [a["name"] for a in abilities] == nc.ABILITIES
    assert all(a["score"] == 10 and a["mod"] == "+0" for a in abilities)
    assert len(saves) == 6 and not any(s["prof"] for s in saves)
    assert len(skills) == len(nc.SKILLS) and not any(s["prof"] for s in skills)
    assert (prof_bonus, passive) == (2, 10)


# --- input helpers ----------------------------------------------------------


def test_ask_uses_default_and_strips(nc, respond):
    prompts = respond({"Name": ["  Tess  ", ""]})
    assert nc._ask("Name") == "Tess"
    assert nc._ask("Name", "Bob") == "Bob"
    assert prompts[1] == "Name [Bob]: "


def test_ask_int_falls_back_to_default_on_bad_input(nc, respond):
    respond({"Level": ["7", "seven", ""]})
    assert nc._ask_int("Level", 1) == 7
    assert nc._ask_int("Level", 1) == 1
    assert nc._ask_int("Level", 4) == 4


def test_ask_yn(nc, respond):
    respond({"Q": ["y", "YES", "n", "no", "", ""]})
    assert [nc._ask_yn("Q") for _ in range(4)] == [True, True, False, False]
    assert nc._ask_yn("Q", default=False) is False
    assert nc._ask_yn("Q", default=True) is True


def test_ask_names_filters_to_valid_and_reports_unknown(nc, respond, capsys):
    respond({"Pick": ["", "Strength, Dexterity", "Strength, Bogus"]})
    assert nc._ask_names("Pick", nc.ABILITIES) == set()
    assert nc._ask_names("Pick", nc.ABILITIES) == {"Strength", "Dexterity"}
    assert nc._ask_names("Pick", nc.ABILITIES) == {"Strength"}
    assert "ignoring unrecognized: Bogus" in capsys.readouterr().out


def test_ask_comma_list_trims_and_drops_blanks(nc, respond):
    respond({"Cantrips": " Light ,, Mage Hand ,"})
    assert nc._ask_comma_list("Cantrips") == ["Light", "Mage Hand"]


def test_collect_simple_list_stops_on_blank(nc, respond):
    respond({"  - ": ["Rope", "Torch", ""]})
    assert nc._collect_simple_list("Equipment") == ["Rope", "Torch"]


def test_collect_named_list_collects_fields(nc, respond):
    respond({"name:": ["Second Wind", ""], "text:": "Heal a bit"})
    assert nc._collect_named_list("Features", ["text"]) == [
        {"name": "Second Wind", "text": "Heal a bit"}
    ]


# --- prompting builders -----------------------------------------------------


def test_ask_ability_inputs_derives_proficiency_bonus_from_level(nc, respond):
    respond(
        {
            "Strength": "16",
            "Character level": "5",
            "Proficient saving throws": "Strength",
            "Proficient skills": "Athletics",
            "Skills with expertise": "Athletics, Stealth",
        }
    )
    scores, prof_bonus, prof_saves, prof_skills, expertise = nc._ask_ability_inputs()
    assert scores["Strength"] == 16 and scores["Dexterity"] == 10
    assert prof_bonus == 3
    assert prof_saves == {"Strength"} and prof_skills == {"Athletics"}
    assert expertise == {"Athletics"}


def test_full_abilities_saves_skills_composes_prompt_and_compute(nc, respond):
    respond({"Strength": "16", "Proficient saving throws": "Strength"})
    abilities, saves, skills, prof_bonus, passive = nc._full_abilities_saves_skills()
    assert abilities[0]["mod"] == "+3"
    assert next(s for s in saves if s["name"] == "Strength")["mod"] == "+5"
    assert (prof_bonus, passive) == (2, 10)


def test_ask_spell_slots_stops_on_blank_level(nc, respond):
    respond({"level": ["1st", "2nd", ""], "total slots": ["4", "bad"]})
    assert nc._ask_spell_slots() == [
        {"level": "1st", "total": 4},
        {"level": "2nd", "total": 1},
    ]


def test_build_spellcasting_declined_returns_none(nc, respond):
    respond({"Include spellcasting": "n"})
    assert nc._build_spellcasting() is None


def test_build_spellcasting_collects_everything(nc, respond):
    respond(
        {
            "Include spellcasting": "y",
            "level": ["1st", ""],
            "total slots": "2",
            "Spellcasting class": "Wizard",
            "Spellcasting ability": "Intelligence",
            "Spell save DC": "14",
            "Spell attack bonus": "+6",
            "Cantrips": "Light, Mage Hand",
            "Prepared": "Shield",
        }
    )
    spellcasting = nc._build_spellcasting()
    assert spellcasting["class"] == "Wizard"
    assert spellcasting["save_dc"] == 14
    assert spellcasting["attack_bonus"] == "+6"
    assert spellcasting["cantrips"] == ["Light", "Mage Hand"]
    assert spellcasting["slots"] == [{"level": "1st", "total": 2}]
    assert spellcasting["prepared"] == ["Shield"]
    assert spellcasting["always_prepared"] == []


def test_section_prompt_helpers(nc, respond):
    respond(
        {
            "Languages": "Common, Elvish",
            "Armor Class": "15",
            "Initiative": "",
            "Personality traits": "Curious",
            "Appearance: age": "30",
            "Treasure title": "Hoard",
        }
    )
    assert nc._ask_other_proficiencies()["languages"] == "Common, Elvish"
    assert nc._ask_combat("+2") == {"ac": 15, "initiative": "+2", "speed": "30 ft"}
    assert nc._ask_personality()["traits"] == "Curious"
    assert nc._ask_appearance()["age"] == "30"
    assert set(nc._ask_appearance()) == {
        "age",
        "height",
        "weight",
        "eyes",
        "skin",
        "hair",
    }
    assert nc._ask_treasure() == {"title": "Hoard", "text": ""}


def test_ask_identity_fields(nc, respond):
    respond({"Class & level": "Wizard 3", "Race": "Elf"})
    identity = nc._ask_identity_fields()
    assert identity["class_level"] == "Wizard 3" and identity["race"] == "Elf"
    assert identity["edition"] == "2014"
    assert set(identity) == {
        "class_level",
        "background",
        "player_name",
        "edition",
        "race",
        "alignment",
    }


def test_build_full_details_covers_every_skeleton_field(nc, respond):
    respond({"Include spellcasting": "n", "Max HP": "31"})
    abilities = nc._skeleton_abilities_saves_skills()[0]
    full = nc._build_full_details(abilities)
    assert set(full) == set(nc._build_skeleton_details())
    assert full["hp"]["max"] == 31
    assert full["combat"]["initiative"] == "+0"
    assert "spellcasting" not in full


def test_build_full_details_adds_spellcasting_when_requested(nc, respond):
    respond({"Include spellcasting": "y", "Spellcasting class": "Wizard"})
    abilities = nc._skeleton_abilities_saves_skills()[0]
    assert nc._build_full_details(abilities)["spellcasting"]["class"] == "Wizard"


def test_skeleton_details_are_valid_blank_defaults(nc):
    details = nc._build_skeleton_details()
    assert details["hp"]["max"] == 10 and details["hit_dice"] == {"total": "1d8"}
    assert details["attacks"] == [] and details["equipment"] == []
    assert set(details["currency"]) == set(nc.CURRENCY_KEYS)


# --- argument / identity resolution ----------------------------------------


def test_parse_args_reads_flags(nc, argv):
    argv("--id", "tess", "--name", "Tess", "--mode", "full")
    args = nc._parse_args()
    assert (args.id, args.name, args.mode) == ("tess", "Tess", "full")


def test_parse_args_rejects_unknown_mode(nc, argv):
    argv("--mode", "bogus")
    with pytest.raises(SystemExit):
        nc._parse_args()


def test_resolve_name_prefers_flag_then_prompts_until_non_blank(nc, argv, respond):
    argv("--name", "Flagged")
    assert nc._resolve_name(nc._parse_args()) == "Flagged"
    argv()
    respond({"Character name": ["", "", "Tess"]})
    assert nc._resolve_name(nc._parse_args()) == "Tess"


def test_resolve_character_id_defaults_to_slug_and_rejects_bad_ids(
    nc, argv, respond, capsys
):
    argv("--id", "good_id")
    assert nc._resolve_character_id(nc._parse_args(), "Tess") == "good_id"
    argv("--id", "bad id!")
    respond({"Character id": "fixed-id"})
    assert nc._resolve_character_id(nc._parse_args(), "Tess") == "fixed-id"
    assert "id must match" in capsys.readouterr().out
    argv()
    respond({"Character id": ""})
    assert (
        nc._resolve_character_id(nc._parse_args(), "Tess Marigold") == "Tess_Marigold"
    )


def test_confirm_overwrite(nc, respond, tmp_path):
    missing = tmp_path / "new.yaml"
    assert nc._confirm_overwrite(missing) is True
    existing = tmp_path / "old.yaml"
    existing.write_text("x")
    respond({"overwrite": ["y", "n"]})
    assert nc._confirm_overwrite(existing) is True
    assert nc._confirm_overwrite(existing) is False


def test_resolve_mode_uses_flag_or_prompts_until_valid(nc, argv, respond):
    argv("--mode", "full")
    assert nc._resolve_mode(nc._parse_args()) == "full"
    argv()
    respond({"Mode": ["nonsense", "full"]})
    assert nc._resolve_mode(nc._parse_args()) == "full"
    respond({"Mode": ""})
    assert nc._resolve_mode(nc._parse_args()) == "skeleton"


# --- assembly and output ----------------------------------------------------


def test_write_character_creates_data_dir_and_round_trips(nc, tmp_path, monkeypatch):
    target = tmp_path / "data"
    monkeypatch.setattr(nc, "DATA_DIR", target)
    out = target / "tess.yaml"
    nc._write_character(out, {"id": "tess", "name": "Tess", "motto": "héllo"})
    assert yaml.safe_load(out.read_text(encoding="utf-8")) == {
        "id": "tess",
        "name": "Tess",
        "motto": "héllo",
    }


def test_build_character_skeleton_and_full(nc, respond):
    respond({"Class & level": "Rogue 1", "Max HP": "9", "Include spellcasting": "n"})
    skeleton = nc._build_character("t", "Tess", "skeleton")
    assert skeleton["id"] == "t" and skeleton["class_level"] == "Rogue 1"
    assert skeleton["hp"]["max"] == 10 and skeleton["proficiency_bonus"] == "+2"
    full = nc._build_character("t", "Tess", "full")
    assert full["hp"]["max"] == 9
    assert set(skeleton) == set(full)


def test_main_writes_the_character_file(nc, argv, respond, tmp_path, monkeypatch):
    monkeypatch.setattr(nc, "DATA_DIR", tmp_path)
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"Class & level": "Rogue 1"})
    nc.main()
    saved = yaml.safe_load((tmp_path / "tess.yaml").read_text(encoding="utf-8"))
    assert saved["name"] == "Tess" and saved["class_level"] == "Rogue 1"


def test_main_aborts_without_overwriting_when_declined(
    nc, argv, respond, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(nc, "DATA_DIR", tmp_path)
    (tmp_path / "tess.yaml").write_text("keep me")
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"overwrite": "n"})
    with pytest.raises(SystemExit) as exit_info:
        nc.main()
    assert exit_info.value.code == 1
    assert (tmp_path / "tess.yaml").read_text() == "keep me"
    assert "Aborted." in capsys.readouterr().out


def test_main_overwrites_when_confirmed(nc, argv, respond, tmp_path, monkeypatch):
    monkeypatch.setattr(nc, "DATA_DIR", tmp_path)
    (tmp_path / "tess.yaml").write_text("old")
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"overwrite": "y"})
    nc.main()
    assert yaml.safe_load((tmp_path / "tess.yaml").read_text())["name"] == "Tess"


def test_compute_doubles_proficiency_for_expertise(nc):
    _, _, skills, _, _ = nc._compute_abilities_saves_skills(
        _scores(nc, Intelligence=20), 2, set(), {"Arcana", "History"}, {"Arcana"}
    )
    by_skill = {s["name"]: s for s in skills}
    assert (
        by_skill["Arcana"]["mod"] == "+9" and by_skill["Arcana"]["prof"] == "expertise"
    )
    assert by_skill["History"]["mod"] == "+7" and by_skill["History"]["prof"] is True


def test_compute_ignores_expertise_without_proficiency(nc):
    _, _, skills, _, _ = nc._compute_abilities_saves_skills(
        _scores(nc), 2, set(), set(), {"Arcana"}
    )
    assert next(s for s in skills if s["name"] == "Arcana")["prof"] is False


def test_ask_edition_reprompts_until_valid(nc, respond):
    respond({"Rules edition": ["2019", "2024"]})
    assert nc._ask_edition() == "2024"


def test_ask_identity_fields_uses_species_label_for_2024(nc, respond):
    prompts = respond({"Rules edition": "2024", "Species": "Human"})
    assert nc._ask_identity_fields()["race"] == "Human"
    assert any("Species" in p for p in prompts)
