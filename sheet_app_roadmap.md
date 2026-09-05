# Character Sheet App: Enhancement Ideas

This is a running list of ideas for `sheet-app/`, gathered from an actual-play
perspective rather than a generic software backlog. It's not a commitment or
a schedule, just a place to park ideas between sessions and pull from
opportunistically.

Ranked below by actual-play pain: how much a mistake or friction point it
causes at the table right now, not by how easy it'd be to build. Re-shuffle
freely as actual play surfaces new pain points.

1. **HP by delta, not by typing the new total.** A "Damage taken" / "Healing
   received" field that adds or subtracts from current HP. Combat is
   arithmetic under time pressure right now (subtract damage from current HP
   in your head, then type the result); a delta field removes the most common
   way to end up with the wrong number on the sheet.
2. **Condition tags** (poisoned, prone, stunned, grappled, restrained,
   frightened, etc.) as simple toggle chips on the sheet. These are exactly
   the kind of thing that gets forgotten three rounds after they're applied.
3. **Concentration tracker**: one field showing what spell is currently being
   concentrated on, so a Constitution save prompt after taking damage doesn't
   require flipping back through notes to remember what's at stake.
4. **+/- stepper buttons for spell slots used and hit dice used**, so a tap
   increments instead of having to clear and retype a number on a phone
   mid-turn.
5. **Death save status banner.** Once 3 successes or 3 failures are logged,
   show "STABILIZED" or "DEAD" clearly instead of leaving it as three
   checkboxes someone has to interpret in the moment.
6. **Long Rest button**: resets HP to max, clears temp HP, restores all spell
   slots, resets hit dice used to half, clears one level of exhaustion. Right
   now all of this is manual, field by field, which is exactly the kind of
   bookkeeping that gets rushed or skipped when everyone's ready to stop for
   the night.
7. **Short Rest button**: prompts for hit dice spent, adds the rolled
   healing, decrements hit dice remaining.
8. **Exhaustion level tracker (0-6)** with the effect at the current level
   shown inline. Exhaustion is one of the most commonly misremembered rules
   at most tables, though it comes up less often than the items above.
9. **Inline attack/damage roller** for weapons and cannon modes: tap "Light
   Crossbow" and get an attack roll plus damage roll without leaving the
   sheet. Worth asking the table about first, some groups want physical dice
   no matter what, and this one changes that.
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
13. **Monster/NPC stat block viewer**, pulling from `dungeon/monsters.md`, so
    the DM gets the same clean sheet treatment for monsters that players get
    for characters.
14. **Character switcher** on the sheet page itself (dropdown or tab strip)
    instead of going back to the list. Useful once more than one or two
    characters are in the app.
15. **Session snapshots**: a way to save a dated copy of a character's state
    at the end of a session, so there's an actual record of HP/inventory/XP
    over time instead of relying on memory of where things were left off.
16. **Print/PDF export button.** The sheet already visually matches the
    official layout, so this is mostly wiring up print CSS that's already
    most of the way there. Low pain today since the browser's own print
    dialog already covers this in a pinch.
17. **Lightweight per-character lock** (a PIN, not a full account system) so
    one player can't accidentally edit another's sheet mid-session. Doesn't
    need to be more than that unless there's an actual reason for real
    accounts later, and doesn't matter until more players share the app.
18. **Add to Home Screen support** (a small web manifest), so the sheet opens
    like an app icon on a phone instead of a bookmarked tab.

## Explicitly not planned right now

- **Full user accounts/authentication.** Deferred deliberately (see the
  security hardening already done in `sheet-app/`); revisit only if this
  ever needs to run somewhere less trusted than a home network.
- **Automated dice rolling as a full replacement for physical dice.** Only
  worth building if the table actually wants it; this would change the feel
  of a session more than anything else on this list.
