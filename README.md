# D&D Campaign Notebook

A personal D&D 5e campaign notebook: hand-maintained Markdown for characters, dungeon prep, and homebrew guides, plus a small self-hosted web app (`codex/`) for running and live-editing a character sheet during actual play.

## Structure

- `characters/` — character sheets and related reference material (hand-maintained Markdown/HTML).
- `dungeon/` — session/dungeon-crawl prep notes: room-by-room writeups, monster stat blocks, and a system for turning Magic: The Gathering booster-pack cards into loot/encounters.
- `guides/` — standalone homebrew rules guides (e.g. tarot-based character creation).
- `codex_roadmap.md` — running list of future ideas for `codex/`, not a commitment or schedule.
- `codex/` — the Flask/Docker character sheet app described below.

## `codex/`

Reads per-character YAML files and renders an HTML character sheet styled after the original hand-built reference sheet, with a "Save Changes" button that persists in-session state (HP, spell slots, currency, etc.) separately from the character's static build data.

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

### Creating a new character

```bash
cd codex
python scripts/new_character.py
```

Interactively generates a new `data/<id>.yaml` file. Choose `skeleton` mode for just the identity fields plus valid defaults you hand-fill afterward, or `full` mode to also be prompted for ability scores, proficiencies, equipment, backstory, etc., with derived stats (modifiers, proficiency bonus, passive perception) computed for you. Needs PyYAML (`pip install -r requirements.txt`), no other setup required. Either mode's output is a starting point, expect to hand-edit the result the same way existing character sheets are maintained.

### Testing

```bash
cd codex
pip install -r requirements-dev.txt
python -m black --check .   # formatting
python -m flake8 .          # linting
python -m pytest            # unit tests (Flask test client, no Docker needed)
```

The [codex tests](.github/workflows/codex-tests.yml) GitHub Actions workflow runs all of this automatically on every pull request (and push to `main`) that touches `codex/**`, across three jobs:

- **lint** — `black --check` and `flake8` against the whole app.
- **test** — the `pytest` suite in `codex/tests/`, exercising the Flask routes directly (index listing, character sheet rendering, the character-id allowlist that blocks path traversal, security headers, and that "Save Changes" persists the right fields to `state/<id>.yaml`).
- **docker-smoke-test** — builds the real `Dockerfile`, runs the resulting image, and curls `/` and a sample character sheet to confirm the container actually serves traffic end to end, the same check used to validate the Python 3.14 upgrade.
