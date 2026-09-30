"""Integration tests: real routes, real templates, real files on disk.

Everything here goes through the Flask test client against temp data/state
directories; nothing touches the real data/ or state/.
"""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

import app as app_module

ROOT = Path(__file__).parent.parent

SPELLCASTING = {
    "class": "Wizard",
    "ability": "Intelligence",
    "save_dc": 14,
    "attack_bonus": "+6",
    "note": "Prepared from the spellbook.",
    "cantrips": ["Light", "Mage Hand"],
    "slots": [
        {"level": "1st", "total": 4, "used": 0},
        {"level": "2nd", "total": 2, "used": 0},
    ],
    "prepared": ["Shield", "Sleep"],
    "always_prepared": [{"spells": "Cure Wounds", "note": "(domain)"}],
    "cannon_modes": [{"name": "Force Ballista", "text": "Ranged spell attack."}],
    "cannon_stats": "AC 18, 5x level HP.",
}


def _saved(state_dir, character_id="sample_character"):
    return yaml.safe_load((state_dir / f"{character_id}.yaml").read_text())


def _field(html, name):
    """The value="..." of the named <input> on a rendered sheet."""
    match = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html)
    assert match, f"no input named {name}"
    return match.group(1)


# --- a whole play session ---------------------------------------------------


def test_full_session_journey(client, data_dir, tmp_path):
    base = "/characters/sample_character"
    max_hp = app_module._load_character("sample_character")["hp"]["max"]

    sheet = client.get(base).data.decode()
    assert _field(sheet, "hp_current") == str(max_hp)
    assert _field(sheet, "hit_dice_used") == "0"

    hit = client.post(
        f"{base}/update", data={"hp_current": str(max_hp), "damage_taken": "10"}
    )
    assert hit.status_code == 302 and hit.headers["Location"].endswith(base)
    sheet = client.get(base).data.decode()
    assert _field(sheet, "hp_current") == str(max_hp - 10)

    client.post(
        f"{base}/update",
        data={
            "hp_current": str(max_hp - 10),
            "condition_prone": "on",
            "concentration": "Bless",
            "exhaustion": "2",
            "currency_gp": "40",
            "xp": "900",
        },
    )
    sheet = client.get(base).data.decode()
    assert "checked" in re.search(r'name="condition_prone"[^>]*>', sheet).group(0)
    assert _saved(tmp_path)["concentration"] == "Bless"
    assert "Speed halved" in sheet
    assert _field(sheet, "currency_gp") == "40"

    client.post(
        f"{base}/rest/short",
        data={
            "hp_current": str(max_hp - 10),
            "rest_hit_dice_spent": "1",
            "rest_healing": "6",
        },
    )
    sheet = client.get(base).data.decode()
    assert _field(sheet, "hp_current") == str(max_hp - 4)
    assert _field(sheet, "hit_dice_used") == "1"

    client.post(
        f"{base}/rest/long", data={"hp_current": str(max_hp - 4), "exhaustion": "2"}
    )
    sheet = client.get(base).data.decode()
    assert _field(sheet, "hp_current") == str(max_hp)
    assert _field(sheet, "hit_dice_used") == "0"
    assert _saved(tmp_path)["exhaustion"] == 1

    pdf = client.get(f"{base}/pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


def test_spellcaster_sheet_slots_and_rests(client, write_character, tmp_path):
    write_character("wizard", name="Wizzy", spellcasting=SPELLCASTING)
    base = "/characters/wizard"
    sheet = client.get(base).data.decode()
    for expected in [
        "Wizzy: Spellcasting",
        "Light",
        "Mage Hand",
        "Spells Prepared (2)",
        "Cure Wounds",
        "Force Ballista",
        "AC 18",
        'name="slot_used_1st"',
        'name="slot_used_2nd"',
    ]:
        assert expected in sheet, expected

    client.post(
        f"{base}/update",
        data={"slot_used_1st": "3", "slot_used_2nd": "1", "slot_used_9th": "5"},
    )
    state = _saved(tmp_path, "wizard")
    assert state["slot_used"] == {"1st": 3, "2nd": 1}
    sheet = client.get(base).data.decode()
    assert _field(sheet, "slot_used_1st") == "3"

    client.post(f"{base}/rest/long", data={"slot_used_1st": "3", "slot_used_2nd": "1"})
    assert _saved(tmp_path, "wizard")["slot_used"] == {"1st": 0, "2nd": 0}
    assert client.get(f"{base}/pdf").status_code == 200


def test_non_caster_sheet_has_no_spell_page(client):
    body = client.get("/characters/sample_character").data.decode()
    assert "Spellcasting Class" not in body and "slot_used_" not in body


def test_caster_without_cannon_modes_omits_that_section(client, write_character):
    plain = {
        k: v
        for k, v in SPELLCASTING.items()
        if k not in ("cannon_modes", "cannon_stats")
    }
    write_character("plain", spellcasting=plain)
    body = client.get("/characters/plain").data.decode()
    assert "Spellcasting Class" in body and "Eldritch Cannon" not in body


# --- listing and state robustness ------------------------------------------


def test_index_lists_every_character_sorted_with_links(client, write_character):
    write_character("zed", name="Zed")
    write_character("amy", name="Amy")
    body = client.get("/").data.decode()
    order = [body.index(n) for n in ("Amy", "Sample Character", "Zed")]
    assert order == sorted(order)
    assert 'href="/characters/zed"' in body and 'href="/characters/amy"' in body


def test_index_with_no_characters_still_renders(client, data_dir):
    (data_dir / "sample_character.yaml").unlink()
    assert client.get("/").status_code == 200


def test_empty_or_partial_state_file_falls_back_to_defaults(client, tmp_path):
    max_hp = app_module._load_character("sample_character")["hp"]["max"]
    (tmp_path / "sample_character.yaml").write_text("")
    sheet = client.get("/characters/sample_character").data.decode()
    assert _field(sheet, "hp_current") == str(max_hp)

    # A state file from before exhaustion/conditions existed.
    (tmp_path / "sample_character.yaml").write_text("hp_current: 3\nhit_dice_used: 1\n")
    resp = client.get("/characters/sample_character")
    assert resp.status_code == 200
    assert _field(resp.data.decode(), "hp_current") == "3"


def test_state_is_per_character(client, write_character, tmp_path):
    write_character("other", name="Other")
    client.post("/characters/sample_character/update", data={"hp_current": "1"})
    assert not (tmp_path / "other.yaml").exists()
    other = client.get("/characters/other").data.decode()
    assert _field(other, "hp_current") == str(
        app_module._load_character("other")["hp"]["max"]
    )


def test_blank_template_file_renders_everywhere(client, data_dir):
    template = ROOT / "data" / "character_template.yaml.example"
    char = yaml.safe_load(template.read_text())
    char.update(id="blank", name="Blank")
    (data_dir / "blank.yaml").write_text(yaml.safe_dump(char))
    for url in ("/characters/blank", "/characters/blank/pdf"):
        assert client.get(url).status_code == 200, url


# --- generated characters flow into the app ---------------------------------


def test_skeleton_character_generated_by_script_renders_and_saves(
    client, data_dir, nc, argv, respond, monkeypatch, tmp_path
):
    monkeypatch.setattr(nc, "DATA_DIR", data_dir)
    argv("--id", "gen_skel", "--name", "Generated Skeleton", "--mode", "skeleton")
    respond({"Class & level": "Fighter 1"})
    nc.main()

    assert b"Generated Skeleton" in client.get("/").data
    sheet = client.get("/characters/gen_skel").data.decode()
    assert "Fighter 1" in sheet and _field(sheet, "hp_current") == "10"
    client.post("/characters/gen_skel/update", data={"hp_current": "4"})
    assert _saved(tmp_path, "gen_skel")["hp_current"] == 4
    assert client.get("/characters/gen_skel/pdf").data.startswith(b"%PDF")


def test_full_character_with_spells_generated_by_script_renders(
    client, data_dir, nc, argv, respond, monkeypatch
):
    monkeypatch.setattr(nc, "DATA_DIR", data_dir)
    argv("--id", "gen_full", "--name", "Generated Wizard", "--mode", "full")
    respond(
        {
            "Class & level": "Wizard 5",
            "Intelligence": "18",
            "Character level": "5",
            "Proficient saving throws": "Intelligence, Wisdom",
            "Proficient skills": "Arcana",
            "Max HP": "27",
            "Hit dice": "5d6",
            "name:": ["Arcane Recovery", ""],
            "text:": "Recover slots",
            "Include spellcasting": "y",
            "level": ["1st", ""],
            "total slots": "4",
            "Spellcasting class": "Wizard",
            "Cantrips": "Light",
        }
    )
    nc.main()

    sheet = client.get("/characters/gen_full").data.decode()
    assert "Arcane Recovery" in sheet and "Wizard" in sheet
    assert 'name="slot_used_1st"' in sheet
    client.post("/characters/gen_full/rest/long", data={"slot_used_1st": "4"})
    assert client.get("/characters/gen_full/pdf").status_code == 200


# --- HTTP surface: security, methods, limits --------------------------------


def test_every_route_sends_security_headers(client):
    urls = [
        "/",
        "/guide",
        "/characters/sample_character",
        "/characters/sample_character/pdf",
        "/favicon.ico",
        "/characters/missing",
        "/static/css/base.css",
    ]
    for url in urls:
        headers = client.get(url).headers
        assert headers["X-Content-Type-Options"] == "nosniff", url
        assert headers["X-Frame-Options"] == "DENY", url
        assert headers["Referrer-Policy"] == "no-referrer", url
        assert "script-src 'none'" in headers["Content-Security-Policy"], url


def test_posts_require_same_origin_on_every_mutating_route(client):
    routes = ["update", "rest/short", "rest/long"]
    for route in routes:
        url = f"/characters/sample_character/{route}"
        headers = {"Origin": "http://evil.example"}
        assert client.post(url, headers=headers).status_code == 403, route
        client.environ_base.pop("HTTP_ORIGIN", None)
        assert client.post(url).status_code == 403, route
        client.environ_base["HTTP_ORIGIN"] = "http://localhost"
        assert client.post(url).status_code == 302, route


def test_same_origin_helper_accepts_origin_and_referer_with_port(client):
    class Req:
        def __init__(self, headers, host):
            self.headers, self.host = headers, host

    same = app_module._same_origin_request
    assert same(Req({"Origin": "http://localhost:8890"}, "localhost:8890"))
    assert same(
        Req({"Referer": "http://localhost:8890/characters/x"}, "localhost:8890")
    )
    assert not same(Req({"Origin": "http://localhost:9999"}, "localhost:8890"))
    assert not same(Req({}, "localhost:8890"))


def test_mutating_routes_reject_get_and_bad_ids_and_bad_rest_kinds(client):
    assert client.get("/characters/sample_character/update").status_code == 405
    assert client.get("/characters/sample_character/rest/long").status_code == 405
    assert client.post("/characters/sample_character/rest/nap").status_code == 404
    for bad_id in ["missing", "a b", ".."]:
        assert client.post(f"/characters/{bad_id}/update").status_code == 404, bad_id
        assert client.get(f"/characters/{bad_id}/pdf").status_code == 404, bad_id


def test_oversized_post_is_rejected(client):
    resp = client.post("/characters/sample_character/update", data={"xp": "x" * 20000})
    assert resp.status_code == 413


def test_path_helper_blocks_escape_even_if_the_id_check_is_bypassed(monkeypatch):
    monkeypatch.setattr(app_module, "_valid_character_id", lambda _id: True)
    with pytest.raises(ValueError):
        app_module._character_path(app_module.STATE_DIR, "../escape")


def test_pdf_response_headers_and_filename(client):
    resp = client.get("/characters/sample_character/pdf")
    assert resp.mimetype == "application/pdf"
    assert (
        resp.headers["Content-Disposition"] == 'inline; filename="sample_character.pdf"'
    )


def test_pdf_render_uses_pdf_stylesheet_and_omits_the_pdf_link(client):
    data = app_module._load_character("sample_character")
    with app_module.app.test_request_context():
        pdf_html = app_module._render_sheet("sample_character", data, pdf=True)
        web_html = app_module._render_sheet("sample_character", data, pdf=False)
    assert "css/pdf.css" in pdf_html and 'class="pdf-link"' not in pdf_html
    assert "css/pdf.css" not in web_html and 'class="pdf-link"' in web_html


def test_static_fetcher_rejects_missing_files_and_directories():
    for url in [
        "http://codex.invalid/static/css/nope.css",
        "http://codex.invalid/static/css",
    ]:
        with pytest.raises(ValueError):
            app_module._resolve_static_file(url)
    path = app_module._resolve_static_file("http://codex.invalid/static/css/pdf.css")
    assert path.name == "pdf.css"


def test_footer_shows_the_build_version(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v9.9.9-test")
    assert b"v9.9.9-test" in client.get("/").data


def test_gunicorn_config_is_loadable_and_sane():
    spec = importlib.util.spec_from_file_location(
        "gunicorn_conf", ROOT / "gunicorn.conf.py"
    )
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    assert conf.bind.endswith(":5000")
    assert conf.workers >= 1 and conf.threads >= 1 and conf.timeout >= 30
