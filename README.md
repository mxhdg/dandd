# D&D Campaign Notebook

A personal D&D 5e campaign notebook: hand-maintained Markdown for characters, dungeon prep, and homebrew guides, plus a small self-hosted web app (`sheet-app/`) for running and live-editing a character sheet during actual play.

## Structure

- `characters/` — character sheets and related reference material (hand-maintained Markdown/HTML).
- `dungeon/` — session/dungeon-crawl prep notes: room-by-room writeups, monster stat blocks, and a system for turning Magic: The Gathering booster-pack cards into loot/encounters.
- `guides/` — standalone homebrew rules guides (e.g. tarot-based character creation).
- `sheet_app_roadmap.md` — running list of future ideas for `sheet-app/`, not a commitment or schedule.
- `sheet-app/` — the Flask/Docker character sheet app described below.

## `sheet-app/`

Reads per-character YAML files and renders an HTML character sheet styled after the original hand-built reference sheet, with a "Save Changes" button that persists in-session state (HP, spell slots, currency, etc.) separately from the character's static build data.

### Local development

```bash
cd sheet-app
docker compose -f docker-compose.dev.yml up -d --build
```

Then open `http://localhost:8890`. This always builds the image locally from source, it never pulls from a registry.

### Production (home lab)

```bash
cd sheet-app
docker compose -f docker-compose.prod.yml up -d
```

Pulls the published image from `ghcr.io/mxhdg/dandd/sheet-app` and uses standard `/opt/sheet-app/...` bind-mount paths. Set `SHEET_APP_TAG` to pin a specific version instead of `latest`.

See `CLAUDE.md` for full implementation detail (data model, CI/release process, security posture).
