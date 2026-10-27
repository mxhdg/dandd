# Character Sheet App: Enhancement Ideas

This is a running list of ideas for `codex/`, gathered from an actual-play
perspective rather than a generic software backlog. It's not a commitment or
a schedule, just a place to park ideas between sessions and pull from
opportunistically.

Grouped below into candidate minor releases (current released version: 1.4.2),
ordered by actual-play pain within each group: how much a mistake or
friction point it causes at the table right now, not by how easy it'd be to
build. Group boundaries and version numbers are a rough planning aid, not a
committed schedule; re-shuffle freely as actual play surfaces new pain
points. One deliberate exception: character creation tooling (1.4.0) was
moved ahead of the DM session tools, by choice rather than by play pain.

## 1.1.0 (shipped)

- **DONE. HP by delta, not by typing the new total.** A "Damage taken" /
  "Healing received" field that adds or subtracts from current HP. Combat is
  arithmetic under time pressure right now (subtract damage from current HP
  in your head, then type the result); a delta field removes the most
  common way to end up with the wrong number on the sheet.

## 1.1.3 (shipped)

- **DONE. Fixed literal `&nbsp;` text shown on the Spellcasting page**
  (e.g. "Cantrips Known" rendered the entity name itself instead of a space
  between items). Jinja was auto-escaping the `&nbsp;` in the join
  separator instead of rendering it, since that output wasn't marked
  `|safe`. Found 2026-09 while verifying the print-layout fix below.
- **DONE. Fixed print layout scattering content across pages** (the
  3-column CSS grid couldn't fragment across a print page break, and Hit
  Points landed on page 2 instead of page 1). See item 17 under 1.7.0 for
  the remaining page-density follow-up.

## Known bugs (fix before new features)

Actual defects in shipped behavior, not feature gaps. These rank above
every group below regardless of playability impact, since they're wrong
output today rather than a missing capability. None currently tracked.

## 1.2.0 (shipped) — At-the-table combat clarity

The highest actual-play pain right now: things forgotten or fumbled
mid-combat.

1. **DONE. Condition tags** (poisoned, prone, stunned, grappled, restrained,
   frightened, etc.) as simple toggle chips on the sheet. These are exactly
   the kind of thing that gets forgotten three rounds after they're applied.
   Exhaustion excluded since it's its own 0-6 tracker under 1.3.0 below.
2. **DONE. Concentration tracker**: one field showing what spell is currently
   being concentrated on, so a Constitution save prompt after taking damage
   doesn't require flipping back through notes to remember what's at stake.
3. **DONE. Spell slots used / hit dice used are tap-adjustable**: the app has
   no JS (CSP blocks it), so this ships as the browser's native
   `<input type="number">` spinner rather than custom +/- buttons, with a
   larger touch target on mobile, instead of a full page reload per tap.
4. **DONE. Death save status banner.** Once 3 successes or 3 failures are
   logged, shows "STABILIZED" or "DEAD" clearly instead of leaving it as
   three checkboxes someone has to interpret in the moment.

Also riding along in this release, unrelated to actual-play pain (ops/
deployment reliability instead):

5. **DONE. Container healthcheck.** A Docker `HEALTHCHECK` (hitting the
   index route via stdlib `urllib`, no new package) so `docker ps`/
   orchestration tooling can see a hung or crashed app instead of a
   container that looks "up" but isn't actually serving requests.

Also added while shipping this release, not originally scoped above:

- **DONE. Getting Started guide**, linked from the character list
  (`/guide`), covering full app usage for a new reader (how editing/saving
  works with no JS, HP deltas, conditions, concentration, death saves,
  spell slots/hit dice, printing, mobile) rather than just the features
  added in this release.

## 1.3.0 (shipped) — Rest & recovery bookkeeping

6. **DONE. Long Rest button**:
   resets HP to max, clears temp HP and death saves, restores all spell
   slots, regains half your total hit dice (min 1, per 2014 PHB), clears one
   level of exhaustion. Right now all of this is manual, field by field, which is
   exactly the kind of bookkeeping that gets rushed or skipped when
   everyone's ready to stop for the night.
7. **DONE. Short Rest button**: prompts for hit dice spent, adds the rolled
   healing, decrements hit dice remaining.
8. **DONE. Exhaustion level tracker (0-6)** with the effect at the current level
   shown inline. Exhaustion is one of the most commonly misremembered rules
   at most tables, though it comes up less often than the items above.

## 1.3.1 (shipped) — Code standards, tests, efficiency, security

No user-facing change. Brings `app.py` and `scripts/character.py` in line
with the project's code standards (one responsibility per function,
`_`-prefixed private functions; see `CLAUDE.md`).

- **DONE. `app.py`**: extracted shared route lookup/origin/render helpers,
  split form parsing into one helper per field group, split saved-state
  reading from merging, split the PDF static-file check from the fetcher.
- **DONE. `character.py`**: split prompting from computation for
  abilities/saves/skills, per-section prompt helpers, spell-slot and
  comma-list helpers, and extracted character assembly out of `main()`.
  Verified byte-identical output against the old code for skeleton, full,
  and full-with-spellcasting runs.
- **DONE. Enforcement**, so the standards hold going forward: flake8
  `max-complexity = 6`, `isort --check` added to the CI lint job, and
  `tests/test_code_standards.py` (function length <= 30 lines, `_` prefix
  on every non-route/non-entry-point function).
- **DONE. Front-end efficiency**: removed all 27 inline `style=""`
  attributes (now classes) and dropped `unsafe-inline` from the CSP;
  cache-busted (`?v=mtime`), immutable static assets; template whitespace
  trimmed (sheet HTML about 6% smaller); `/favicon.ico` answers 204 instead
  of a 404 on every page. Verified pixel-identical on desktop, mobile,
  browser print and PDF. Not done: response compression (would need a new
  dependency for ~17 KB pages on a home LAN) and CSS minification (10 KB of
  CSS, and the repo deliberately has no build step).
- **DONE. Security hardening** from a full review: Host-header
  allowlist against DNS rebinding (`CODEX_ALLOWED_HOSTS`), escaped cantrip
  list (was `|safe` on raw data), server-side clamping of HP/hit dice/slots/
  currency, PDF concurrency cap, extra response headers, loopback-only dev
  server, `pids_limit` and `noexec` tmpfs, hash-pinned lock files
  (`pip-compile`) installed with `--require-hashes`, and Dependabot for pip,
  Docker, and Actions. Still open (needs a human): branch protection on
  `main` (GitHub setting), and whether to rewrite git history to drop the
  gitignored-since "howto" files from the public repo.
- **DONE. Top-to-bottom tests**: `character.py` unit tests (30% -> 100%
  coverage), integration journeys (a full play session, spellcasters,
  script-generated characters rendering in the app, security sweep,
  gunicorn config), tests converted to in-body loops with shared fixtures in
  `conftest.py`, and a 100% line+branch coverage gate enforced in CI.
- **DONE. Tests** for the newly testable pure helpers
  (`tests/test_character.py`).

## 1.4.0 (shipped) — Character creation tooling

Separate from actual-play pain entirely; touches `character.py`, not
the live sheet (item 25 is the one exception, a live-sheet lookup that shares
item 24's content source). Prioritized ahead of the DM tools.

**Suggested order:** 26 (schema validation) first, since 23 depends on it,
then 23 (edit/level-up mode), then 24 (Open5e-guided creation), then 25.

**Shipped as 1.4.0 (PR #24, 2026-10-16) after nine release candidates (items 23
to 37):** rc1 added
the import-friendly sheet fields, rc2 folded in the Dependabot updates, rc3
made sheet text uniform, rc4 fixed the 403 on Save/rest buttons, rc5 fit the
sheet on phones, rc6 added multiclass support, a friendlier `character.py`
and the treasure list, rc7 added schema validation (26), gunicorn 26 (28),
pip removal from the image (29) and the gender/faith fields (30), and rc8 added
`character.py` with level-up and the edit menu (23). rc9 added SRD-guided creation (24) and rules lookup on the sheet (25). The
theme's items are done; the rest of 29 (Debian findings, Trivy
version) is waiting on upstream.

23. **DONE (1.4.0-rc8): level-up and the edit menu.** The script
    is now `scripts/character.py` with `--new`, `--level-up [ID]` and an
    action question when no flag is given, and `--edit [ID]`, a nine-section
    menu (identity, abilities and proficiencies, combat, attacks, gear, features
    and allies, spells, story, other proficiencies) with the current value shown
    for every prompt, per-section validation (an invalid result is discarded),
    numbered remove-and-add list editing, and the same preview, backup and
    `state/` rules as level-up. Level-up: validates the file, picks the class (or a new one for
    multiclass), HP by roll or average plus CON (with a retroactive adjustment
    when the CON modifier changes), ASI or feat, new features, spell slots and
    spells by hand (no slot tables; item 24 could supply them), derived values
    shifted by the formula change so custom bonuses are kept, an old->new
    preview, `<id>.yaml.bak`, re-validation before writing, `state/` never
    touched. Not recalculated, only flagged: attack bonuses, damage, AC. Known
    gaps: YAML comments are dropped on rewrite (warned); only the standard ASI
    levels are suggested (4, 8, 12, 16, 19); list entries are edited by
    removing and re-adding, not in place. Original spec for the whole item
    follows.

    **Edit-existing-character mode in `character.py`**, alongside the
    current `skeleton`/`full` creation modes: point it at an existing
    `data/<id>.yaml`, walk through the same prompts pre-filled with that
    character's current values, and write the result back. Right now
    leveling up or any other build change to a real character means
    hand-editing the YAML directly; a guided edit mode would keep the same
    validation/derived-value computation (modifiers, DC, passive
    perception) that creation already gets, instead of that only applying
    the first time a character is made.

    **Level-up is the first-class flow within this mode**, not an
    afterthought: a dedicated `level-up` path that bumps class level and
    proficiency bonus, recomputes max HP (roll or average for the new hit
    die plus CON modifier), adds the hit die, prompts for new class
    features, ASI/feat at the right levels, and new spells known/prepared
    and slot counts, then recomputes every derived value. General edit mode
    (respec, new gear, backstory changes) builds on the same
    load/prefill/validate/write-back machinery, so design that machinery
    for level-up first and let the free-form edit mode reuse it. Level-up
    must only touch `data/<id>.yaml` (the static build), never
    `state/<id>.yaml`, though it should flag stale state (e.g. current HP
    above the new max is fine, but spell slots used beyond a changed slot
    count isn't). Multiclassing is the awkward case to decide up front
    whether to support. Depends on the schema validation in item 26: edit
    and level-up should validate before reading and before writing.
24. **DONE (1.4.0-rc9). SRD-guided character creation.** Built as `srd_lookup.py`
    plus `--online` / an opt-in question in `character.py`: class (hit die,
    saving throws, subclass names, level 1 features), species and subspecies
    (traits) and class-limited spell pickers, from the `srd-2014` / `srd-2024`
    documents of the Open5e v2 API only. Findings that changed the plan:
    Open5e v2 is not SRD-only (24 documents, mixed licenses), so the client
    filters to those two; the SRD licence is CC BY 4.0 (plus OGL 1.0a for
    2014), so the attribution is the CC text, in the guide and printed after a
    lookup; the API 403s the default Python User-Agent; the SRD documents have
    no conditions and only 1 (2014) or 4 (2024) backgrounds, so those are not
    looked up. Level-up and edit do not use it yet. Original spec follows.

    **API-guided character creation in `character.py`**, sourcing race/
    class/background/equipment/spell lists from the Open5e API
    (`api.open5e.com`) instead of the user typing everything freehand.
    Must be opt-in (e.g. a prompt or flag before any network call), never
    the default path, so `character.py` still works fully offline for
    anyone who doesn't want it hitting an external API. Chosen over
    broader-but-riskier sources (e.g. 5etools' data mirrors) because Open5e
    only serves SRD/OGL-licensed content, keeping the app's licensing clean;
    requires adding an OGL Section 15 attribution notice somewhere in the
    app (footer or a `/license` page) as a condition of using that content.
    Content outside the SRD (some subclasses/spells) would still need to be
    hand-authored the way campaign repos already handle original stat
    blocks (e.g. `TheChillBeneaththeCrust/arc-vanilla-vault/monsters.md`).
25. **DONE (1.4.0-rc9). Rules lookup on the sheet.** A `?` beside each condition and
    each SRD spell opens its text in a new tab, per the character's edition.
    Conditions came from Open5e's `core` document, which carries per-edition
    SRD wording (the plan's "no conditions in the SRD documents" worry only
    applied to the srd-* documents themselves). Text is bundled as JSON in
    `codex/rules/` (about 750 KB, built by `scripts/build_rules.py`) so the app
    never touches the network; entries with no upstream text (2024 Greater
    Invisibility) are skipped, so no dead links. Display only; features and
    items are not looked up. Checked in Chromium at 360, 375, 393 and 430px
    (no overflow), desktop, `/pdf` and the print rule. Original spec follows.

    **Rules-content lookup** (note from item 24's research: Open5e v2 has no
    conditions in the SRD documents, so a condition lookup would have to be
    bundled static text; spells and class/species features are available
    through `srd_lookup.py`) for spells/features/conditions on the live
    sheet (e.g. tap "Poisoned" and see what it actually does, rather than
    just a toggle label). Same SRD/OGL licensing path as item 24's Open5e
    API idea above — could plausibly share that same content source
    rather than being a separate integration. Display only; explicitly not
    a step toward automated dice rolling, which stays out of scope per
    "Explicitly not planned right now" below.
26. **DONE (1.4.0-rc7). Schema validation for `data/<id>.yaml`**, a prerequisite for item 23.
    Built as `codex/character_schema.py` (hand-written, table-driven, stdlib
    only; the `jsonschema` option was weighed and declined to keep the image's
    dependencies and scan surface small). Runs in the app (422 error page, list
    flag, other characters unaffected, YAML syntax errors included) and in pytest
    (sample, template, script output and constants cannot drift). Not yet wired
    into `character.py` edit mode (item 23, which does not exist yet); `state/<id>.yaml`
    validation is still unscheduled. Original spec follows.
    Define one schema (required keys, types, allowed values, e.g. ability
    scores as ints, proficiency lists as lists) and check every character
    file against it. Today `data/character_template.yaml.example` is the
    only definition of the format, and nothing enforces it. Where it runs:
    - `character.py` edit/level-up: validate on load and again before
      writing. On failure, list every problem (file, field path, expected
      vs. found), not just the first, and refuse to write a file that
      fails.
    - `app.py`: validate when loading a character. A failure shows a clear
      error naming the file and fields (on the index page and the sheet
      route) rather than a 500 or a half-rendered sheet, and one bad file
      must not break the other characters' listing.
    - `pytest`: a test that validates `sample_character.yaml` and the
      template, so schema and sample can't drift apart.
    Open decision: a JSON Schema checked with `jsonschema` (standard,
    declarative, but a new dependency) versus a small hand-rolled validator
    (no new dependency, matches the repo's stdlib-leaning approach). The
    same question applies to `state/<id>.yaml`, which is lower priority.

27. **DONE (1.4.0-rc1). Import-friendliness schema additions**, found while
    hand-converting a D&D Beyond (2024-rules) PDF sheet into
    `data/<id>.yaml`: (a) skill `prof` accepts `"expertise"` (doubles the
    proficiency bonus, shown as a ringed checkbox), (b) attacks take an
    optional `notes` string (extra Notes column only when used), (c) an
    optional `edition` field (`"2014"` default, `"2024"` labels "Race" as
    "Species"). `character.py` prompts for all three. Deferred, not
    done: per-spell details (time/range/components/duration/save) and
    limited-use trackers (1/Long Rest features, Staff charges, Portent dice).

28. **DONE (1.4.0-rc7). Revisit the gunicorn 26 upgrade.** Upgraded to 26.2.0 with
    `control_socket_disable = True` in `gunicorn.conf.py`; verified under the
    real restrictions (read-only root, `/tmp` noexec, all capabilities dropped,
    no-new-privileges): no startup error, `/`, the sheet and `/pdf` return 200,
    Save and the rest buttons succeed (302). The 26.x lock also drops the
    `packaging` dependency. Original problem report: held at 23.0.0 since rc2 (Dependabot PR #21). Under 26.2.0 the hardened container
    logs `Control server error: Permission denied: '/home/appuser'` at
    startup; the app still served requests, but the root filesystem is
    read-only and the new control socket tries to write to the home
    directory. Candidate fix, untested: `control_socket_disable = True` in
    `gunicorn.conf.py` (CLI `--no-control-socket`), or point the socket at
    `/tmp`. Verify under the real compose files (read-only root, `/tmp`
    `noexec`), not just a plain `docker run`, and check the 23 to 26 release
    notes for other breaking changes. Until then, close or ignore PR #21 so
    Dependabot stops reopening it.

29. **Image scan follow-ups (same pass as item 28). pip removal DONE (1.4.0-rc7); the rest is open.** From the
    `v1.4.0-rc2` Trivy scan (non-blocking, exit-code 0): 48 HIGH on Debian
    13.7, 4 HIGH in Python, 0 CRITICAL.
    - **DONE (1.4.0-rc7). Removed pip from the final image** (`pip uninstall -y pip` right after the
      hashed install; the Dockerfile comment is updated; the image's Python findings went 4 -> 0;
      verified: `/`, the sheet and `/pdf` return 200, the healthcheck is healthy; the local gate command
      now bootstraps pip with `ensurepip --user`). Original plan: (`pip uninstall -y pip` as the
      last build step, after the `--require-hashes` install). All 4 Python
      findings (msgpack 1.1.2, setuptools 70.3.0, urllib3 2.7.0 x2) are
      copies vendored inside the base image's pip 26.2.1, not the app's real
      dependencies, which all scan clean. Untested: confirm the app and
      `/pdf` still work, the smoke test passes, and the findings clear. Also
      update the Dockerfile comment that says the vendored msgpack can't be
      fixed.
    - **Debian findings: nothing to do yet.** None has a fixed version
      (util-linux's 4 CVEs repeat across about 11 sub-packages; also expat,
      ncurses, systemd/udev, libacl1, perl-base). All need mount/namespace
      privileges the non-root, cap-dropped container doesn't have. Re-scan
      after each base-image digest bump (Dependabot) and re-check then.
    - **Trivy is 5 minor versions behind** (0.70.0 vs 0.75.0 available). The
      version comes from the pinned `trivy-action` default, so it moves when
      Dependabot bumps the action; no manual change needed.

30. **DONE (1.4.0-rc7). Gender and faith character fields.** Found importing a D&D Beyond
    sheet, which has both in its header block; codex has neither, so for now
    they live as plain text in `additional_features`. Added optional `gender`
    and `faith` keys in the `appearance` block (page 2, so page 1's header and
    phone fit are untouched), shown on the sheet only when set. Touches the
    template, `character_template.yaml.example`, `character.py` prompts
    and the docs; a schema addition like item 27, so the same upgrade path
    (optional, existing character files keep working).

31. **DONE (1.4.0-rc2). Dependabot updates folded into the feature
    branch** instead of bumping each PR (they fail the version-bump check by
    design): base image digest, pyyaml 6.0.3, and the dev-tools group
    (flake8 7.4.1, isort 9.0.2 and friends). Lock files regenerated with
    `pip-compile` on Python 3.14 and the full gates re-run. gunicorn 26 was
    deliberately skipped (item 28).
32. **DONE (1.4.0-rc3). Uniform sheet text.** Traits rendered at 11px while
    ideals, bonds and flaws inherited 16px. All running text (values,
    features, tables, spell lists, inputs) now uses one `--text-size`
    custom property (12pt, the APA body size); labels, section titles and
    ability names stay deliberately smaller (an all-12pt trial of those was
    rejected as too tall). A test checks the four personality boxes share
    one markup.
33. **DONE (1.4.0-rc4). Fixed 403 on Save Changes and the rest buttons on
    the live site.** `Referrer-Policy: no-referrer` made Firefox and
    Chromium send `Origin: null` on form POSTs, so the same-origin check
    rejected every POST; it is now `same-origin` (still no referrer sent
    cross-site). Reproduced in both browsers before and fixed after.
    Deployment note found at the same time: the prod `state/` bind mount
    must be writable by the container user (UID 1000), or saves fail with a
    500.
34. **DONE (1.4.0-rc5). Sheet fits phone-width screens (iPhone 14 Pro,
    393px).** The single phone column was `1fr`, which grew to fit 12pt
    content and pushed tiles past the margin; it is now `minmax(0, 1fr)`.
    On phones the attack table shows Notes as a full-width line under each
    attack instead of a clipped fifth column, and "Damage/Type" wraps at the
    slash. Checked at 360, 375, 393 and 430px in Chromium emulation (real
    Safari untested). Also removed the original hand-built
    `characters/2014_marigold_kettlewick.{html,css}` and cleaned up the root
    `.gitignore`.

35. **DONE (1.4.0-rc6). Multiclass characters.** `character.py` prompts per
    class (name, level, subclass, hit die defaulted from the class name) and
    builds `class_level`, `hit_dice.total` (same-size dice merged) and the
    proficiency bonus from total level; the spellcasting prompt mentions
    multiple classes. The sheet already rendered these as free text.
    Not done: separate hit dice "Used" counts per die type, and per-class
    spell lists/slot tables (slots are entered by hand, one shared pool).

36. **DONE (1.4.0-rc6). Friendlier `character.py` for non-coders.** (Renamed from
    `new_character.py` in rc8, when the script also became the place for
    editing and levelling up; older items above keep the new name.)
    Welcome line and plain closing message; "quick or detailed" instead of
    `skeleton`/`full` (flags unchanged); no file-id prompt (derived from the
    name unless `--id`); case-insensitive and unique-prefix name matching;
    bad numbers and unrecognized names re-prompt instead of silently
    defaulting or dropping. Still a terminal script needing Python and
    PyYAML; a web form (item 24-style) was considered and deferred.

37. **DONE (1.4.0-rc6). Treasure is a list.** The sheet's header is a fixed
    "Treasure" and the box is a bulleted list of strings or `{name, text}`
    items, replacing the single titled box. `_treasure_items` normalizes the
    old `{title, text}` shape (title becomes the item name), so existing
    character files need no edits; `character.py` asks for one item per
    line.

## 1.4.1 (shipped) — Changelog

38. **DONE (1.4.1). `codex/CHANGELOG.md`.** A Keep a Changelog file
    back-filled from the git tags and this roadmap (1.0.0 to 1.4.0), with an
    entry for each new version added in the same change that makes it. A
    test (`tests/test_changelog.py`) fails if the current version has no
    entry, if entries are out of order, or if a section name is non-standard.
    Not done: showing the changelog inside the app (a `/changelog` page).

## 1.4.2 (shipped) — Dependency security patch

39. **DONE (1.4.2). Pillow 13.0.0 and Brotli 1.2.1.** Folded Dependabot PRs
    #29 and #30 into one branch (they fail the version-bump check by design),
    clearing 30 open alerts (28 Pillow, 1 Brotli; several critical). Both come
    in through WeasyPrint for the PDF route; the app opens no user-uploaded
    images, so real exposure was low. Gates re-run on Python 3.14 unchanged.
    Process change: the changelog date is now set in the final bump PR into
    `main` (released the same day), so no follow-up PR is needed.

## 1.5.0 — DM session tools

DM-facing prep/mid-session pain that exists right now regardless of party
size, unlike the party-overview/initiative items below which explicitly
wait on more characters being in the app.

9. **Monster/NPC stat block viewer**, pulling from a campaign repo's
   `monsters.md` (e.g. `TheChillBeneaththeCrust/arc-vanilla-vault/monsters.md`),
   so the DM gets the same clean sheet treatment for monsters that players
   get for characters.
10. **Session notes field per character**: a scratchpad for things like
   "already used Lucky reroll this fight" or loot/plot reminders that don't
   belong on the permanent sheet.
11. **Party overview page**: one screen showing every character's current
    HP/AC/conditions at a glance, so the DM isn't clicking through separate
    sheets mid-combat. Bigger payoff once more than one character is in the
    app; only Marigold is wired in today.
12. **Initiative tracker** tied to the party overview. Juggling initiative
    order on paper is one of the most common things to fumble at the table,
    but like the party overview, the payoff scales with party size.
40. **DONE (1.5.0-rc1). Level-up ability prompt reads clumsily.** Found in the 1.4.0 test plan
    walkthrough: the prompt shows two parentheticals back to back, "(one name
    = +2, two names = +1 each) (comma-separated, e.g. Charisma, Constitution;
    blank for none)". `_ask_asi_abilities` builds the first half and
    `_ask_names` appends the second. Merge them into one line, and update any
    test that matches the prompt text.

## 1.6.0 — Multi-character & session history

13. **Character switcher** on the sheet page itself (dropdown or tab strip)
    instead of going back to the list. Useful once more than one or two
    characters are in the app.
14. **Session snapshots**: a way to save a dated copy of a character's state
    at the end of a session, so there's an actual record of HP/inventory/XP
    over time instead of relying on memory of where things were left off.

## 1.7.0 — Polish & convenience

Lower urgency: preference-driven or already partially covered by an
existing workaround.

15. **Inline attack/damage roller** for weapons and cannon modes: tap "Light
    Crossbow" and get an attack roll plus damage roll without leaving the
    sheet. This is a table-preference change, not a friction fix, worth
    asking the table about first since some groups want physical dice no
    matter what.
16. **Print/PDF export button.** The sheet already visually matches the
    official layout, so this is mostly wiring up print CSS that's already
    most of the way there. Low pain today since the browser's own print
    dialog already covers this in a pinch.
17. **Further optimize the print layout for page count/density.** The
    2026-09 pagination fix (single-column print flow instead of the
    3-column CSS grid, which browsers can't fragment across a page break;
    reordering columns so Hit Points lands on page 1 instead of the long
    abilities/skills column pushing it to page 2; wrapping ability score
    boxes into a compact row instead of each spanning the full page width)
    fixed the worst breakage and wasted space, but the print output still
    isn't tightly packed — more pages than strictly necessary, uneven
    whitespace per page. Revisit with more time to explore a denser
    print-only layout (e.g. CSS multi-column, or hand-tuned per-section
    widths) without reintroducing the grid-fragmentation bug it just fixed.
18. **Lightweight per-character lock** (a PIN, not a full account system) so
    one player can't accidentally edit another's sheet mid-session. Doesn't
    need to be more than that unless there's an actual reason for real
    accounts later, and doesn't matter until more players share the app.
    Separate concern from the CSRF/CSP hardening done 2026-09 — this is
    about accidental cross-edits between trusted players, not a hostile
    request forgery.
19. **PARTLY DONE: make the Trivy image scan blocking** (the weekly scheduled run now fails on fixable CRITICALs; release builds stay report-only) in `codex-image.yml` for
    HIGH/CRITICAL findings, instead of the current non-blocking report-only
    scan. Right now a real CVE in a future base-image bump ships silently;
    low urgency since a home-LAN app isn't a high-value target, but cheap
    to tighten once noticed.
20. **Add to Home Screen support** (a small web manifest), so the sheet
    opens like an app icon on a phone instead of a bookmarked tab.
21. **Derived stats from equipment** (encumbrance, AC changing with
    equipped armor) instead of everything being hand-typed into
    `data/<id>.yaml`. Would need the equipment list to become structured
    entries (weight, armor type, an equipped flag) rather than the current
    plain list of strings — a data-model change, not just a display one.
22. **Selectable color themes.** Right now the parchment/red palette is
    the only option (`--red`/`--parchment`/`--paper`/`--ink`/`--rule`
    custom properties in `character_sheet.css`, already centralized
    enough to swap). Exact shape TBD — per-character preference stored in
    `data/<id>.yaml`? a query param? something else? — and how it should
    interact with the existing `@media print` override, which already
    repurposes those same variables for black-on-white output.

## Unscoped ideas

Parked here because there's not enough shape yet to slot into a version
group above.

- **DM campaign-level tooling.** Some way for the DM to use `codex/` across
  a whole campaign, not just one character's sheet at a time — exact shape
  still TBD (a dashboard tying into a campaign repo like
  `TheChillBeneaththeCrust/`? cross-character campaign state? something
  else?). Revisit once there's a concrete at-the-table pain point to design
  against, same as everything else on this list.

- **SRD lookups beyond creation (follow-ups to 1.4.0 items 24 and 25).**
  Level-up and edit still take spells and features by typing; they could use
  the same SRD pickers (and the class tables in the SRD data could replace the
  hand-typed spell slot counts). The sheet's `?` links cover conditions and
  spells only; class and species features, and items, are not looked up.
- **Repo housekeeping from the 1.4.0 security review.** Make `check`,
  `docker-smoke-test`, `check-version-bump` and `CodeQL` required status
  checks on the `main` ruleset (it already requires PRs and blocks force-push
  and deletion); set Actions to enforce SHA pinning; re-scan the Debian base
  findings (49 HIGH, none with a fix) at the next base-image bump.

## Explicitly not planned right now

- **Full user accounts/authentication.** Deferred deliberately (see the
  security hardening already done in `codex/`); revisit only if this
  ever needs to run somewhere less trusted than a home network.
- **Automated dice rolling as a full replacement for physical dice.** Only
  worth building if the table actually wants it; this would change the feel
  of a session more than anything else on this list.
