import re
from pathlib import Path

import pytest
import yaml

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "STATE_DIR", tmp_path)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        # Real browsers send Origin on POSTs; set it here so every existing
        # test reflects that instead of adding it to each call site.
        client.environ_base["HTTP_ORIGIN"] = "http://localhost"
        yield client


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


@pytest.mark.parametrize("bad_id", ["..", "%2e%2e", "a b", "a/../b"])
def test_invalid_character_id_404s(client, bad_id):
    resp = client.get(f"/characters/{bad_id}")
    assert resp.status_code == 404


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


@pytest.mark.parametrize(
    "total,count", [("3d10", 3), ("3d10 + 2d8", 5), ("1d8", 1), ("", 0)]
)
def test_hit_dice_count(total, count):
    assert app_module._hit_dice_count(total) == count


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


@pytest.mark.parametrize("bad_id", ["..", "../x", "a/b", "a b", ""])
def test_character_path_rejects_bad_ids_even_without_route_checks(bad_id):
    assert app_module._load_character(bad_id) is None
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
