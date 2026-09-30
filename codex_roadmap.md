# Character Sheet App: Enhancement Ideas

This is a running list of ideas for `codex/`, gathered from an actual-play
perspective rather than a generic software backlog. It's not a commitment or
a schedule, just a place to park ideas between sessions and pull from
opportunistically.

Grouped below into candidate minor releases (current prod version: 1.2.0),
ordered by actual-play pain within each group: how much a mistake or
friction point it causes at the table right now, not by how easy it'd be to
build. Group boundaries and version numbers are a rough planning aid, not a
committed schedule; re-shuffle freely as actual play surfaces new pain
points.

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
  Points landed on page 2 instead of page 1). See item 17 under 1.6.0 for
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

## 1.3.0 — Rest & recovery bookkeeping

6. **Long Rest button**: resets HP to max, clears temp HP, restores all
   spell slots, resets hit dice used to half, clears one level of
   exhaustion. Right now all of this is manual, field by field, which is
   exactly the kind of bookkeeping that gets rushed or skipped when
   everyone's ready to stop for the night.
7. **Short Rest button**: prompts for hit dice spent, adds the rolled
   healing, decrements hit dice remaining.
8. **Exhaustion level tracker (0-6)** with the effect at the current level
   shown inline. Exhaustion is one of the most commonly misremembered rules
   at most tables, though it comes up less often than the items above.

## 1.4.0 — DM session tools

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

## 1.5.0 — Multi-character & session history

13. **Character switcher** on the sheet page itself (dropdown or tab strip)
    instead of going back to the list. Useful once more than one or two
    characters are in the app.
14. **Session snapshots**: a way to save a dated copy of a character's state
    at the end of a session, so there's an actual record of HP/inventory/XP
    over time instead of relying on memory of where things were left off.

## 1.6.0 — Polish & convenience

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
19. **Make the Trivy image scan blocking** in `codex-image.yml` for
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

## 1.7.0 — Character creation tooling

Separate from actual-play pain entirely; touches `new_character.py`, not
the live sheet.

23. **Edit-existing-character mode in `new_character.py`**, alongside the
    current `skeleton`/`full` creation modes: point it at an existing
    `data/<id>.yaml`, walk through the same prompts pre-filled with that
    character's current values, and write the result back. Right now
    leveling up or any other build change to a real character means
    hand-editing the YAML directly; a guided edit mode would keep the same
    validation/derived-value computation (modifiers, DC, passive
    perception) that creation already gets, instead of that only applying
    the first time a character is made.
24. **API-guided character creation in `new_character.py`**, sourcing race/
    class/background/equipment/spell lists from the Open5e API
    (`api.open5e.com`) instead of the user typing everything freehand.
    Must be opt-in (e.g. a prompt or flag before any network call), never
    the default path, so `new_character.py` still works fully offline for
    anyone who doesn't want it hitting an external API. Chosen over
    broader-but-riskier sources (e.g. 5etools' data mirrors) because Open5e
    only serves SRD/OGL-licensed content, keeping the app's licensing clean;
    requires adding an OGL Section 15 attribution notice somewhere in the
    app (footer or a `/license` page) as a condition of using that content.
    Content outside the SRD (some subclasses/spells) would still need to be
    hand-authored the way campaign repos already handle original stat
    blocks (e.g. `TheChillBeneaththeCrust/arc-vanilla-vault/monsters.md`).
25. **Rules-content lookup** for spells/features/conditions on the live
    sheet (e.g. tap "Poisoned" and see what it actually does, rather than
    just a toggle label). Same SRD/OGL licensing path as item 24's Open5e
    API idea above — could plausibly share that same content source
    rather than being a separate integration. Display only; explicitly not
    a step toward automated dice rolling, which stays out of scope per
    "Explicitly not planned right now" below.

## Unscoped ideas

Parked here because there's not enough shape yet to slot into a version
group above.

- **DM campaign-level tooling.** Some way for the DM to use `codex/` across
  a whole campaign, not just one character's sheet at a time — exact shape
  still TBD (a dashboard tying into a campaign repo like
  `TheChillBeneaththeCrust/`? cross-character campaign state? something
  else?). Revisit once there's a concrete at-the-table pain point to design
  against, same as everything else on this list.

## Explicitly not planned right now

- **Full user accounts/authentication.** Deferred deliberately (see the
  security hardening already done in `codex/`); revisit only if this
  ever needs to run somewhere less trusted than a home network.
- **Automated dice rolling as a full replacement for physical dice.** Only
  worth building if the table actually wants it; this would change the feel
  of a session more than anything else on this list.
