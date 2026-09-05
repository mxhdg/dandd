import yaml
import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "STATE_DIR", tmp_path)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def test_index_lists_sample_character(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sample Character" in resp.data


def test_character_sheet_renders(client):
    resp = client.get("/characters/sample_character")
    assert resp.status_code == 200
    assert b"Sample Character" in resp.data


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


def test_update_unknown_character_404s(client):
    resp = client.post("/characters/does_not_exist/update", data={})
    assert resp.status_code == 404


def test_update_invalid_character_id_404s(client):
    resp = client.post("/characters/..%2f../update", data={})
    assert resp.status_code == 404
