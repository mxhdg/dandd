"""Tests for scripts/build_rules.py (the maintainer tool that writes rules/)."""

import json

import pytest


def _fake_loaders(build_rules, monkeypatch, calls=None):
    def conditions(edition, refresh):
        if calls is not None:
            calls.append(("conditions", edition, refresh))
        return [{"slug": "poisoned", "name": "Poisoned", "text": f"{edition} text"}]

    def spells(edition, refresh):
        if calls is not None:
            calls.append(("spells", edition, refresh))
        return [{"slug": "light", "name": "Light", "text": "Glow."}]

    monkeypatch.setattr(build_rules, "load_conditions", conditions)
    monkeypatch.setattr(build_rules, "load_spell_details", spells)


def test_main_writes_a_bundle_per_kind_and_edition(
    build_rules, argv, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(build_rules, "RULES_DIR", tmp_path / "rules")
    _fake_loaders(build_rules, monkeypatch)
    argv()
    build_rules.main()
    names = sorted(p.name for p in (tmp_path / "rules").iterdir())
    assert names == [
        "conditions-2014.json",
        "conditions-2024.json",
        "spells-2014.json",
        "spells-2024.json",
    ]
    bundle = json.loads((tmp_path / "rules" / "conditions-2024.json").read_text())
    assert bundle["edition"] == "2024" and bundle["entries"][0]["text"] == "2024 text"
    assert "Creative Commons Attribution 4.0" in bundle["attribution"]
    out = capsys.readouterr().out
    assert "2014: 1 conditions, 1 spells" in out and "Review and commit" in out


def test_entries_without_rule_text_are_skipped_and_reported(
    build_rules, argv, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(build_rules, "RULES_DIR", tmp_path / "rules")
    _fake_loaders(build_rules, monkeypatch)
    monkeypatch.setattr(
        build_rules,
        "load_spell_details",
        lambda edition, refresh: [
            {"slug": "light", "name": "Light", "text": "Glow."},
            {"slug": "blank", "name": "Blank Spell", "text": "  "},
        ],
    )
    argv()
    build_rules.main()
    entries = json.loads((tmp_path / "rules" / "spells-2014.json").read_text())[
        "entries"
    ]
    assert [e["name"] for e in entries] == ["Light"]
    out = capsys.readouterr().out
    assert "skipped spell Blank Spell (2014): the SRD has no text" in out


def test_refresh_flag_is_passed_to_the_loaders(
    build_rules, argv, tmp_path, monkeypatch
):
    monkeypatch.setattr(build_rules, "RULES_DIR", tmp_path / "rules")
    calls = []
    _fake_loaders(build_rules, monkeypatch, calls)
    argv("--refresh")
    build_rules.main()
    assert {refresh for _, _, refresh in calls} == {True}
    argv()
    calls.clear()
    build_rules.main()
    assert {refresh for _, _, refresh in calls} == {False}


def test_an_unreachable_srd_stops_the_build_without_writing_anything(
    build_rules, argv, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(build_rules, "RULES_DIR", tmp_path / "rules")

    def offline(edition, refresh):
        raise build_rules.SrdUnavailable("could not reach the SRD (no route)")

    monkeypatch.setattr(build_rules, "load_conditions", offline)
    argv()
    with pytest.raises(SystemExit) as exit_info:
        build_rules.main()
    assert exit_info.value.code == 1
    assert "Could not build the rules files" in capsys.readouterr().out
    assert not (tmp_path / "rules").exists()
