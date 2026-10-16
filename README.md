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

### Characters: create, level up, edit

One script does all three. Run it from `codex/` (it needs PyYAML, which `pip install -r requirements.txt` provides):

```bash
cd codex
python scripts/character.py
```

With no flag it asks what you want to do. Flags skip that question:

| Command | What it does |
|---|---|
| `python scripts/character.py --new` | Create a character (add `--online` to look things up from the free SRD) |
| `python scripts/character.py --level-up [ID]` | Advance an existing character one level |
| `python scripts/character.py --edit [ID]` | Change anything on an existing character |

Leave off `ID` and the script lists your characters so you can pick one.

Every prompt follows the same rules, so you never have to guess:

- **Enter** keeps the value shown in `[brackets]`, or skips the question.
- **Names are forgiving.** Upper or lower case both work, and so does the start of a name (`ath` finds Athletics).
- **A typo is explained and asked again,** and so is a non-number where a number is expected. Nothing is silently dropped.
- **Ctrl+C** (or Ctrl+D) quits at any point and saves nothing.

If you are new to D&D and unsure what to pick for race, class or background, D&D Beyond's free [2014 Step-by-Step Characters](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/step-by-step-characters) guide (or, for 2024 rules, [Creating a Character](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character)) walks through those decisions. The script prints the link that matches your chosen edition when it starts.

#### Creating a character

The script writes a new `data/<id>.yaml`. The id comes from the character's name; pass `--id` to choose another.

1. **Rules edition** is asked first (2014 or 2024). 2024 relabels "Race" as "Species" on the sheet.
2. **Quick or detailed** (`--mode skeleton|full`):
   - *Quick* asks for the identity fields and fills in valid defaults for everything else, so the sheet works straight away.
   - *Detailed* also asks for ability scores, proficiencies (and which skills have expertise), equipment, backstory and more, and computes the derived numbers for you (modifiers, proficiency bonus, passive Perception).
3. **Classes** are asked one at a time, so multiclass works: name, level, optional subclass, and hit die (suggested from the class name). The script builds the class line (`Fighter 3 (Champion) / Ranger 1`), the combined hit dice (`4d10`, or `3d10 + 2d6` for mixed dice) and the proficiency bonus from your total level. The sheet counts every die, with one shared Used count.

Treat the result as a first draft: open the file and hand-edit anything you skipped, the same way the existing sheets are maintained.

##### Looking things up from the free SRD (optional)

Add `--online`, or answer yes when asked "Look up classes, species and spells from the free SRD?". It is off unless you ask for it, and nothing is requested from the network otherwise. If the lookup fails (offline, timeout) the script says so and you type everything yourself, as usual.

With it on:

- Your class is matched against the SRD (`wiz` finds Wizard). The hit die, saving-throw proficiencies and subclass names come along.
- Species and subspecies are matched the same way.
- Level 1 class features and species traits are offered for you to add to the sheet.
- Spell prompts accept part of a name (`fire` finds Fire Bolt), limited to your class's spell list.

Only the two System Reference Documents are used (`srd-2014` for 2014 rules, `srd-2024` for 2024), through the free [Open5e](https://open5e.com) API. Answers are cached for 30 days in `codex/.cache/srd/` (git-ignored).

SRD text is licensed CC BY 4.0, so the credit is printed after a lookup and kept in the Getting Started guide: *This work includes material from the System Reference Document (SRD) by Wizards of the Coast LLC, available at <https://dnd.wizards.com/resources/systems-reference-document>. The SRD is licensed under the Creative Commons Attribution 4.0 International License available at <https://creativecommons.org/licenses/by/4.0/legalcode>.*

#### Levelling up

`python scripts/character.py --level-up [ID]`, or answer "level-up" when asked.

1. The file is checked first. If it has problems, every one is listed and nothing changes.
2. Pick the class that gains the level, or add a new class for multiclass.
3. Enter your hit die roll. Enter uses the average, and a change in your Constitution modifier also adjusts hit points for earlier levels.
4. Take an ability score improvement or a feat if you want one. It is suggested at levels 4, 8, 12, 16 and 19.
5. Add any new features.
6. Spellcasters update slots and spells. Slots are typed in by hand; the save DC and attack bonus are suggested from your ability and proficiency bonus.
7. Review the changes (old -> new) and confirm before anything is saved.

Ability modifiers, saves, skills, passive Perception and initiative move by the amount they change, so bonuses you added by hand are kept. Attack bonuses, damage and Armor Class are **not** recalculated; the script lists what to review.

#### Editing

`python scripts/character.py --edit [ID]`, or answer "edit". You get a menu of nine sections:

1. Identity and background
2. Ability scores and proficiencies
3. Combat stats
4. Attacks
5. Equipment, treasure and money
6. Features and allies
7. Spellcasting
8. Personality, appearance and backstory
9. Languages and other proficiencies

Pick a section, answer its prompts, and repeat until you press Enter at the menu. The current value shows in brackets: Enter keeps it and `-` clears it. Lists show numbered items so you can remove some and add others. A section whose result would make the file invalid is discarded with the reasons, so one slip never costs you your other edits. Changing ability scores or proficiencies shifts the derived values by the change, the same as level-up. To gain a level, use `--level-up`, which also handles hit points and features.

#### Level-up and edit safety

- You see every change (old -> new) and confirm before saving.
- The previous file is kept as `<id>.yaml.bak` (git-ignored).
- `state/<id>.yaml` (current HP, slots used and so on) is never touched.
- Saving rewrites the file, so any comments in it are not kept.

#### What goes in a character file

`data/character_template.yaml.example` is the blank starting point. A few things worth knowing:

- A skill's `prof` is `true`, `false` or `"expertise"`.
- `appearance` takes optional `gender` and `faith`, shown on page 2 only when set.
- `treasure` is a list: plain strings, or `{name, text}` for an item with a description. The older single `{title, text}` box still loads, with the title shown as the item name.
- Each attack can carry an optional `notes` string; the sheet only shows a Notes column when at least one attack has one.

#### Character file checks

Every `data/<id>.yaml` is validated when it is opened (`codex/character_schema.py`, a small stdlib-only checker driven by one `SCHEMA` table).

- A file with problems shows an error page listing each wrong field (path, what was expected, what was found) instead of a 500.
- The character list marks that file "needs fixing", and every other character keeps working.
- Unknown extra fields are allowed. Wrong types, missing required sections and YAML syntax errors are not.
- To support a new field, add one line to `SCHEMA`, to `data/character_template.yaml.example` and to `scripts/character.py`. The tests fail if these drift apart.

### Rules text on the sheet

Each condition on a character sheet, and each spell in the spellcasting section that is in the free SRD, has a small **?** beside it.

- Tapping it opens the rules text in a **new tab**, so unsaved edits on the sheet are never lost.
- The wording matches the character's own rules edition (2014 or 2024, from the `edition` field).
- The links do not appear on the printed sheet or the PDF, and a spell the SRD does not contain simply has no link.
- It is display only: there is no dice rolling or automation.

The text is bundled in `codex/rules/*.json` (conditions and spells for both editions, about 750 KB) and read from disk, so the running app never calls the network. To refresh it, run `python scripts/build_rules.py` (needs internet; `--refresh` skips the 30-day download cache), review the diff and commit. Entries the SRD leaves blank are skipped. The CC BY 4.0 credit is on every rules page and in the Getting Started guide.

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
