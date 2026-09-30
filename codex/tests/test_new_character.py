import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parent.parent / "scripts" / "new_character.py"
_spec = importlib.util.spec_from_file_location("new_character", _SCRIPT)
nc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nc)


def _scores(**overrides):
    return {**{a: 10 for a in nc.ABILITIES}, **overrides}


def test_compute_applies_proficiency_only_to_chosen_saves_and_skills():
    abilities, saves, skills, prof_bonus, passive = nc._compute_abilities_saves_skills(
        _scores(Strength=16, Wisdom=12), 2, {"Strength"}, {"Perception"}
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


def test_compute_passive_perception_is_ten_plus_perception_mod():
    *_, passive = nc._compute_abilities_saves_skills(
        _scores(Wisdom=14), 3, set(), {"Perception"}
    )
    assert passive == 10 + 2 + 3


def test_ask_comma_list_trims_and_drops_blanks(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: " Light ,, Mage Hand ,")
    assert nc._ask_comma_list("Cantrips") == ["Light", "Mage Hand"]


@pytest.mark.parametrize("level,bonus", [(1, 2), (4, 2), (5, 3), (9, 4), (17, 6)])
def test_proficiency_bonus_by_level(level, bonus):
    assert nc._proficiency_bonus(level) == bonus
