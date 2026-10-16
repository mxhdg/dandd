"""Tests for the opt-in SRD lookups during character creation."""

import pytest
import yaml

import srd_lookup


def _srd():
    wizard = {
        "name": "Wizard",
        "die": 6,
        "saves": ["Intelligence", "Wisdom"],
        "features": [
            {"name": "Arcane Recovery", "text": "Regain slots.", "levels": [1]},
            {"name": "Spell Mastery", "text": "Cast often.", "levels": [18]},
        ],
        "subclasses": ["School of Evocation"],
    }
    fighter = {**wizard, "name": "Fighter", "die": 10, "subclasses": [], "features": []}
    elf = {
        "name": "Elf",
        "traits": [{"name": "Darkvision", "text": "See in the dark."}],
        "subspecies": [
            {"name": "High Elf", "traits": [{"name": "Cantrip", "text": "A cantrip."}]}
        ],
    }
    human = {"name": "Human", "traits": [], "subspecies": []}
    spells = [
        {"name": "Fire Bolt", "level": 0, "classes": ["Wizard"]},
        {"name": "Light", "level": 0, "classes": ["Wizard", "Cleric"]},
        {"name": "Shield", "level": 1, "classes": ["Wizard"]},
        {"name": "Bless", "level": 1, "classes": ["Cleric"]},
    ]
    return {"classes": [fighter, wizard], "species": [elf, human], "spells": spells}


@pytest.fixture
def fake_srd(cli, monkeypatch):
    srd = _srd()
    monkeypatch.setattr(cli, "load_classes", lambda edition: srd["classes"])
    monkeypatch.setattr(cli, "load_species", lambda edition: srd["species"])
    monkeypatch.setattr(cli, "load_spells", lambda edition: srd["spells"])
    return srd


# --- matching and prompts ---------------------------------------------------


def test_by_name_matches_case_insensitively_and_by_unique_prefix(cli):
    entries = _srd()["classes"]
    assert cli._by_name(entries, "WIZ")["name"] == "Wizard"
    assert cli._by_name(entries, "fighter")["name"] == "Fighter"
    assert cli._by_name(entries, "") is None and cli._by_name(entries, "bard") is None
    assert cli._srd_class(None, "wizard") is None
    assert cli._srd_class(_srd(), "wiz")["die"] == 6


def test_ask_class_uses_the_srd_name_hit_die_and_subclass(cli, respond, capsys):
    respond({"Class (": "wiz", "Subclass": "evoc"})
    entry = cli._ask_class(_srd())
    assert entry == {
        "name": "Wizard",
        "level": 1,
        "subclass": "School of Evocation",
        "die": 6,
    }
    out = capsys.readouterr().out
    assert "From the SRD: Wizard, hit die d6" in out and "SRD subclasses" in out


def test_ask_class_keeps_unknown_classes_as_typed(cli, respond, capsys):
    respond({"Class (": "Artificer", "Subclass": "Alchemist"})
    entry = cli._ask_class(_srd())
    assert (entry["name"], entry["subclass"], entry["die"]) == (
        "Artificer",
        "Alchemist",
        8,
    )
    assert "From the SRD" not in capsys.readouterr().out
    respond({"Class (": "fighter"})
    fighter = cli._ask_class(_srd())
    assert fighter["die"] == 10 and fighter["subclass"] == ""


def test_ask_race_matches_species_and_offers_subspecies(cli, respond, capsys):
    srd = _srd()
    respond({"Race": "elf", "Subspecies": "high"})
    assert cli._ask_race("2014", srd) == "High Elf"
    respond({"Race": "elf", "Subspecies": ""})
    assert cli._ask_race("2014", srd) == "Elf"
    respond({"Race": "elf", "Subspecies": "dark"})
    assert cli._ask_race("2014", srd) == "Elf"
    assert "Not recognized; using Elf" in capsys.readouterr().out
    respond({"Species": "hum"})
    assert cli._ask_race("2024", srd) == "Human"
    respond({"Race": "Dragonkin"})
    assert cli._ask_race("2014", srd) == "Dragonkin"
    respond({"Race": "Dragonkin"})
    assert cli._ask_race("2014", None) == "Dragonkin"


def test_race_traits_include_the_parent_species_for_a_subspecies(cli):
    srd = _srd()
    names = [t["name"] for t in cli._race_traits(srd, "High Elf")]
    assert names == ["Darkvision", "Cantrip"]
    assert [t["name"] for t in cli._race_traits(srd, "Elf")] == ["Darkvision"]
    assert cli._race_traits(srd, "Nobody") == [] and cli._race_traits(None, "Elf") == []


def test_srd_feature_candidates_are_level_one_features_plus_traits(cli):
    srd = _srd()
    classes = [{"name": "Wizard", "level": 1, "subclass": "", "die": 6}]
    names = [c["name"] for c in cli._srd_feature_candidates(srd, classes, "Elf")]
    assert names == ["Arcane Recovery", "Darkvision"]
    assert cli._srd_feature_candidates(None, classes, "Elf") == []
    homebrew = [{"name": "Artificer", "level": 1, "subclass": "", "die": 8}]
    assert cli._srd_feature_candidates(srd, homebrew, "Human") == []


def test_choose_features_adds_all_or_asks_one_by_one(cli, respond):
    offered = [{"name": "A", "text": "a"}, {"name": "B", "text": "b"}]
    assert cli._choose_features([]) == []
    respond({"Add all 2": "y"})
    assert cli._choose_features(offered) == offered
    respond({"Add all 2": "n", "Add A": "y", "Add B": "n"})
    assert cli._choose_features(offered) == [offered[0]]


def test_srd_saves_come_from_the_first_class(cli):
    classes = [{"name": "Wizard", "level": 1, "subclass": "", "die": 6}]
    assert cli._srd_saves(_srd(), classes) == {"Intelligence", "Wisdom"}
    assert cli._srd_saves(None, classes) == frozenset()


def test_spell_choices_filter_by_class_and_cantrip_status(cli):
    srd = _srd()
    assert cli._spell_choices(srd, ["Wizard"], True) == ["Fire Bolt", "Light"]
    assert cli._spell_choices(srd, ["Wizard"], False) == ["Shield"]
    assert cli._spell_choices(srd, ["Cleric", "Wizard"], False) == ["Bless", "Shield"]
    assert cli._spell_choices(None, ["Wizard"], True) == []


def test_ask_spell_list_matches_names_or_falls_back_to_free_text(cli, respond, capsys):
    respond({"Cantrips": ["fire, lig"]})
    assert cli._ask_spell_list("Cantrips", _srd(), ["Wizard"], True) == [
        "Fire Bolt",
        "Light",
    ]
    respond({"Cantrips": "Mage Hand, Prestidigitation"})
    assert cli._ask_spell_list("Cantrips", None, ["Wizard"], True) == [
        "Mage Hand",
        "Prestidigitation",
    ]
    respond({"Cantrips": "Mage Hand"})
    assert cli._ask_spell_list("Cantrips", _srd(), ["Artificer"], True) == ["Mage Hand"]
    assert capsys.readouterr().out == ""


def test_many_spell_choices_are_not_all_printed_on_a_typo(cli, respond, capsys):
    names = [f"Spell {n}" for n in range(60)]
    respond({"Pick": ["nope", "spell 7"]})
    assert cli._ask_names("Pick", names) == {"Spell 7"}
    out = capsys.readouterr().out
    assert "type part of a name" in out and "choices:" not in out


# --- skeleton saves ---------------------------------------------------------


def test_skeleton_marks_suggested_saves_proficient(cli):
    _, saves, *_ = cli._skeleton_abilities_saves_skills(1, {"Wisdom"})
    by_name = {s["name"]: s for s in saves}
    assert by_name["Wisdom"] == {"name": "Wisdom", "mod": "+2", "prof": True}
    assert by_name["Strength"] == {"name": "Strength", "mod": "+0", "prof": False}
    plain = cli._skeleton_abilities_saves_skills()[1]
    assert not any(s["prof"] for s in plain)


# --- loading and the opt-in -------------------------------------------------


def test_load_srd_returns_everything_or_explains_and_returns_none(
    cli, fake_srd, monkeypatch, capsys
):
    loaded = cli._load_srd("2014")
    assert set(loaded) == {"classes", "species", "spells"}

    def offline(edition):
        raise srd_lookup.SrdUnavailable("could not reach the SRD (no route)")

    monkeypatch.setattr(cli, "load_spells", offline)
    assert cli._load_srd("2014") is None
    assert "Could not use the SRD" in capsys.readouterr().out


def test_resolve_srd_is_opt_in_by_flag_or_by_answering_yes(
    cli, argv, respond, fake_srd, monkeypatch
):
    def boom(edition):
        raise AssertionError("must not be called")

    monkeypatch.setattr(cli, "load_classes", boom)
    argv()
    respond({"free SRD": "n"})
    assert cli._resolve_srd(cli._parse_args(), "2014") is None
    respond({})
    assert cli._resolve_srd(cli._parse_args(), "2014") is None
    monkeypatch.setattr(cli, "load_classes", lambda edition: [])
    respond({"free SRD": "y"})
    assert cli._resolve_srd(cli._parse_args(), "2014")["classes"] == []
    argv("--online")
    prompts = respond({})
    assert cli._resolve_srd(cli._parse_args(), "2014") is not None
    assert prompts == []


# --- whole flow -------------------------------------------------------------


def test_online_detailed_creation_fills_in_the_srd_choices(
    cli, argv, respond, fake_srd, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv("--online", "--id", "tess", "--name", "Tess", "--mode", "full")
    respond(
        {
            "Class (": ["wiz", ""],
            "Subclass": "evoc",
            "Race": "elf",
            "Subspecies": "high",
            "Add all": "y",
            "Proficient saving throws": "",
            "Include spellcasting": "y",
            "Spellcasting class": "",
            "slot level": ["1st", ""],
            "Cantrips": "fire",
            "Prepared spells": "shield",
        }
    )
    cli.main()
    char = yaml.safe_load((tmp_path / "tess.yaml").read_text(encoding="utf-8"))
    assert char["class_level"] == "Wizard 1 (School of Evocation)"
    assert char["race"] == "High Elf" and char["hit_dice"]["total"] == "1d6"
    saves = {s["name"] for s in char["saves"] if s["prof"]}
    assert saves == {"Intelligence", "Wisdom"}
    names = [f["name"] for f in char["features"]]
    assert names == ["Arcane Recovery", "Darkvision", "Cantrip"]
    spells = char["spellcasting"]
    assert spells["class"] == "Wizard" and spells["cantrips"] == ["Fire Bolt"]
    assert spells["prepared"] == ["Shield"]
    assert cli.validate_character(char) == []
    assert srd_lookup.ATTRIBUTION in capsys.readouterr().out


def test_creation_without_the_srd_prints_no_credit_and_asks_nothing_extra(
    cli, argv, respond, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    argv("--id", "tess", "--name", "Tess", "--mode", "skeleton")
    respond({"Class (": ["Rogue", ""]})
    cli.main()
    assert srd_lookup.ATTRIBUTION not in capsys.readouterr().out
    char = yaml.safe_load((tmp_path / "tess.yaml").read_text(encoding="utf-8"))
    assert char["features"] == [] and not any(s["prof"] for s in char["saves"])
