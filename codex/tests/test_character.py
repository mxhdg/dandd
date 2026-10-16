"""Unit tests for scripts/character.py (prompt helpers and builders)."""

import pytest
import yaml


def _scores(cli, **overrides):
    return {**{a: 10 for a in cli.ABILITIES}, **overrides}


# --- pure helpers -----------------------------------------------------------


def test_slugify(cli):
    cases = [
        ("Tess Marigold", "Tess_Marigold"),
        ("  Élan  the Bold! ", "lan_the_Bold"),
        ("a--b", "a_b"),
        ("", "character"),
        ("!!!", "character"),
    ]
    for name, slug in cases:
        assert cli._slugify(name) == slug, name


def test_ability_mod_and_formatting(cli):
    for score, mod in [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (20, 5)]:
        assert cli._ability_mod(score) == mod, score
    assert cli._fmt_mod(3) == "+3"
    assert cli._fmt_mod(0) == "+0"
    assert cli._fmt_mod(-2) == "-2"


def test_proficiency_bonus_by_level(cli):
    for level, bonus in [(0, 2), (1, 2), (4, 2), (5, 3), (9, 4), (13, 5), (17, 6)]:
        assert cli._proficiency_bonus(level) == bonus, level


def test_compute_applies_proficiency_only_to_chosen_saves_and_skills(cli):
    abilities, saves, skills, prof_bonus, _ = cli._compute_abilities_saves_skills(
        _scores(cli, Strength=16, Wisdom=12), 2, {"Strength"}, {"Perception"}
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


def test_compute_passive_perception_is_ten_plus_perception_mod(cli):
    *_, passive = cli._compute_abilities_saves_skills(
        _scores(cli, Wisdom=14), 3, set(), {"Perception"}
    )
    assert passive == 10 + 2 + 3


def test_skeleton_abilities_saves_skills_are_blank_but_complete(cli):
    abilities, saves, skills, prof_bonus, passive = (
        cli._skeleton_abilities_saves_skills()
    )
    assert [a["name"] for a in abilities] == cli.ABILITIES
    assert all(a["score"] == 10 and a["mod"] == "+0" for a in abilities)
    assert len(saves) == 6 and not any(s["prof"] for s in saves)
    assert len(skills) == len(cli.SKILLS) and not any(s["prof"] for s in skills)
    assert (prof_bonus, passive) == (2, 10)


# --- input helpers ----------------------------------------------------------


def test_ask_uses_default_and_strips(cli, respond):
    prompts = respond({"Name": ["  Tess  ", ""]})
    assert cli._ask("Name") == "Tess"
    assert cli._ask("Name", "Bob") == "Bob"
    assert prompts[1] == "Name [Bob]: "


def test_ask_int_reprompts_on_bad_input_and_uses_default_on_blank(cli, respond, capsys):
    respond({"Level": ["7", "seven", "8", "", ""]})
    assert cli._ask_int("Level", 1) == 7
    assert cli._ask_int("Level", 1) == 8
    assert "please type a whole number" in capsys.readouterr().out
    assert cli._ask_int("Level", 1) == 1
    assert cli._ask_int("Level", 4) == 4


def test_ask_yn(cli, respond):
    respond({"Q": ["y", "YES", "n", "no", "", ""]})
    assert [cli._ask_yn("Q") for _ in range(4)] == [True, True, False, False]
    assert cli._ask_yn("Q", default=False) is False
    assert cli._ask_yn("Q", default=True) is True


def test_match_name_ignores_case_and_accepts_unique_prefixes(cli):
    valid = ["Strength", "Stealth", "Survival", "Athletics"]
    cases = [
        ("strength", "Strength"),
        ("  ATH ", "Athletics"),
        ("sur", "Survival"),
        ("st", None),
        ("s", None),
        ("bogus", None),
        ("", None),
    ]
    for token, expected in cases:
        assert cli._match_name(token, valid) == expected, token


def test_parse_names_splits_matches_and_unknown(cli):
    chosen, unknown = cli._parse_names(" str, dex ,, nope", cli.ABILITIES)
    assert chosen == {"Strength", "Dexterity"}
    assert unknown == ["nope"]
    assert cli._parse_names("", cli.ABILITIES) == (set(), [])


def test_ask_names_matches_loosely_and_reprompts_on_unknown(cli, respond, capsys):
    respond({"Pick": ["", "strength, dex", "Strength, Bogus", "Strength"]})
    assert cli._ask_names("Pick", cli.ABILITIES) == set()
    assert cli._ask_names("Pick", cli.ABILITIES) == {"Strength", "Dexterity"}
    assert cli._ask_names("Pick", cli.ABILITIES) == {"Strength"}
    out = capsys.readouterr().out
    assert "not recognized: Bogus" in out
    assert "choices: Charisma, Constitution" in out


def test_ask_comma_list_trims_and_drops_blanks(cli, respond):
    respond({"Cantrips": " Light ,, Mage Hand ,"})
    assert cli._ask_comma_list("Cantrips") == ["Light", "Mage Hand"]


def test_collect_simple_list_stops_on_blank(cli, respond):
    respond({"  - ": ["Rope", "Torch", ""]})
    assert cli._collect_simple_list("Equipment") == ["Rope", "Torch"]


def test_collect_named_list_shows_example_in_prompt_format(cli, respond, capsys):
    respond({})
    cli._collect_named_list("Features", ["text"], ("Second Wind", "Heal a bit"))
    out = capsys.readouterr().out
    assert "    name: Second Wind\n    text: Heal a bit\n  Your entries:" in out


def test_collect_named_list_prints_the_explanation_before_the_example(
    cli, respond, capsys
):
    respond({})
    cli._collect_named_list("Allies", ["text"], ("Marta", "Friend"), "Who helps you.")
    out = capsys.readouterr().out
    assert out.index("Who helps you.") < out.index("Example entry")


def test_collect_named_list_collects_fields(cli, respond):
    respond({"name:": ["Second Wind", ""], "text:": "Heal a bit"})
    assert cli._collect_named_list("Features", ["text"]) == [
        {"name": "Second Wind", "text": "Heal a bit"}
    ]


# --- prompting builders -----------------------------------------------------


def test_ask_ability_inputs_derives_proficiency_bonus_from_level(cli, respond):
    respond(
        {
            "Strength": "16",
            "Proficient saving throws": "Strength",
            "Proficient skills": "Athletics",
            "Skills with expertise": ["Athletics, Stealth", "ath"],
        }
    )
    scores, prof_bonus, prof_saves, prof_skills, expertise = cli._ask_ability_inputs(5)
    assert scores["Strength"] == 16 and scores["Dexterity"] == 10
    assert prof_bonus == 3
    assert prof_saves == {"Strength"} and prof_skills == {"Athletics"}
    assert expertise == {"Athletics"}


def _classes(cli, *entries):
    return [
        {"name": n, "level": lv, "subclass": sub, "die": d} for n, lv, sub, d in entries
    ]


def test_total_level_sums_every_class(cli):
    classes = _classes(cli, ("Fighter", 3, "", 10), ("Ranger", 1, "", 10))
    assert cli._total_level(classes) == 4


def test_format_class_level_joins_classes_and_subclasses(cli):
    classes = _classes(cli, ("Fighter", 3, "Champion", 10), ("Ranger", 1, "", 10))
    assert cli._format_class_level(classes) == "Fighter 3 (Champion) / Ranger 1"
    assert cli._format_class_level(classes[1:]) == "Ranger 1"


def test_format_hit_dice_merges_matching_die_sizes(cli):
    same = _classes(cli, ("Fighter", 3, "", 10), ("Ranger", 1, "", 10))
    mixed = _classes(cli, ("Fighter", 3, "", 10), ("Wizard", 2, "", 6))
    assert cli._format_hit_dice(same) == "4d10"
    assert cli._format_hit_dice(mixed) == "3d10 + 2d6"


def test_ask_class_defaults_hit_die_from_class_name(cli, respond):
    respond({"Class (": "Ranger", "Level in": "3", "Subclass": "Hunter"})
    assert cli._ask_class() == {
        "name": "Ranger",
        "level": 3,
        "subclass": "Hunter",
        "die": 10,
    }
    respond({"Class (": "Homebrewer", "Level in": "0"})
    assert cli._ask_class() == {
        "name": "Homebrewer",
        "level": 1,
        "subclass": "",
        "die": 8,
    }


def test_ask_class_returns_none_on_blank(cli, respond):
    respond({})
    assert cli._ask_class() is None


def test_ask_classes_collects_until_blank_and_requires_one(cli, respond):
    respond({"Class (": ["", "Fighter", "Ranger", ""], "Level in": ["3", "1"]})
    classes = cli._ask_classes()
    assert [(c["name"], c["level"]) for c in classes] == [("Fighter", 3), ("Ranger", 1)]


def test_full_abilities_saves_skills_composes_prompt_and_compute(cli, respond):
    respond({"Strength": "16", "Proficient saving throws": "Strength"})
    abilities, saves, skills, prof_bonus, passive = cli._full_abilities_saves_skills(1)
    assert abilities[0]["mod"] == "+3"
    assert next(s for s in saves if s["name"] == "Strength")["mod"] == "+5"
    assert (prof_bonus, passive) == (2, 10)


def test_ask_spell_slots_stops_on_blank_level(cli, respond):
    respond({"slot level": ["1st", "2nd", ""], "total slots": ["4", "bad"]})
    assert cli._ask_spell_slots() == [
        {"level": "1st", "total": 4},
        {"level": "2nd", "total": 1},
    ]


def test_build_spellcasting_declined_returns_none(cli, respond):
    respond({"Include spellcasting": "n"})
    assert cli._build_spellcasting() is None


def test_build_spellcasting_collects_everything(cli, respond):
    respond(
        {
            "Include spellcasting": "y",
            "slot level": ["1st", ""],
            "total slots": "2",
            "Spellcasting class": "Wizard",
            "Spellcasting ability": "Intelligence",
            "Spell save DC": "14",
            "Spell attack bonus": "+6",
            "Cantrips": "Light, Mage Hand",
            "Prepared": "Shield",
        }
    )
    spellcasting = cli._build_spellcasting()
    assert spellcasting["class"] == "Wizard"
    assert spellcasting["save_dc"] == 14
    assert spellcasting["attack_bonus"] == "+6"
    assert spellcasting["cantrips"] == ["Light", "Mage Hand"]
    assert spellcasting["slots"] == [{"level": "1st", "total": 2}]
    assert spellcasting["prepared"] == ["Shield"]
    assert spellcasting["always_prepared"] == []


def test_section_prompt_helpers(cli, respond):
    respond(
        {
            "Languages": "Common, Elvish",
            "Armor Class": "15",
            "Initiative": "",
            "Personality traits": "Curious",
            "Appearance: Age": "30",
        }
    )
    assert cli._ask_other_proficiencies()["languages"] == "Common, Elvish"
    assert cli._ask_combat("+2") == {"ac": 15, "initiative": "+2", "speed": "30 ft"}
    assert cli._ask_personality()["traits"] == "Curious"
    assert cli._ask_appearance()["age"] == "30"
    assert set(cli._ask_appearance()) == set(cli.APPEARANCE_PROMPTS)
    assert {"gender", "faith"} <= set(cli.APPEARANCE_PROMPTS)


def test_ask_identity_fields(cli, respond):
    respond({"Race": "Elf"})
    identity = cli._ask_identity_fields("2014")
    assert identity["race"] == "Elf"
    assert identity["edition"] == "2014"
    assert set(identity) == {
        "background",
        "player_name",
        "edition",
        "race",
        "alignment",
    }


def test_build_full_details_covers_every_skeleton_field(cli, respond):
    respond({"Include spellcasting": "n", "Max HP": "31"})
    abilities = cli._skeleton_abilities_saves_skills()[0]
    full = cli._build_full_details(abilities)
    assert set(full) == set(cli._build_skeleton_details())
    assert full["hp"]["max"] == 31
    assert full["treasure"] == []
    assert full["combat"]["initiative"] == "+0"
    assert "spellcasting" not in full


def test_build_full_details_collects_treasure_as_a_list(cli, respond):
    # Equipment is asked first and shares the "  - " prompt: skip it, then add one.
    respond({"  - ": ["", "Jade ring", ""]})
    abilities = cli._skeleton_abilities_saves_skills()[0]
    full = cli._build_full_details(abilities)
    assert full["equipment"] == [] and full["treasure"] == ["Jade ring"]


def test_build_full_details_adds_spellcasting_when_requested(cli, respond):
    respond({"Include spellcasting": "y", "Spellcasting class": "Wizard"})
    abilities = cli._skeleton_abilities_saves_skills()[0]
    assert cli._build_full_details(abilities)["spellcasting"]["class"] == "Wizard"


def test_skeleton_details_are_valid_blank_defaults(cli):
    details = cli._build_skeleton_details()
    assert details["hp"]["max"] == 10 and details["hit_dice"] == {"total": "1d8"}
    assert details["attacks"] == [] and details["equipment"] == []
    assert details["treasure"] == []
    assert set(details["currency"]) == set(cli.CURRENCY_KEYS)


# --- argument / identity resolution ----------------------------------------


def test_parse_args_reads_flags(cli, argv):
    argv("--id", "tess", "--name", "Tess", "--mode", "full")
    args = cli._parse_args()
    assert (args.id, args.name, args.mode) == ("tess", "Tess", "full")


def test_parse_args_rejects_unknown_mode(cli, argv):
    argv("--mode", "bogus")
    with pytest.raises(SystemExit):
        cli._parse_args()


def test_resolve_name_prefers_flag_then_prompts_until_non_blank(cli, argv, respond):
    argv("--name", "Flagged")
    assert cli._resolve_name(cli._parse_args()) == "Flagged"
    argv()
    respond({"Character name": ["", "", "Tess"]})
    assert cli._resolve_name(cli._parse_args()) == "Tess"


def test_resolve_character_id_derives_from_name_and_rejects_bad_ids(
    cli, argv, respond, capsys
):
    argv("--id", "good_id")
    assert cli._resolve_character_id(cli._parse_args(), "Tess") == "good_id"
    argv("--id", "bad id!")
    respond({"File name": "fixed-id"})
    assert cli._resolve_character_id(cli._parse_args(), "Tess") == "fixed-id"
    assert "id must match" in capsys.readouterr().out
    argv()
    prompts = respond({})
    assert (
        cli._resolve_character_id(cli._parse_args(), "Tess Marigold") == "Tess_Marigold"
    )
    assert prompts == []


def test_confirm_overwrite(cli, respond, tmp_path):
    missing = tmp_path / "new.yaml"
    assert cli._confirm_overwrite(missing) is True
    existing = tmp_path / "old.yaml"
    existing.write_text("x")
    respond({"overwrite": ["y", "n"]})
    assert cli._confirm_overwrite(existing) is True
    assert cli._confirm_overwrite(existing) is False


def test_resolve_mode_uses_flag_or_prompts_until_valid(cli, argv, respond, capsys):
    argv("--mode", "full")
    assert cli._resolve_mode(cli._parse_args()) == "full"
    argv()
    respond({"Quick or detailed": ["nonsense", "Detailed"]})
    assert cli._resolve_mode(cli._parse_args()) == "full"
    assert "please type quick or detailed" in capsys.readouterr().out
    cases = [
        ("", "skeleton"),
        ("q", "skeleton"),
        ("Q", "skeleton"),
        ("D", "full"),
        ("full", "full"),
    ]
    for reply, mode in cases:
        respond({"Quick or detailed": reply})
        assert cli._resolve_mode(cli._parse_args()) == mode, reply


# --- assembly and output ----------------------------------------------------


def test_write_character_creates_data_dir_and_round_trips(cli, tmp_path, monkeypatch):
    target = tmp_path / "data"
    monkeypatch.setattr(cli, "DATA_DIR", target)
    out = target / "tess.yaml"
    cli._write_character(out, {"id": "tess", "name": "Tess", "motto": "héllo"})
    assert yaml.safe_load(out.read_text(encoding="utf-8")) == {
        "id": "tess",
        "name": "Tess",
        "motto": "héllo",
    }


def test_build_character_skeleton_and_full(cli, respond):
    respond(
        {
            "Class (": ["Rogue", "", "Rogue", ""],
            "Max HP": "9",
            "Include spellcasting": "n",
        }
    )
    skeleton = cli._build_character("t", "Tess", "skeleton", "2014")
    assert skeleton["id"] == "t" and skeleton["class_level"] == "Rogue 1"
    assert skeleton["hp"]["max"] == 10 and skeleton["proficiency_bonus"] == "+2"
    full = cli._build_character("t", "Tess", "full", "2014")
    assert full["hp"]["max"] == 9
    assert set(skeleton) == set(full)


def test_build_character_multiclass_derives_level_and_hit_dice(cli, respond):
    respond({"Class (": ["Fighter", "Ranger", ""], "Level in": ["3", "2"]})
    char = cli._build_character("e", "Elowen", "skeleton", "2014")
    assert char["class_level"] == "Fighter 3 / Ranger 2"
    assert char["hit_dice"] == {"total": "5d10"}
    assert char["proficiency_bonus"] == "+3"
    assert list(char)[:3] == ["id", "name", "class_level"]


def test_main_writes_the_character_file(
    cli, argv, respond, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"Class (": ["Rogue", ""]})
    cli.main()
    saved = yaml.safe_load((tmp_path / "tess.yaml").read_text(encoding="utf-8"))
    assert saved["name"] == "Tess" and saved["class_level"] == "Rogue 1"
    out = capsys.readouterr().out
    assert "Answer each question" in out
    assert cli.GUIDE_URLS["2014"] in out and cli.GUIDE_URLS["2024"] not in out
    assert f"Saved your character to {tmp_path / 'tess.yaml'}" in out
    assert "do not commit" in out


def test_main_with_no_flags_only_asks_name_mode_and_character_questions(
    cli, argv, respond, tmp_path, monkeypatch
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv()
    prompts = respond({"Character name": "Tess Marigold", "Class (": ["Rogue", ""]})
    cli.main()
    assert (tmp_path / "Tess_Marigold.yaml").exists()
    keys = ("Rules edition", "Quick or detailed", "Character name")
    asked = [k for p in prompts for k in keys if k in p]
    assert asked == list(keys)
    assert not any("id" in p.lower().split() for p in prompts)
    assert any("Quick or detailed" in p for p in prompts)


def test_main_aborts_without_overwriting_when_declined(
    cli, argv, respond, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    (tmp_path / "tess.yaml").write_text("keep me")
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"overwrite": "n"})
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    assert (tmp_path / "tess.yaml").read_text() == "keep me"
    assert "Aborted." in capsys.readouterr().out


def test_main_overwrites_when_confirmed(cli, argv, respond, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    (tmp_path / "tess.yaml").write_text("old")
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"overwrite": "y", "Class (": ["Rogue", ""]})
    cli.main()
    assert yaml.safe_load((tmp_path / "tess.yaml").read_text())["name"] == "Tess"


def test_compute_doubles_proficiency_for_expertise(cli):
    _, _, skills, _, _ = cli._compute_abilities_saves_skills(
        _scores(cli, Intelligence=20), 2, set(), {"Arcana", "History"}, {"Arcana"}
    )
    by_skill = {s["name"]: s for s in skills}
    assert (
        by_skill["Arcana"]["mod"] == "+9" and by_skill["Arcana"]["prof"] == "expertise"
    )
    assert by_skill["History"]["mod"] == "+7" and by_skill["History"]["prof"] is True


def test_compute_ignores_expertise_without_proficiency(cli):
    _, _, skills, _, _ = cli._compute_abilities_saves_skills(
        _scores(cli), 2, set(), set(), {"Arcana"}
    )
    assert next(s for s in skills if s["name"] == "Arcana")["prof"] is False


def test_ask_edition_reprompts_until_valid(cli, respond):
    respond({"Rules edition": ["2019", "2024"]})
    assert cli._ask_edition() == "2024"


def test_ask_identity_fields_uses_species_label_for_2024(cli, respond):
    prompts = respond({"Species": "Human"})
    assert cli._ask_identity_fields("2024")["race"] == "Human"
    assert any("Species" in p for p in prompts)


def test_ask_names_hint_shows_examples_only_when_names_exist(cli, respond):
    prompts = respond({})
    cli._ask_names("Pick", ["Strength", "Dexterity", "Wisdom"])
    cli._ask_names("Pick", [])
    assert "e.g. Dexterity, Strength" in prompts[0]
    assert "e.g." not in prompts[1]


def test_main_exits_gracefully_on_ctrl_c_or_ctrl_d(
    cli, argv, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv("--mode", "skeleton")
    for error in (KeyboardInterrupt, EOFError):

        def interrupted(prompt="", error=error):
            raise error

        monkeypatch.setattr("builtins.input", interrupted)
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
        assert exit_info.value.code == 130
        assert "Cancelled. Nothing was saved." in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_main_shows_the_guide_for_the_chosen_edition(
    cli, argv, respond, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"Rules edition": "2024", "Class (": ["Rogue", ""]})
    cli.main()
    out = capsys.readouterr().out
    assert cli.GUIDE_URLS["2024"] in out and cli.GUIDE_URLS["2014"] not in out
    saved = yaml.safe_load((tmp_path / "tess.yaml").read_text(encoding="utf-8"))
    assert saved["edition"] == "2024"
