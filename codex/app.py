import contextlib
import ipaddress
import os
import re
import threading
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
# Drop the newline/indent around {% %} lines from rendered HTML.
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
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


@app.after_request
def cache_versioned_static(response):
    if request.endpoint == "static" and "v" in request.args:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.route("/favicon.ico")
def favicon():
    # No icon to serve; answering 204 stops browsers logging a 404 per page.
    return "", 204


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


def _static_url(filename):
    # The file's mtime in the query string makes each edit a new URL, so the
    # asset can be cached "forever" (see cache_versioned_static) and still
    # update the moment it changes.
    version = int((STATIC_DIR / filename).stat().st_mtime)
    return url_for("static", filename=filename, v=version)


@app.context_processor
def inject_template_globals():
    return {
        "app_version": os.environ.get("APP_VERSION", "dev"),
        "app_commit_sha": os.environ.get("APP_COMMIT_SHA", "unknown"),
        "static_url": _static_url,
    }


# Hostnames a browser can only reach by name if public DNS can resolve them, so
# a DNS-rebinding page (which needs its own registered domain) can never use
# one of these; IP literals and single-label names can't be rebound either.
_LOCAL_NAME_SUFFIXES = (".local", ".lan", ".localdomain", ".home.arpa", ".internal")


def _host_name(host):
    return (urlsplit(f"//{host}").hostname or "").lower()


def _is_ip_literal(name):
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


def _extra_allowed_hosts():
    raw = os.environ.get("CODEX_ALLOWED_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _host_allowed(host):
    name = _host_name(host)
    return bool(name) and (
        host.lower() in _extra_allowed_hosts()
        or name in _extra_allowed_hosts()
        or _is_ip_literal(name)
        or "." not in name
        or name.endswith(_LOCAL_NAME_SUFFIXES)
    )


@app.before_request
def enforce_trusted_host():
    # There is no login, so the Host header is the only thing standing between
    # this app and a DNS-rebinding page on the same network (see CLAUDE.md).
    if not _host_allowed(request.host):
        abort(400)


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Not "no-referrer": that makes browsers send "Origin: null" on form POSTs,
    # which the same-origin check in _same_origin_request would reject.
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; "
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


def _read_saved_state(character_id):
    path = _character_path(STATE_DIR, character_id)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _merge_state(defaults, saved):
    # Nested dicts are merged key by key so a state file written before a new
    # key existed (e.g. a newly added condition) still loads with that default.
    state = {**defaults, **saved}
    for key in ("currency", "slot_used", "conditions"):
        state[key] = {**defaults[key], **saved.get(key, {})}
    return state


def _load_state(character_id, char):
    return _merge_state(_default_state(char), _read_saved_state(character_id))


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


def _character_or_404(character_id):
    if not _valid_character_id(character_id):
        abort(404)
    data = _load_character(character_id)
    if data is None:
        abort(404)
    return data


def _enforce_same_origin():
    if not _same_origin_request(request):
        abort(403)


def _render_sheet(character_id, data, pdf=False):
    state = _load_state(character_id, data)
    return render_template(
        "character_sheet.html",
        c=_apply_state(data, state),
        condition_keys=CONDITION_KEYS,
        exhaustion_effects=EXHAUSTION_EFFECTS,
        pdf=pdf,
    )


@app.route("/characters/<character_id>")
def character_sheet(character_id):
    return _render_sheet(character_id, _character_or_404(character_id))


def _resolve_static_file(url):
    url_path = urlsplit(url).path
    path = (STATIC_DIR / url_path.removeprefix("/static/")).resolve()
    if (
        not url_path.startswith("/static/")
        or not path.is_file()
        or STATIC_DIR.resolve() not in path.parents
    ):
        raise ValueError(f"blocked resource: {url}")
    return path


class _StaticOnlyFetcher(URLFetcher):
    # WeasyPrint would otherwise fetch any URL the page references. The sheet
    # only needs its own stylesheet, so serve files under static/ and refuse
    # everything else (no network access, no arbitrary local files).
    def fetch(self, url, headers=None):
        path = _resolve_static_file(url)
        mime = "text/css" if path.suffix == ".css" else "application/octet-stream"
        return URLFetcherResponse(url, path.read_bytes(), {"Content-Type": mime})


# A render costs about a second of CPU and ~150 MB, and there is no login, so
# cap how many run at once instead of letting repeated requests exhaust the box.
_PDF_RENDER_SLOTS = threading.BoundedSemaphore(2)


def _html_to_pdf(html):
    if not _PDF_RENDER_SLOTS.acquire(blocking=False):
        abort(503)
    try:
        return HTML(
            string=html,
            base_url="http://codex.invalid/",
            url_fetcher=_StaticOnlyFetcher(),
        ).write_pdf()
    finally:
        _PDF_RENDER_SLOTS.release()


@app.route("/characters/<character_id>/pdf")
def character_pdf(character_id):
    # Rendered server-side so margins and page breaks are identical in every
    # browser, instead of depending on each browser's print dialog/engine.
    data = _character_or_404(character_id)
    pdf = _html_to_pdf(_render_sheet(character_id, data, pdf=True))
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


def _text_field(form, key, previous):
    value = form.get(key)
    return value.strip() if value is not None else previous


def _as_int(value, default=0):
    # Currency starts out as whatever the data file holds ("" or "15"), so
    # coerce before doing arithmetic or comparisons on it.
    with contextlib.suppress(TypeError, ValueError):
        return int(value)
    return default


def _clamp(value, low, high):
    return min(max(value, low), high)


def _hp_from_form(form, previous, max_hp):
    return _apply_hp_delta(
        _clamp(_parse_int_field(form, "hp_current", previous["hp_current"]), 0, max_hp),
        max(_parse_int_field(form, "hp_temp", previous["hp_temp"]), 0),
        max(_parse_int_field(form, "damage_taken", 0), 0),
        max(_parse_int_field(form, "healing_received", 0), 0),
        max_hp,
    )


def _death_saves_from_form(form):
    successes = sum(1 for i in range(3) if f"death_success_{i}" in form)
    failures = sum(1 for i in range(3) if f"death_failure_{i}" in form)
    return successes, failures


def _currency_from_form(form, previous):
    return {
        k: max(_parse_int_field(form, f"currency_{k}", _as_int(previous.get(k))), 0)
        for k in CURRENCY_KEYS
    }


def _slots_used_from_form(form, previous, slot_totals):
    return {
        level: _clamp(
            _parse_int_field(form, f"slot_used_{level}", previous.get(level, 0)),
            0,
            total,
        )
        for level, total in slot_totals.items()
    }


def _hit_dice_used_from_form(form, previous, hit_dice_total):
    used = _parse_int_field(form, "hit_dice_used", previous)
    return _clamp(used, 0, hit_dice_total)


def _exhaustion_from_form(form, previous):
    level = _parse_int_field(form, "exhaustion", previous)
    return min(max(level, 0), len(EXHAUSTION_EFFECTS))


def _state_from_form(form, previous, limits):
    hp_current, hp_temp = _hp_from_form(form, previous, limits["max_hp"])
    death_successes, death_failures = _death_saves_from_form(form)
    return {
        "hp_current": hp_current,
        "hp_temp": hp_temp,
        "hit_dice_used": _hit_dice_used_from_form(
            form, previous["hit_dice_used"], limits["hit_dice"]
        ),
        "death_save_successes": death_successes,
        "death_save_failures": death_failures,
        "inspiration": "inspiration" in form,
        "xp": _text_field(form, "xp", previous["xp"]),
        "concentration": _text_field(form, "concentration", previous["concentration"]),
        "currency": _currency_from_form(form, previous["currency"]),
        "slot_used": _slots_used_from_form(
            form, previous["slot_used"], limits["slot_totals"]
        ),
        "conditions": {k: f"condition_{k}" in form for k in CONDITION_KEYS},
        "exhaustion": _exhaustion_from_form(form, previous["exhaustion"]),
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


def _apply_rest(state, char, form, rest):
    if rest == "long":
        return _apply_long_rest(state, char)
    if rest == "short":
        return _apply_short_rest(state, char, form)
    return state


def _limits_for(char):
    # Server-side ceilings for the numeric fields; the HTML max= attributes are
    # only a hint, anything can POST whatever it likes.
    slots = char.get("spellcasting", {}).get("slots", [])
    return {
        "max_hp": char["hp"]["max"],
        "hit_dice": _hit_dice_count(char["hit_dice"]["total"]),
        "slot_totals": {slot["level"]: slot["total"] for slot in slots},
    }


def _state_from_submission(character_id, data, form):
    previous = _load_state(character_id, data)
    return _state_from_form(form, previous, _limits_for(data))


def _handle_update(character_id, rest=None):
    _enforce_same_origin()
    data = _character_or_404(character_id)
    # Edits typed into the sheet before pressing a rest button are applied
    # first, not silently lost.
    state = _state_from_submission(character_id, data, request.form)
    _save_state(character_id, _apply_rest(state, data, request.form, rest))
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
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
