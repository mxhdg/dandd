import json
import re
from html import unescape
from pathlib import Path

import pytest
import yaml

import app as app_module


def test_index_lists_sample_character(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sample Character" in resp.data


def test_character_sheet_renders(client):
    resp = client.get("/characters/sample_character")
    assert resp.status_code == 200
    assert b"Sample Character" in resp.data


def test_guide_page_renders(client):
    resp = client.get("/guide")
    assert resp.status_code == 200
    assert b"Getting Started" in resp.data


def test_index_links_to_guide(client):
    resp = client.get("/")
    assert b'href="/guide"' in resp.data


def test_unknown_character_404s(client):
    resp = client.get("/characters/does_not_exist")
    assert resp.status_code == 404


def test_invalid_character_id_404s(client):
    for bad_id in ["..", "%2e%2e", "a b", "a/../b"]:
        assert client.get(f"/characters/{bad_id}").status_code == 404, bad_id


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "script-src 'none'" in resp.headers["Content-Security-Policy"]


def test_update_persists_state(client, tmp_path):
    resp = client.post(
        "/characters/sample_character/update",
        data={
            "hp_current": "5",
            "hp_temp": "2",
            "hit_dice_used": "1",
            "inspiration": "on",
            "xp": "150",
        },
    )
    assert resp.status_code == 302

    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["hp_current"] == 5
    assert saved["hp_temp"] == 2
    assert saved["hit_dice_used"] == 1
    assert saved["inspiration"] is True
    assert saved["xp"] == "150"


def test_update_applies_hp_delta(client, tmp_path):
    resp = client.post(
        "/characters/sample_character/update",
        data={"hp_current": "10", "hp_temp": "3", "damage_taken": "5"},
    )
    assert resp.status_code == 302

    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["hp_temp"] == 0
    assert saved["hp_current"] == 8


def test_update_hp_delta_caps_healing_at_max(client, tmp_path):
    data = app_module._load_character("sample_character")
    resp = client.post(
        "/characters/sample_character/update",
        data={
            "hp_current": str(data["hp"]["max"] - 1),
            "healing_received": "100",
        },
    )
    assert resp.status_code == 302

    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["hp_current"] == data["hp"]["max"]


def test_update_persists_conditions(client, tmp_path):
    resp = client.post(
        "/characters/sample_character/update",
        data={"condition_poisoned": "on", "condition_prone": "on"},
    )
    assert resp.status_code == 302

    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["conditions"]["poisoned"] is True
    assert saved["conditions"]["prone"] is True
    assert saved["conditions"]["stunned"] is False


def test_update_persists_concentration(client, tmp_path):
    resp = client.post(
        "/characters/sample_character/update",
        data={"concentration": "Fireball"},
    )
    assert resp.status_code == 302
    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["concentration"] == "Fireball"

    resp = client.post(
        "/characters/sample_character/update",
        data={"concentration": ""},
    )
    assert resp.status_code == 302
    saved = yaml.safe_load((tmp_path / "sample_character.yaml").read_text())
    assert saved["concentration"] == ""


def test_death_save_banner_shows_stabilized_at_three_successes(client, tmp_path):
    (tmp_path / "sample_character.yaml").write_text(
        yaml.safe_dump({"death_save_successes": 3, "death_save_failures": 0})
    )
    resp = client.get("/characters/sample_character")
    assert b"STABILIZED" in resp.data
    assert b"DEAD" not in resp.data


def test_death_save_banner_shows_dead_at_three_failures(client, tmp_path):
    (tmp_path / "sample_character.yaml").write_text(
        yaml.safe_dump({"death_save_successes": 0, "death_save_failures": 3})
    )
    resp = client.get("/characters/sample_character")
    assert b"DEAD" in resp.data
    assert b"STABILIZED" not in resp.data


def test_death_save_banner_hidden_below_three(client):
    resp = client.get("/characters/sample_character")
    assert b"STABILIZED" not in resp.data
    assert b"DEAD" not in resp.data


def test_update_rejects_missing_origin(client):
    del client.environ_base["HTTP_ORIGIN"]
    resp = client.post("/characters/sample_character/update", data={"xp": "1"})
    assert resp.status_code == 403


def test_update_rejects_cross_site_origin(client):
    client.environ_base["HTTP_ORIGIN"] = "http://evil.example"
    resp = client.post("/characters/sample_character/update", data={"xp": "1"})
    assert resp.status_code == 403


def test_update_accepts_matching_referer_without_origin(client):
    del client.environ_base["HTTP_ORIGIN"]
    resp = client.post(
        "/characters/sample_character/update",
        data={"xp": "1"},
        headers={"Referer": "http://localhost/characters/sample_character"},
    )
    assert resp.status_code == 302


def test_update_unknown_character_404s(client):
    resp = client.post("/characters/does_not_exist/update", data={})
    assert resp.status_code == 404


def test_update_invalid_character_id_404s(client):
    resp = client.post("/characters/..%2f../update", data={})
    assert resp.status_code == 404


def _saved(tmp_path):
    return yaml.safe_load((tmp_path / "sample_character.yaml").read_text())


def test_long_rest_restores_hp_slots_and_half_hit_dice(client, tmp_path):
    data = app_module._load_character("sample_character")
    total = app_module._hit_dice_count(data["hit_dice"]["total"])
    resp = client.post(
        "/characters/sample_character/rest/long",
        data={
            "hp_current": "1",
            "hp_temp": "4",
            "hit_dice_used": str(total),
            "death_failure_0": "on",
            "slot_used_1": "1",
        },
    )
    assert resp.status_code == 302

    saved = _saved(tmp_path)
    assert saved["hp_current"] == data["hp"]["max"]
    assert saved["hp_temp"] == 0
    assert saved["hit_dice_used"] == total - max(total // 2, 1)
    assert saved["death_save_failures"] == 0
    assert all(v == 0 for v in saved["slot_used"].values())


def test_long_rest_never_makes_hit_dice_used_negative(client, tmp_path):
    client.post("/characters/sample_character/rest/long", data={"hit_dice_used": "0"})
    assert _saved(tmp_path)["hit_dice_used"] == 0


def test_short_rest_spends_hit_dice_and_heals(client, tmp_path):
    resp = client.post(
        "/characters/sample_character/rest/short",
        data={
            "hp_current": "5",
            "hit_dice_used": "0",
            "rest_hit_dice_spent": "2",
            "rest_healing": "9",
        },
    )
    assert resp.status_code == 302

    saved = _saved(tmp_path)
    assert saved["hit_dice_used"] == 2
    assert saved["hp_current"] == 14


def test_short_rest_caps_spent_dice_and_healing(client, tmp_path):
    data = app_module._load_character("sample_character")
    total = app_module._hit_dice_count(data["hit_dice"]["total"])
    client.post(
        "/characters/sample_character/rest/short",
        data={
            "hp_current": str(data["hp"]["max"] - 1),
            "hit_dice_used": str(total - 1),
            "rest_hit_dice_spent": "50",
            "rest_healing": "500",
        },
    )
    saved = _saved(tmp_path)
    assert saved["hit_dice_used"] == total
    assert saved["hp_current"] == data["hp"]["max"]


def test_rest_applies_pending_sheet_edits(client, tmp_path):
    client.post(
        "/characters/sample_character/rest/short",
        data={"xp": "999", "rest_hit_dice_spent": "0"},
    )
    assert _saved(tmp_path)["xp"] == "999"


def test_rest_rejects_unknown_kind(client):
    resp = client.post("/characters/sample_character/rest/nap")
    assert resp.status_code == 404


def test_rest_rejects_missing_origin(client):
    client.environ_base.pop("HTTP_ORIGIN")
    resp = client.post("/characters/sample_character/rest/long")
    assert resp.status_code == 403


def test_hit_dice_count():
    cases = [("3d10", 3), ("3d10 + 2d8", 5), ("1d8", 1), ("", 0)]
    for total, count in cases:
        assert app_module._hit_dice_count(total) == count, total


def test_update_persists_exhaustion_and_clamps(client, tmp_path):
    client.post("/characters/sample_character/update", data={"exhaustion": "3"})
    assert _saved(tmp_path)["exhaustion"] == 3
    client.post("/characters/sample_character/update", data={"exhaustion": "99"})
    assert _saved(tmp_path)["exhaustion"] == 6
    client.post("/characters/sample_character/update", data={"exhaustion": "-2"})
    assert _saved(tmp_path)["exhaustion"] == 0


def test_exhaustion_effects_are_cumulative_on_sheet(client):
    client.post("/characters/sample_character/update", data={"exhaustion": "2"})
    body = client.get("/characters/sample_character").data
    assert b"Disadvantage on ability checks" in body
    assert b"Speed halved" in body
    assert b"Disadvantage on attack rolls" not in body


def test_long_rest_clears_one_level_of_exhaustion(client, tmp_path):
    client.post("/characters/sample_character/rest/long", data={"exhaustion": "3"})
    assert _saved(tmp_path)["exhaustion"] == 2
    client.post("/characters/sample_character/rest/long", data={"exhaustion": "0"})
    assert _saved(tmp_path)["exhaustion"] == 0


def test_print_overrides_come_after_base_layout_rules():
    # A print override placed before the base rule it overrides loses the
    # cascade (this broke page-1 printing once already), so the @media print
    # block must be the last thing in the stylesheet.
    css = (
        Path(app_module.__file__).parent / "static/css/character_sheet.css"
    ).read_text()
    print_at = css.index("@media print")
    assert css.count("@media print") == 1
    for base_rule in (
        ".columns-3 {",
        ".col { display: flex",
        ".rest-buttons { display: flex",
    ):
        assert css.index(base_rule) < print_at, base_rule


def test_pdf_route_returns_a_pdf(client):
    resp = client.get("/characters/sample_character/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")


def test_pdf_route_unknown_and_invalid_ids_404(client):
    assert client.get("/characters/does_not_exist/pdf").status_code == 404
    assert client.get("/characters/a b/pdf").status_code == 404


def test_sheet_links_to_pdf(client):
    body = client.get("/characters/sample_character").data
    assert b'href="/characters/sample_character/pdf"' in body
    assert b'target="_blank"' in body


def test_pdf_fetcher_only_serves_static_files():
    fetcher = app_module._StaticOnlyFetcher()
    ok = fetcher.fetch("http://codex.invalid/static/css/character_sheet.css")
    assert b".sheet-page" in ok.read()
    for bad in (
        "http://example.com/static/css/character_sheet.css.evil",
        "http://codex.invalid/static/../app.py",
        "http://codex.invalid/etc/passwd",
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
    ):
        with pytest.raises(ValueError):
            fetcher.fetch(bad)


def test_character_path_rejects_bad_ids_even_without_route_checks():
    for bad_id in ["..", "../x", "a/b", "a b", ""]:
        assert app_module._load_character(bad_id) is None, bad_id
        with pytest.raises(ValueError):
            app_module._character_path(app_module.STATE_DIR, bad_id)


def test_merge_state_fills_missing_nested_keys_from_defaults():
    defaults = {
        "hp_current": 10,
        "currency": {"gp": 0, "sp": 0},
        "slot_used": {"1st": 0},
        "conditions": {"prone": False, "poisoned": False},
    }
    saved = {"hp_current": 4, "conditions": {"prone": True}}
    merged = app_module._merge_state(defaults, saved)
    assert merged["hp_current"] == 4
    assert merged["conditions"] == {"prone": True, "poisoned": False}
    assert merged["currency"] == {"gp": 0, "sp": 0}


def test_death_saves_from_form_counts_checked_boxes():
    form = {"death_success_0": "on", "death_success_2": "on", "death_failure_1": "on"}
    assert app_module._death_saves_from_form(form) == (2, 1)


def test_csp_forbids_inline_styles_and_pages_use_none(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp
    for url in ("/", "/guide", "/characters/sample_character"):
        body = client.get(url).data
        assert b' style="' not in body
        assert b"<style" not in body


def test_static_assets_are_cache_busted_and_immutable(client):
    body = client.get("/characters/sample_character").data.decode()
    match = re.search(r'href="(/static/css/character_sheet\.css\?v=\d+)"', body)
    assert match
    resp = client.get(match.group(1))
    assert "immutable" in resp.headers["Cache-Control"]


def test_unversioned_static_is_not_marked_immutable(client):
    resp = client.get("/static/css/character_sheet.css")
    assert "immutable" not in resp.headers.get("Cache-Control", "")


def test_favicon_is_a_quiet_204(client):
    assert client.get("/favicon.ico").status_code == 204


def test_sheet_labels_species_for_2024_and_race_otherwise(client, write_character):
    write_character("old_rules")
    write_character("new_rules", edition="2024")
    old = client.get("/characters/old_rules").get_data(as_text=True)
    new = client.get("/characters/new_rules").get_data(as_text=True)
    assert '<span class="label">Race</span>' in old
    assert '<span class="label">Species</span>' in new


def test_sheet_marks_expertise_skills(client, write_character):
    sample = Path(app_module.__file__).parent / "data/sample_character.yaml"
    char = yaml.safe_load(sample.read_text(encoding="utf-8"))
    for skill in char["skills"]:
        skill["prof"] = "expertise" if skill["name"] == "Athletics" else skill["prof"]
    write_character("expert", skills=char["skills"])
    html = client.get("/characters/expert").get_data(as_text=True)
    assert html.count("chk filled expertise") == 1


def test_attack_notes_column_only_appears_when_an_attack_has_notes(
    client, write_character
):
    write_character("plain")
    write_character(
        "noted",
        attacks=[
            {
                "name": "Dagger",
                "bonus": "+5",
                "damage": "1d4",
                "range": "Melee",
                "notes": "Finesse, Thrown",
            }
        ],
    )
    plain = client.get("/characters/plain").get_data(as_text=True)
    noted = client.get("/characters/noted").get_data(as_text=True)
    assert "<th>Notes</th>" not in plain
    assert "<th>Notes</th>" in noted and "Finesse, Thrown" in noted


def test_personality_boxes_share_one_markup(client):
    page = client.get("/characters/sample_character").get_data(as_text=True)
    page = unescape(page)
    sample = Path(app_module.__file__).parent / "data/sample_character.yaml"
    personality = yaml.safe_load(sample.read_text(encoding="utf-8"))["personality"]
    for field in ("traits", "ideals", "bonds", "flaws"):
        assert f'<div class="value">{personality[field]}</div>' in page


def test_treasure_items_accepts_every_supported_shape():
    cases = [
        (None, []),
        ("", []),
        ("A yoyo", [{"name": "", "text": "A yoyo"}]),
        (
            ["Ring", "Gems"],
            [{"name": "", "text": "Ring"}, {"name": "", "text": "Gems"}],
        ),
        ([{"name": "Mug", "text": "Tin"}], [{"name": "Mug", "text": "Tin"}]),
        ([{"name": "Mug"}, "", {}], [{"name": "Mug", "text": ""}]),
        ({"title": "Staff", "text": "Frost"}, [{"name": "Staff", "text": "Frost"}]),
        ({"title": "", "text": ""}, []),
    ]
    for raw, expected in cases:
        assert app_module._treasure_items(raw) == expected, raw


def test_treasure_renders_as_a_bulleted_list_under_a_plain_header(
    client, write_character
):
    write_character("loot", treasure=["Jade ring", {"name": "Mug", "text": "Tin cup"}])
    sheet = client.get("/characters/loot").data.decode()
    assert '<div class="section-title">Treasure</div>' in sheet
    assert "<li>Jade ring</li>" in sheet
    assert "<li><strong>Mug</strong>: Tin cup</li>" in sheet


def test_legacy_treasure_box_still_renders_with_title_as_item_name(
    client, write_character
):
    write_character("legacy", treasure={"title": "Staff of Frost", "text": "5 charges"})
    sheet = client.get("/characters/legacy").data.decode()
    assert "<li><strong>Staff of Frost</strong>: 5 charges</li>" in sheet
    assert "Treasure: Staff" not in sheet


def test_empty_character_file_is_not_found(client, data_dir):
    (data_dir / "empty.yaml").write_text("")
    assert client.get("/characters/empty").status_code == 404


def test_gender_and_faith_show_on_the_sheet_only_when_set(client, write_character):
    char = yaml.safe_load(
        (Path(__file__).parent.parent / "data" / "sample_character.yaml").read_text()
    )
    unset = client.get("/characters/sample_character").data.decode()
    assert "Gender" not in unset and "Faith" not in unset
    write_character("devout", appearance={**char["appearance"], "faith": "Pelor"})
    only_faith = client.get("/characters/devout").data.decode()
    assert 'Faith</span><span class="value">Pelor' in only_faith
    assert "Gender" not in only_faith
    both = {**char["appearance"], "gender": "Female", "faith": "Pelor"}
    write_character("both", appearance=both)
    sheet = client.get("/characters/both").data.decode()
    assert 'Gender</span><span class="value">Female' in sheet
    assert client.get("/characters/both/pdf").status_code == 200


# --- schema validation in the app -------------------------------------------


def test_invalid_character_file_shows_a_clear_error_page(
    client, write_character, data_dir
):
    path = write_character("broken")
    data = yaml.safe_load(path.read_text())
    data["hp"]["max"] = "ten"
    data["edition"] = 2024
    path.write_text(yaml.safe_dump(data))
    for url in ("/characters/broken", "/characters/broken/pdf"):
        resp = client.get(url)
        page = resp.data.decode()
        assert resp.status_code == 422, url
        assert "broken.yaml" in page and "file.hp.max" in page
        assert "found str &#39;ten&#39;" in page and "file.edition" in page
    assert client.post("/characters/broken/update", data={}).status_code == 422


def test_one_bad_file_never_breaks_the_listing_or_other_characters(
    client, write_character, data_dir
):
    write_character("good")
    (data_dir / "garbled.yaml").write_text("name: [unclosed\n  - oops: :")
    (data_dir / "noname.yaml").write_text("id: noname\n")
    page = client.get("/").data.decode()
    assert client.get("/").status_code == 200
    assert "Sample Character" in page and "garbled" in page and "noname" in page
    assert page.count("needs fixing") == 2
    assert client.get("/characters/good").status_code == 200
    garbled = client.get("/characters/garbled")
    assert garbled.status_code == 422 and "not valid YAML" in garbled.data.decode()


def test_display_name_falls_back_to_the_file_name(client):
    cases = [({"name": "Tess"}, "Tess"), ({"name": ""}, "fb"), ({}, "fb"), (None, "fb")]
    for data, expected in cases:
        assert app_module._display_name(data, "fb") == expected, data
    assert app_module._one_line("a\n  b\tc") == "a b c"


def test_valid_and_empty_files_keep_their_old_behavior(client, data_dir):
    assert client.get("/characters/sample_character").status_code == 200
    assert "needs fixing" not in client.get("/").data.decode()
    (data_dir / "empty.yaml").write_text("")
    assert client.get("/characters/empty").status_code == 404


def test_guide_carries_the_srd_attribution_that_creation_prints(client):
    import srd_lookup

    guide = client.get("/guide").data.decode()
    for needle in (
        "System Reference Document",
        "Wizards of the Coast LLC",
        "https://dnd.wizards.com/resources/systems-reference-document",
        "Creative Commons Attribution 4.0",
        "https://creativecommons.org/licenses/by/4.0/legalcode",
    ):
        assert needle in guide and needle in srd_lookup.ATTRIBUTION, needle


# --- rules text: formatter, links, pages ------------------------------------


def test_text_blocks_split_paragraphs_bullets_and_tables():
    text = (
        "While you have the **Poisoned** condition:\n"
        "\n"
        "* _Ability Checks_. Disadvantage on checks.\n"
        "- Attacks too.\n"
        "\n"
        "A second paragraph\n"
        "on two lines.\n"
        "| Level | Effect |\n"
        "| --- | --- |\n"
        "| 1 | Slow |"
    )
    blocks = app_module._text_blocks(text)
    assert [b["kind"] for b in blocks] == ["p", "ul", "p", "table"]
    assert blocks[0]["lines"] == ["While you have the Poisoned condition:"]
    assert blocks[1]["lines"] == [
        "Ability Checks. Disadvantage on checks.",
        "Attacks too.",
    ]
    assert blocks[2]["lines"] == ["A second paragraph", "on two lines."]
    assert blocks[3]["rows"] == [["Level", "Effect"], ["1", "Slow"]]
    assert app_module._text_blocks(None) == [] and app_module._text_blocks("\n\n") == []


@pytest.fixture
def rules(tmp_path, monkeypatch):
    """A tiny bundled rules directory instead of the real one."""
    directory = tmp_path / "rules"
    directory.mkdir()
    bundles = {
        "conditions-2014.json": [
            {"slug": "poisoned", "name": "Poisoned", "text": "Old <b>text</b>."},
            {"slug": "exhaustion", "name": "Exhaustion", "text": "Six levels."},
        ],
        "conditions-2024.json": [
            {"slug": "poisoned", "name": "Poisoned", "text": "New text."}
        ],
        "spells-2014.json": [
            {
                "slug": "hunters-mark",
                "name": "Hunter's Mark",
                "level": 1,
                "school": "Divination",
                "casting_time": "Bonus action",
                "range": "90 feet",
                "components": "V",
                "duration": "1 hour",
                "concentration": True,
                "ritual": False,
                "classes": ["Ranger"],
                "text": "You mark a creature.\n\n* It glows.",
                "higher": "Longer at higher levels.",
            },
            {
                "slug": "light",
                "name": "Light",
                "level": 0,
                "school": "Evocation",
                "casting_time": "Action",
                "range": "Touch",
                "components": "V, M",
                "duration": "1 hour",
                "concentration": False,
                "ritual": True,
                "classes": [],
                "text": "A glow.",
                "higher": "",
            },
        ],
    }
    for name, entries in bundles.items():
        (directory / name).write_text(json.dumps({"entries": entries}))
    monkeypatch.setattr(app_module, "RULES_DIR", directory)
    app_module._rules_index.cache_clear()
    yield directory
    app_module._rules_index.cache_clear()


def test_rules_url_exists_only_for_bundled_names_and_follows_the_edition(client, rules):
    with app_module.app.test_request_context():
        url = app_module._rules_url
        assert (
            url("conditions", "poisoned", "2014") == "/rules/2014/conditions/poisoned"
        )
        assert (
            url("conditions", "Poisoned", "2024") == "/rules/2024/conditions/poisoned"
        )
        assert url("conditions", "exhaustion", "2024") is None  # not in that bundle
        assert url("spells", "Hunter's Mark", None) == "/rules/2014/spells/hunters-mark"
        assert url("spells", "Mage Hand", "2014") is None
        assert url("spells", "Light", "weird") == "/rules/2014/spells/light"
    assert app_module._rules_edition(2024) == "2024"


def test_rules_pages_show_conditions_and_spells_and_escape_the_text(client, rules):
    page = client.get("/rules/2014/conditions/poisoned").data.decode()
    assert "<h1>Poisoned</h1>" in page and "2014 rules" in page
    assert "Old &lt;b&gt;text&lt;/b&gt;." in page and "<b>text</b>" not in page
    assert "Creative Commons Attribution 4.0" in page
    spell = client.get("/rules/2014/spells/hunters-mark").data.decode()
    for needle in (
        "Level 1 &middot; Divination &middot; Concentration",
        "<strong>Casting time:</strong> Bonus action",
        "<strong>Classes:</strong> Ranger",
        "<li>It glows.</li>",
        "At higher levels",
        "Longer at higher levels.",
    ):
        assert needle in spell, needle
    assert (
        "Cantrip &middot; Evocation &middot; Ritual"
        in client.get("/rules/2014/spells/light").data.decode()
    )


def test_rules_pages_refuse_anything_that_is_not_bundled(client, rules):
    urls = [
        "/rules/2014/conditions/nope",
        "/rules/2014/monsters/poisoned",
        "/rules/2019/conditions/poisoned",
        "/rules/2024/spells/hunters-mark",
        "/rules/2014/conditions/p\u00f6isoned",
        "/rules/2014/conditions/..%2f..%2fapp",
    ]
    for url in urls:
        assert client.get(url).status_code == 404, url


def test_sheet_links_conditions_and_spells_to_their_rules_text(
    client, rules, write_character
):
    spellcasting = {
        "class": "Ranger",
        "ability": "Wisdom",
        "cantrips": ["Light", "Mage Hand"],
        "slots": [{"level": "1st", "total": 2}],
        "prepared": ["Hunter's Mark"],
        "always_prepared": [{"spells": "Light, Unknown Spell", "note": "(racial)"}],
    }
    write_character("ranger", spellcasting=spellcasting)
    sheet = client.get("/characters/ranger").data.decode()
    assert 'href="/rules/2014/conditions/poisoned"' in sheet
    assert 'href="/rules/2014/conditions/exhaustion"' in sheet
    assert (
        'href="/rules/2014/conditions/blinded"' not in sheet
    )  # not in the test bundle
    assert sheet.count('href="/rules/2014/spells/light"') == 2
    assert 'href="/rules/2014/spells/hunters-mark"' in sheet
    assert "Mage Hand</div>" in sheet or "Mage Hand " in sheet
    assert "mage-hand" not in sheet
    for link in re.findall(r'<a class="rules-link"[^>]*>', sheet):
        assert 'target="_blank"' in link and 'rel="noopener"' in link
    pdf_html = app_module._render_sheet(
        "ranger", app_module._load_character("ranger"), pdf=True
    )
    assert "rules-link" not in pdf_html


def test_rules_links_are_hidden_when_printing():
    css = (
        Path(app_module.__file__).parent / "static" / "css" / "character_sheet.css"
    ).read_text()
    print_block = css[css.index("@media print") :]
    assert ".rules-link { display: none; }" in print_block


def test_the_bundled_rules_cover_every_condition_the_sheet_offers():
    for edition in ("2014", "2024"):
        index = app_module._rules_index("conditions", edition)
        wanted = [*app_module.CONDITION_KEYS, "exhaustion"]
        assert [k for k in wanted if k not in index] == [], edition
        assert len(app_module._rules_index("spells", edition)) > 300, edition


def test_bundled_rules_files_are_complete_and_carry_the_credit():
    import srd_lookup

    for kind in ("conditions", "spells"):
        for edition in ("2014", "2024"):
            path = app_module.RULES_DIR / f"{kind}-{edition}.json"
            bundle = json.loads(path.read_text(encoding="utf-8"))
            assert bundle["edition"] == edition
            assert bundle["attribution"] == srd_lookup.ATTRIBUTION
            for entry in bundle["entries"]:
                assert entry["slug"] == srd_lookup.slugify(entry["name"]), entry["name"]
                assert entry["text"].strip(), entry["name"]
