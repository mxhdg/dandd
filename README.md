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

#### Upgrading to 1.4.0

Nothing to configure: `CODEX_ALLOWED_HOSTS`, the Host guard and the same-origin check are unchanged, and the new files the app needs (`srd_lookup.py`, `rules/`) are inside the image. What changes:

- **No arm64 image.** Only `linux/amd64` is published. On Apple silicon build locally with `docker-compose.dev.yml` (native arm64).
- **The script was renamed** from `scripts/new_character.py` to `scripts/character.py`; it now also levels up and edits characters (`--new`, `--level-up`, `--edit`).
- **Character files are checked when opened.** A file with a wrong type or a missing section shows a "needs fixing" page naming the fields instead of a half-drawn sheet; the other characters keep working. Files that opened before still do.
- **`treasure` is now a list** on the sheet (the old single `{title, text}` box still loads).
- **New `?` links** beside conditions and SRD spells open rule text from bundled files; the app makes no network calls. Character pages are sent `Cache-Control: no-store`.
- gunicorn is 26.2.0 and the image no longer contains pip.

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

### Creating and levelling up a character

```bash
cd codex
python scripts/character.py
```

With no flag the script asks whether to create a character, level one up, or edit one; `--new`, `--level-up [ID]` and `--edit [ID]` skip that question (see below). Creating interactively generates a new `data/<id>.yaml` file; the file name comes from the character's name (pass `--id` to choose another). Answers are forgiving: Enter keeps the `[default]`, names are matched without regard to case or by unique first letters (`ath` for Athletics), and a typo or non-number is explained and asked again instead of being dropped; Ctrl+C (or Ctrl+D) quits cleanly and saves nothing. It asks "quick or detailed" (`--mode skeleton|full`): `skeleton`/quick covers just the identity fields plus valid defaults you hand-fill afterward, and `full`/detailed also prompts for ability scores, proficiencies, equipment, backstory, etc., with derived stats (modifiers, proficiency bonus, passive perception) computed for you. Multiclass characters are supported: the script asks for each class in turn (name, level, optional subclass, hit die size, defaulting from the class name), then builds `Fighter 3 (Champion) / Ranger 1`, the combined hit dice (`4d10`, or `3d10 + 2d6` for mixed dice) and the proficiency bonus from total level; the sheet counts every die (one shared Used count). Both modes ask for the rules edition (2014 or 2024; 2024 relabels "Race" as "Species" on the sheet), and `full` mode asks which proficient skills have expertise. In a character file, a skill's `prof` is `true`, `false`, or `"expertise"`, `appearance` takes optional `gender` and `faith`, shown on page 2 only when set, `treasure` is a list (plain strings, or `{name, text}` for an item with a description; the older single `{title, text}` box still loads, with the title shown as the item name), and each attack can carry an optional `notes` string (the sheet only shows a Notes column when at least one attack has one). Needs PyYAML (`pip install -r requirements.txt`), no other setup required. Either mode's output is a starting point, expect to hand-edit the result the same way existing character sheets are maintained.

**Looking things up from the free SRD** (optional, creation only): add `--online`, or answer yes when asked "Look up classes, species and spells from the free SRD?". Nothing is requested from the network unless you do; if the lookup fails (offline, timeout) the script says so and you type everything yourself as before. With it on: the class you type is matched against the SRD (`wiz` finds Wizard; the hit die, saving-throw proficiencies and subclass names come along), the species and subspecies are matched the same way, the level 1 class features and species traits are offered to add to the sheet, and spell prompts accept part of a name (`fire` for Fire Bolt) limited to your class's list. Only the two System Reference Documents are used (`srd-2014` for 2014 rules, `srd-2024` for 2024), via the free [Open5e](https://open5e.com) API. Answers are cached for 30 days in `codex/.cache/srd/` (git-ignored). SRD text is licensed CC BY 4.0, so the credit line is printed after a lookup and kept in the Getting Started guide: *This work includes material from the System Reference Document (SRD) by Wizards of the Coast LLC, available at <https://dnd.wizards.com/resources/systems-reference-document>. The SRD is licensed under the Creative Commons Attribution 4.0 International License available at <https://creativecommons.org/licenses/by/4.0/legalcode>.*

**Levelling up** (`python scripts/character.py --level-up [ID]`, or pick "level-up" when asked; without an ID it lists your characters): the file is validated first and every problem is listed if it fails. You then choose which class gains the level (or add a new one for multiclass), enter the hit die roll (Enter uses the average; a Constitution modifier change also adjusts earlier levels), take an ability score improvement or a feat when you want one (it suggests it at levels 4, 8, 12, 16 and 19), add new features, and, for spellcasters, update slots and spells (slots are typed in by hand; save DC and attack bonus are suggested from your ability and proficiency bonus). Ability modifiers, saves, skills, passive Perception and initiative are updated by the amount they change, so custom bonuses you added by hand are kept. Attack bonuses, damage and Armor Class are not recalculated; the script lists what to review. Everything changed is shown (old -> new) and you confirm before it saves. The previous file is kept as `<id>.yaml.bak` (git-ignored) and `state/<id>.yaml` is never touched. Saving rewrites the file, so any comments in it are not kept.

**Editing** (`python scripts/character.py --edit [ID]`, or answer "edit"): a menu of nine sections (identity and background, ability scores and proficiencies, combat stats, attacks, equipment/treasure/money, features and allies, spellcasting, personality/appearance/backstory, languages and other proficiencies). Pick a section, answer its prompts (the current value is shown in brackets: Enter keeps it, `-` clears it; lists show numbered items so you can remove some and add others), and repeat until you press Enter at the menu. A section whose result would make the file invalid is discarded with the reasons, so a slip never costs you the other edits. Changing ability scores or proficiencies shifts the derived values by the change, the same way level-up does. As with level-up you see every change (old -> new) before confirming, `<id>.yaml.bak` is written first, and `state/` is untouched. Gaining a level goes through `--level-up`, which also handles hit points and features.

New to D&D and not sure what to pick for race/class/background before running the script? D&D Beyond's free [2014 Step-by-Step Characters](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/step-by-step-characters) guide (or, for 2024 rules, [Creating a Character](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character)) walks through those decisions. The script prints the one matching your chosen edition when it starts.

### Rules text on the sheet

Each condition on a character sheet, and each spell in the spellcasting section that is in the free SRD, has a small **?** beside it. Tapping it opens the rules text in a new tab (so unsaved edits on the sheet are never lost), worded for the character's own rules edition (2014 or 2024, from the `edition` field). The links are not part of the printed sheet or the PDF, and a spell the SRD does not contain simply has no link. The text is bundled in `codex/rules/*.json` (conditions and spells for both editions; about 750 KB) and read by the app from disk, so the running app never calls the network. Refresh it with `python scripts/build_rules.py` (needs internet; `--refresh` skips the 30-day download cache), review the diff, and commit. Entries the SRD leaves blank are skipped. Display only: there is no dice rolling or automation. The CC BY 4.0 credit is on every rules page and in the Getting Started guide.

### Character file checks

Every `data/<id>.yaml` is validated when it is opened (`codex/character_schema.py`, a small stdlib-only checker driven by one `SCHEMA` table). A file with problems shows an error page listing each wrong field (path, what was expected, what was found) instead of a 500, the character list marks it "needs fixing", and every other character keeps working. Unknown extra fields are allowed; wrong types, missing required sections, and a YAML syntax error are not. To support a new field, add one line to `SCHEMA`, to `data/character_template.yaml.example`, and to `scripts/character.py`; the tests fail if these drift apart.

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
