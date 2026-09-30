import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from flask import (
    Flask,
    Response,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)
from weasyprint import HTML, URLFetcher
from weasyprint.urls import URLFetcherResponse

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = (
    16 * 1024
)  # form posts here are a few dozen small fields

DATA_DIR = Path(__file__).parent / "data"
STATE_DIR = Path(__file__).parent / "state"
STATIC_DIR = Path(__file__).parent / "static"
STATE_DIR.mkdir(exist_ok=True)

CURRENCY_KEYS = ["cp", "sp", "ep", "gp", "pp"]

# 2014 PHB conditions, minus Exhaustion (tracked separately as a 0-6 level,
# see EXHAUSTION_EFFECTS below).
CONDITION_KEYS = [
    "blinded",
    "charmed",
    "deafened",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
]

# 2014 PHB exhaustion table. Effects are cumulative: level N has its own
# effect plus every lower level's. Index 0 is level 1.
EXHAUSTION_EFFECTS = [
    "Disadvantage on ability checks",
    "Speed halved",
    "Disadvantage on attack rolls and saving throws",
    "Hit point maximum halved",
    "Speed reduced to 0",
    "Death",
]

# Character ids become filenames (data/<id>.yaml, state/<id>.yaml); this keeps
# a path-traversal payload (e.g. "../../etc/passwd") from ever reaching disk,
# regardless of how permissive Flask's own URL routing turns out to be.
CHARACTER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _valid_character_id(character_id):
    return bool(CHARACTER_ID_RE.fullmatch(character_id))


def _same_origin_request(req):
    # No auth/session exists to hang a CSRF token off of (see CLAUDE.md), so
    # this checks Origin (falling back to Referer) against the request's own
    # host instead - enough to block a cross-site page from forging a POST
    # to /update, which a browser wouldn't let it forge these headers for.
    source = req.headers.get("Origin") or req.headers.get("Referer")
    if not source:
        return False
    return urlsplit(source).netloc == req.host


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
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; base-uri 'none'; object-src 'none'"
    )
    return response


def _character_path(directory, character_id):
    # Defense in depth: routes already reject bad ids, but every helper that
    # builds a path from one re-checks it, so a future caller can't reach
    # outside data/ or state/ by forgetting to. The normpath + prefix check is
    # the form static analysis (CodeQL) recognizes as a path sanitizer.
    if not _valid_character_id(character_id):
        raise ValueError("invalid character id")
    base = os.path.normpath(directory)
    full = os.path.normpath(os.path.join(base, f"{character_id}.yaml"))
    if not full.startswith(base + os.sep):
        raise ValueError("invalid character id")
    return Path(full)


def _load_character(character_id):
    try:
        path = _character_path(DATA_DIR, character_id)
    except ValueError:
        return None
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _list_characters():
    characters = []
    for path in sorted(DATA_DIR.glob("*.yaml")):
        data = _load_character(path.stem)
        characters.append({"id": path.stem, "name": data["name"]})
    return characters


def _default_state(char):
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
        "conditions": {k: False for k in CONDITION_KEYS},
        "concentration": "",
        "exhaustion": 0,
    }


def _load_state(character_id, char):
    state = _default_state(char)
    path = _character_path(STATE_DIR, character_id)
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            saved = yaml.safe_load(f) or {}
        state.update(saved)
        state["currency"] = {**state["currency"], **saved.get("currency", {})}
        state["slot_used"] = {**state["slot_used"], **saved.get("slot_used", {})}
        state["conditions"] = {**state["conditions"], **saved.get("conditions", {})}
    return state


def _save_state(character_id, state):
    path = _character_path(STATE_DIR, character_id)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(state, f, sort_keys=False)


def _apply_state(char, state):
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
    char["conditions"] = state["conditions"]
    char["concentration"] = state["concentration"]
    char["exhaustion"] = state["exhaustion"]
    for slot in char.get("spellcasting", {}).get("slots", []):
        slot["used"] = state["slot_used"].get(slot["level"], 0)
    return char


@app.route("/")
def index():
    return render_template("index.html", characters=_list_characters())


@app.route("/guide")
def guide():
    return render_template("guide.html")


@app.route("/characters/<character_id>")
def character_sheet(character_id):
    if not _valid_character_id(character_id):
        abort(404)
    data = _load_character(character_id)
    if data is None:
        abort(404)
    state = _load_state(character_id, data)
    data = _apply_state(data, state)
    return render_template(
        "character_sheet.html",
        c=data,
        condition_keys=CONDITION_KEYS,
        exhaustion_effects=EXHAUSTION_EFFECTS,
    )


class _StaticOnlyFetcher(URLFetcher):
    # WeasyPrint would otherwise fetch any URL the page references. The sheet
    # only needs its own stylesheet, so serve files under static/ and refuse
    # everything else (no network access, no arbitrary local files).
    def fetch(self, url, headers=None):
        url_path = urlsplit(url).path
        path = (STATIC_DIR / url_path.removeprefix("/static/")).resolve()
        if (
            not url_path.startswith("/static/")
            or not path.is_file()
            or STATIC_DIR.resolve() not in path.parents
        ):
            raise ValueError(f"blocked resource: {url}")
        mime = "text/css" if path.suffix == ".css" else "application/octet-stream"
        return URLFetcherResponse(url, path.read_bytes(), {"Content-Type": mime})


@app.route("/characters/<character_id>/pdf")
def character_pdf(character_id):
    # Rendered server-side so margins and page breaks are identical in every
    # browser, instead of depending on each browser's print dialog/engine.
    if not _valid_character_id(character_id):
        abort(404)
    data = _load_character(character_id)
    if data is None:
        abort(404)
    data = _apply_state(data, _load_state(character_id, data))
    html = render_template(
        "character_sheet.html",
        c=data,
        condition_keys=CONDITION_KEYS,
        exhaustion_effects=EXHAUSTION_EFFECTS,
        pdf=True,
    )
    pdf = HTML(
        string=html, base_url="http://codex.invalid/", url_fetcher=_StaticOnlyFetcher()
    ).write_pdf()
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{character_id}.pdf"'},
    )


def _parse_int_field(form, key, default):
    try:
        return int(form.get(key, "").strip())
    except ValueError:
        return default


def _apply_hp_delta(current, temp, damage, healing, max_hp):
    absorbed = min(temp, damage)
    temp -= absorbed
    damage -= absorbed
    current = max(current - damage, 0)
    current = min(current + healing, max_hp)
    return current, temp


def _state_from_form(form, previous, slot_levels, max_hp):
    xp_value = form.get("xp")
    concentration_value = form.get("concentration")
    hp_current, hp_temp = _apply_hp_delta(
        _parse_int_field(form, "hp_current", previous["hp_current"]),
        _parse_int_field(form, "hp_temp", previous["hp_temp"]),
        max(_parse_int_field(form, "damage_taken", 0), 0),
        max(_parse_int_field(form, "healing_received", 0), 0),
        max_hp,
    )
    return {
        "hp_current": hp_current,
        "hp_temp": hp_temp,
        "hit_dice_used": _parse_int_field(
            form, "hit_dice_used", previous["hit_dice_used"]
        ),
        "death_save_successes": sum(
            1 for i in range(3) if f"death_success_{i}" in form
        ),
        "death_save_failures": sum(1 for i in range(3) if f"death_failure_{i}" in form),
        "inspiration": "inspiration" in form,
        "xp": xp_value.strip() if xp_value is not None else previous["xp"],
        "concentration": (
            concentration_value.strip()
            if concentration_value is not None
            else previous["concentration"]
        ),
        "currency": {
            k: _parse_int_field(
                form, f"currency_{k}", previous["currency"].get(k, 0) or 0
            )
            for k in CURRENCY_KEYS
        },
        "slot_used": {
            level: _parse_int_field(
                form, f"slot_used_{level}", previous["slot_used"].get(level, 0)
            )
            for level in slot_levels
        },
        "conditions": {k: f"condition_{k}" in form for k in CONDITION_KEYS},
        "exhaustion": min(
            max(_parse_int_field(form, "exhaustion", previous["exhaustion"]), 0),
            len(EXHAUSTION_EFFECTS),
        ),
    }


def _hit_dice_count(total):
    # hit_dice.total is free text like "3d10" (or "3d10 + 2d8" for a
    # multiclass); the dice count is everything before each "d".
    return sum(int(n) for n in re.findall(r"(\d+)\s*d\s*\d+", str(total)))


def _apply_long_rest(state, char):
    # 2014 PHB: regain all HP, and up to half your total hit dice (min 1).
    total = _hit_dice_count(char["hit_dice"]["total"])
    state["hp_current"] = char["hp"]["max"]
    state["hp_temp"] = 0
    state["hit_dice_used"] = max(state["hit_dice_used"] - max(total // 2, 1), 0)
    state["death_save_successes"] = 0
    state["death_save_failures"] = 0
    state["slot_used"] = {level: 0 for level in state["slot_used"]}
    state["exhaustion"] = max(state["exhaustion"] - 1, 0)
    return state


def _apply_short_rest(state, char, form):
    total = _hit_dice_count(char["hit_dice"]["total"])
    remaining = max(total - state["hit_dice_used"], 0)
    spent = min(max(_parse_int_field(form, "rest_hit_dice_spent", 0), 0), remaining)
    healing = max(_parse_int_field(form, "rest_healing", 0), 0)
    state["hit_dice_used"] += spent
    state["hp_current"], state["hp_temp"] = _apply_hp_delta(
        state["hp_current"], state["hp_temp"], 0, healing, char["hp"]["max"]
    )
    return state


def _handle_update(character_id, rest=None):
    if not _same_origin_request(request):
        abort(403)
    if not _valid_character_id(character_id):
        abort(404)
    data = _load_character(character_id)
    if data is None:
        abort(404)
    previous = _load_state(character_id, data)
    slot_levels = [
        slot["level"] for slot in data.get("spellcasting", {}).get("slots", [])
    ]
    # Edits typed into the sheet before pressing a rest button are applied
    # first, not silently lost.
    state = _state_from_form(request.form, previous, slot_levels, data["hp"]["max"])
    if rest == "long":
        state = _apply_long_rest(state, data)
    elif rest == "short":
        state = _apply_short_rest(state, data, request.form)
    _save_state(character_id, state)
    return redirect(url_for("character_sheet", character_id=character_id))


@app.route("/characters/<character_id>/update", methods=["POST"])
def update_character(character_id):
    return _handle_update(character_id)


@app.route("/characters/<character_id>/rest/<kind>", methods=["POST"])
def rest_character(character_id, kind):
    if kind not in ("short", "long"):
        abort(404)
    return _handle_update(character_id, rest=kind)


if __name__ == "__main__":
    # Direct "python app.py" is for local template iteration only.
    # The container runs this through gunicorn.conf.py instead (see Dockerfile).
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
