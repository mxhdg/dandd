# D&D Campaign Notebook

A personal D&D 5e campaign notebook: hand-maintained Markdown for characters and homebrew guides, plus a small self-hosted web app (`codex/`) for running and live-editing a character sheet during actual play. Campaign-specific prep (dungeon crawls, session notes, NPC dialogue) lives in its own sibling repo per campaign instead, e.g. `TheChillBeneaththeCrust/`.

## Structure

- `characters/` — character sheets and related reference material (hand-maintained Markdown/HTML).
- `guides/` — standalone homebrew rules guides (e.g. tarot-based character creation).
- `codex_roadmap.md` — running list of future ideas for `codex/`, not a commitment or schedule.
- `codex/` — the Flask/Docker character sheet app described below.

## `codex/`

Reads per-character YAML files and renders an HTML character sheet styled after the original hand-built reference sheet, with a "Save Changes" button that persists in-session state (HP, spell slots, currency, etc.) separately from the character's static build data. HP updates by delta ("Damage Taken" / "Healing Received" fields that adjust current HP, accounting for temp HP absorption and capping at max) rather than by typing a new total. Short Rest and Long Rest buttons apply the 2014 rest rules (HP, hit dice, spell slots, death saves), and an exhaustion tracker (0-6) lists the effects at the current level. A "PDF" button on each sheet opens a server-rendered PDF (WeasyPrint) with consistent page margins in any browser.

### Local development

```bash
cd codex
docker compose -f docker-compose.dev.yml up -d --build
```

Then open `http://localhost:8890`. This always builds the image locally from source, it never pulls from a registry.

### Production (home lab)

```bash
cd codex
docker compose -f docker-compose.prod.yml up -d
```

Pulls the published image from `ghcr.io/mxhdg/dandd/codex` and uses standard `/opt/codex/...` bind-mount paths. Set `CODEX_TAG` to pin a specific version instead of `latest`.

#### Allowed hostnames (DNS-rebinding guard)

The app has no login, so it refuses any request whose `Host` header is a public-looking hostname (a defense against DNS-rebinding attacks). These work out of the box: `localhost`, IP addresses, single-label names (`codex`), and `*.local`, `*.lan`, `*.localdomain`, `*.home.arpa`, `*.internal`. Anything else gets a `400`.

To serve it under any other name (your own domain, a reverse proxy, a Cloudflare Tunnel), set `CODEX_ALLOWED_HOSTS` to a comma-separated list of bare hostnames (no `https://`, no path; a port is optional) in `docker-compose.prod.yml`. The block is already there, commented out:

```yaml
    environment:
      CODEX_ALLOWED_HOSTS: codex.yourdomain.com
```

To keep the domain out of git, instead write `CODEX_ALLOWED_HOSTS: ${CODEX_ALLOWED_HOSTS:-}` in that block and put `CODEX_ALLOWED_HOSTS=codex.yourdomain.com` in a `.env` file next to the compose file (Compose reads it automatically, the same way as `CODEX_TAG`). Either way, apply it with `docker compose -f docker-compose.prod.yml up -d`. Set this **before** upgrading to 1.3.1 or later, or the site answers `400` after the upgrade.

**Cloudflare Tunnel:** `cloudflared` forwards your public hostname as the `Host` header by default, so that hostname is the value to list. Leave the tunnel's **HTTP Host Header** override (Zero Trust, Networks, Tunnels, your tunnel, Public Hostname, Additional application settings, HTTP Settings) empty, or `originRequest.httpHostHeader` unset in a config file. Rewriting `Host` to an internal name makes "Save Changes" fail with `403`, because the save endpoint compares the browser's `Origin` to `Host`.

**Put a login in front of it.** This app has none, so anyone who finds a publicly reachable URL can view and edit the sheets. For a tunnel, add a Cloudflare Access application for the hostname (Zero Trust, Access, Applications) with a policy allowing only your players' emails; it needs no code change.

### Creating a new character

```bash
cd codex
python scripts/new_character.py
```

Interactively generates a new `data/<id>.yaml` file. Choose `skeleton` mode for just the identity fields plus valid defaults you hand-fill afterward, or `full` mode to also be prompted for ability scores, proficiencies, equipment, backstory, etc., with derived stats (modifiers, proficiency bonus, passive perception) computed for you. Both modes ask for the rules edition (2014 or 2024; 2024 relabels "Race" as "Species" on the sheet), and `full` mode asks which proficient skills have expertise. In a character file, a skill's `prof` is `true`, `false`, or `"expertise"`, and each attack can carry an optional `notes` string (the sheet only shows a Notes column when at least one attack has one). Needs PyYAML (`pip install -r requirements.txt`), no other setup required. Either mode's output is a starting point, expect to hand-edit the result the same way existing character sheets are maintained.

New to D&D and not sure what to pick for race/class/background before running the script? D&D Beyond's free [Step-by-Step Characters](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/step-by-step-characters) guide walks through those decisions.

### Testing

```bash
cd codex
pip install -r requirements-dev.txt   # hash-pinned; edit requirements*.in and recompile, never the .txt
python -m black --check .   # formatting
python -m flake8 .          # linting
python -m isort --check .     # import order
python -m pytest --cov      # unit + integration tests with coverage (must stay at 100%)
```

The [codex tests](.github/workflows/codex-tests.yml) GitHub Actions workflow runs all of this automatically on every pull request (and push to `main`) that touches `codex/**`, across three jobs:

- **lint** — `black --check`, `isort --check` and `flake8` (including a cyclomatic-complexity limit) against the whole app.
- **test** — the `pytest` suite in `codex/tests/`, exercising the Flask routes directly (index listing, character sheet rendering, the character-id allowlist that blocks path traversal, security headers, and that "Save Changes" persists the right fields to `state/<id>.yaml`).
- **docker-smoke-test** — builds the real `Dockerfile`, runs the resulting image, and curls `/` and a sample character sheet to confirm the container actually serves traffic end to end, the same check used to validate the Python 3.14 upgrade.
