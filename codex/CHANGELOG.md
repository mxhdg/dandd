# Changelog

All notable changes to `codex/` are listed here, newest first. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(the single source of truth is `[project] version` in `pyproject.toml`).

Add an entry under the version you are working on in the same change that
makes the change (headed `unreleased`), and set the date in the final bump PR
into `main`, releasing the same day, so no follow-up PR is needed. A test fails
if the current version has no entry here. The longer reasoning behind each
change lives in `../codex_roadmap.md`.

## [1.5.0] - unreleased

### Added
- Add to Home Screen support: a web manifest (`static/manifest.webmanifest`),
  a d20 icon set in `static/icons/` and a shared `_head_links.html` partial
  (manifest, Apple touch icon, theme color) on every page except the PDF
  render, so the sheet can be installed on a phone like an app. No JavaScript
  or service worker; it still needs the network.

### Fixed
- The level-up ability prompt is one line, "Ability to raise (one name for +2,
  or two for +1 each, e.g. Charisma, Constitution)", instead of two
  parentheticals back to back, and no longer says "blank for none" (a blank
  answer is rejected there).

## [1.4.2] - 2026-10-24

### Security
- Bump Pillow 12.3.0 to 13.0.0 and Brotli 1.2.0 to 1.2.1 (WeasyPrint's
  dependencies), clearing 30 open Dependabot alerts.

## [1.4.1] - 2026-10-16

### Added
- This changelog, with a test that keeps an entry for the current version.

## [1.4.0] - 2026-10-16

Character creation tooling, plus the sheet, image and workflow work that came
with it (shipped through nine release candidates).

### Added
- **One script for characters:** `scripts/character.py` creates, levels up and
  edits characters. With no flag it asks what you want; `--new`,
  `--level-up [ID]` and `--edit [ID]` skip the question.
- **Level-up:** pick the class that gains the level (or add one for
  multiclass), hit points by roll or average with a retroactive Constitution
  adjustment, ability score improvement or feat, new features, and spell
  changes. Derived values move by the change so hand-added bonuses survive.
- **Edit menu:** nine sections (identity, abilities and proficiencies, combat,
  attacks, gear, features and allies, spellcasting, story, other
  proficiencies); a section that would make the file invalid is discarded.
- Level-up and edit show every change (old -> new) before saving, keep the
  previous file as `<id>.yaml.bak`, and never touch `state/`.
- **Opt-in SRD lookups** when creating (`--online`): class (hit die, saving
  throws, subclasses, level 1 features), species and subspecies traits, and
  class-limited spell pickers, from the free SRD via the Open5e API
  (`srd-2014` / `srd-2024`, CC BY 4.0 credit included).
- **`?` rules links** beside each condition and SRD spell on the sheet, opening
  the rule text in a new tab for the character's own edition. The text is
  bundled in `rules/*.json` (rebuild with `scripts/build_rules.py`), so the app
  makes no network calls; the links do not print.
- **Character file validation** (`character_schema.py`): a file with problems
  shows a "needs fixing" page naming each wrong field instead of a 500, and
  never breaks the other characters.
- Optional `gender` and `faith` in `appearance`; `treasure` is a bulleted list.
- Multiclass support in the script (per-class prompts, combined hit dice,
  proficiency bonus from total level).
- Import-friendly fields: skill `prof` may be `"expertise"`, attacks take
  `notes`, and `edition` (`"2014"` or `"2024"`) relabels Race as Species.

### Changed
- `scripts/new_character.py` is now `scripts/character.py`; its prompts are
  friendlier for non-coders (quick or detailed, edition first with the matching
  D&D Beyond guide link, forgiving names, re-asking on typos, Ctrl+C).
- All running text on the sheet uses one 12pt size (`--text-size`).
- The sheet fits phone-width screens (360 to 430px) without overflow.
- gunicorn 26.2.0; Black 26.10.1 and other dependency updates.
- Character pages and the list are sent `Cache-Control: no-store`.
- Only `linux/amd64` images are published (arm64 dropped).
- CI: lint and tests are one job with pip and Docker layer caching.

### Fixed
- Save Changes and the rest buttons returned 403 on the live site
  (`Referrer-Policy` is now `same-origin`).
- In the PDF, the Armor Class, Initiative and Speed labels could land on a
  different page from their values on long sheets.

### Security
- pip removed from the image, clearing four vendored-library findings.
- Rules file paths are built only from known names (CodeQL path alerts).
- A `.dockerignore` keeps real characters out of locally built images.

## [1.3.1] - 2026-09-30

No user-facing change.

### Changed
- `app.py` and the character script follow the project's code standards (one
  job per function, private helpers), enforced by flake8 complexity and a
  standards test.
- Front end: inline styles removed and `unsafe-inline` dropped from the CSP;
  static assets are cache-busted and immutable; `/favicon.ico` answers 204.
- Test suite brought to 100% line and branch coverage, enforced in CI.

### Security
- Host-header allowlist against DNS rebinding (`CODEX_ALLOWED_HOSTS`).
- Server-side clamping of HP, hit dice, slots and currency; PDF concurrency cap;
  extra response headers; hash-pinned lock files; Dependabot for pip, Docker and
  Actions.

## [1.3.0] - 2026-09-30

### Added
- **Long Rest** and **Short Rest** buttons that apply pending edits first, then
  restore HP, slots, hit dice and exhaustion by the rules.
- **Exhaustion tracker** (levels 0 to 6) showing the effect at the current level.
- **Server-side PDF export** (`/characters/<id>/pdf`) so margins match in every
  browser.

## [1.2.0] - 2026-09-29

### Added
- **Condition chips** (poisoned, prone, stunned, and so on) on the sheet.
- **Concentration tracker**, tap-adjustable spell slots and hit dice, and a
  death-save banner (STABILIZED or DEAD).
- A **Getting Started guide** (`/guide`) for new players.
- A container healthcheck.

### Security
- Hardening pass alongside the release (see the roadmap).

## [1.1.3] - 2026-09-28

### Added
- A scheduled cleanup of stale images in the container registry.

### Fixed
- A literal `&nbsp;` showed on the Spellcasting page.
- Printing scattered content across pages; Hit Points landed on page 2.

## [1.1.2] - 2026-09-18

### Security
- CVE fixes.

## [1.1.1] - 2026-09-18

### Fixed
- Important values were hard to read on the mobile layout.

## [1.1.0] - 2026-09-09

### Added
- **HP by delta:** "Damage taken" and "Healing received" fields that adjust
  current HP instead of retyping the total.
- Python 3.14 and an automated test framework.

## [1.0.3] - 2026-09-04

### Changed
- Maintenance updates.

## [1.0.2] - 2026-09-04

### Changed
- GitHub Actions pins bumped; the Docker base image is pinned by digest.

## [1.0.1] - 2026-09-04

### Added
- The version is shown on the app's pages; image publishing is documented.

### Changed
- Workflows migrated to Python where it helped.

## [1.0.0] - 2026-09-04

### Added
- First tagged release: GitHub Actions workflows that build and publish the
  character sheet app's container image.
