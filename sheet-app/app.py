import os
import re
from pathlib import Path

import yaml
from flask import Flask, abort, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # form posts here are a few dozen small fields

DATA_DIR = Path(__file__).parent / "data"
STATE_DIR = Path(__file__).parent / "state"
STATE_DIR.mkdir(exist_ok=True)

CURRENCY_KEYS = ["cp", "sp", "ep", "gp", "pp"]

# Character ids become filenames (data/<id>.yaml, state/<id>.yaml); this keeps
# a path-traversal payload (e.g. "../../etc/passwd") from ever reaching disk,
# regardless of how permissive Flask's own URL routing turns out to be.
CHARACTER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def valid_character_id(character_id):
    return bool(CHARACTER_ID_RE.fullmatch(character_id))


@app.context_processor
def inject_app_version():
    return {
        "app_version": os.environ.get("APP_VERSION", "dev"),
        "app_commit_sha": os.environ.get("APP_COMMIT_SHA", "unknown"),
    }


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; frame-ancestors 'none'"
    )
    return response


def load_character(character_id):
    path = DATA_DIR / f"{character_id}.yaml"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_characters():
    characters = []
    for path in sorted(DATA_DIR.glob("*.yaml")):
        data = load_character(path.stem)
        characters.append({"id": path.stem, "name": data["name"]})
    return characters


def default_state(char):
    slots = char.get("spellcasting", {}).get("slots", [])
    return {
        "hp_current": char["hp"]["max"],
        "hp_temp": 0,
        "hit_dice_used": 0,
        "death_save_successes": 0,
        "death_save_failures": 0,
        "inspiration": bool(char.get("inspiration", False)),
        "xp": char.get("xp") or "",
        "currency": {k: char.get("currency", {}).get(k, "") for k in CURRENCY_KEYS},
        "slot_used": {slot["level"]: 0 for slot in slots},
    }


def load_state(character_id, char):
    state = default_state(char)
    path = STATE_DIR / f"{character_id}.yaml"
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            saved = yaml.safe_load(f) or {}
        state.update(saved)
        state["currency"] = {**state["currency"], **saved.get("currency", {})}
        state["slot_used"] = {**state["slot_used"], **saved.get("slot_used", {})}
    return state


def save_state(character_id, state):
    path = STATE_DIR / f"{character_id}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(state, f, sort_keys=False)


def apply_state(char, state):
    char["hp"]["current"] = state["hp_current"]
    char["hp"]["temp"] = state["hp_temp"]
    char["hit_dice"]["used"] = state["hit_dice_used"]
    char["death_saves"] = {
        "successes": state["death_save_successes"],
        "failures": state["death_save_failures"],
    }
    char["inspiration"] = state["inspiration"]
    char["xp"] = state["xp"]
    char["currency"] = state["currency"]
    for slot in char.get("spellcasting", {}).get("slots", []):
        slot["used"] = state["slot_used"].get(slot["level"], 0)
    return char


@app.route("/")
def index():
    return render_template("index.html", characters=list_characters())


@app.route("/characters/<character_id>")
def character_sheet(character_id):
    if not valid_character_id(character_id):
        abort(404)
    data = load_character(character_id)
    if data is None:
        abort(404)
    state = load_state(character_id, data)
    data = apply_state(data, state)
    return render_template("character_sheet.html", c=data)


@app.route("/characters/<character_id>/update", methods=["POST"])
def update_character(character_id):
    if not valid_character_id(character_id):
        abort(404)
    data = load_character(character_id)
    if data is None:
        abort(404)
    previous = load_state(character_id, data)
    form = request.form

    def as_int(key, default):
        value = form.get(key, "").strip()
        try:
            return int(value)
        except ValueError:
            return default

    slot_levels = [slot["level"] for slot in data.get("spellcasting", {}).get("slots", [])]

    xp_value = form.get("xp")

    state = {
        "hp_current": as_int("hp_current", previous["hp_current"]),
        "hp_temp": as_int("hp_temp", previous["hp_temp"]),
        "hit_dice_used": as_int("hit_dice_used", previous["hit_dice_used"]),
        "death_save_successes": sum(1 for i in range(3) if f"death_success_{i}" in form),
        "death_save_failures": sum(1 for i in range(3) if f"death_failure_{i}" in form),
        "inspiration": "inspiration" in form,
        "xp": xp_value.strip() if xp_value is not None else previous["xp"],
        "currency": {k: as_int(f"currency_{k}", previous["currency"].get(k, 0) or 0) for k in CURRENCY_KEYS},
        "slot_used": {level: as_int(f"slot_used_{level}", previous["slot_used"].get(level, 0)) for level in slot_levels},
    }
    save_state(character_id, state)
    return redirect(url_for("character_sheet", character_id=character_id))


if __name__ == "__main__":
    # Direct "python app.py" is for local template iteration only.
    # The container runs this through gunicorn.conf.py instead (see Dockerfile).
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
