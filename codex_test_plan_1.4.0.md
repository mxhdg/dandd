# codex 1.4.0 manual test plan

Run by hand against the dev stack before opening the 1.4.x PR. Automated tests
already cover the logic (278 tests, 100% coverage); this plan covers what they
cannot: how it looks and feels on your real devices, your real character files,
and the live deploy. Tick each box; write what you saw under **Notes** if it
differs from **Expect**. About 50 minutes in total.

Version under test: `1.4.0-rc9` (check `codex/pyproject.toml`).

## 0. Setup (5 min)

- [ ] Back up your real data: `cp -r ~/source/dandd/codex/data /tmp/data-backup`
- [ ] Rebuild and start the dev stack: `cd ~/source/dandd/codex && docker compose -f docker-compose.dev.yml up -d --build`
- [ ] Open `http://192.168.40.31:8890`. The footer shows `dev` or the rc9 version and the list loads.
- [ ] For every script test below, use throwaway names starting with `zz_` and delete them at the end (section 7). Never run the script's level-up or edit against a real character without a copy.

## 1. Sheet, list and PDF (10 min)

| # | Do | Expect |
|---|---|---|
| 1.1 | Open the list page | Marigold, Hazel, Elowen (and the sample) listed; no "needs fixing" flags |
| 1.2 | Open each real character's sheet | All load; nothing looks different except the new `?` links |
| 1.3 | Marigold's PDF: `/characters/2014_marigold_kettlewick/pdf` | 6 pages; Armor Class, Initiative and Speed labels are on the same page as their values (page 2) |
| 1.4 | Hazel's PDF and the sample's PDF | Render normally; no `?` marks in the PDF |
| 1.5 | Ctrl+P (browser print preview) on a sheet | No `?` links in the preview; page layout unchanged |
| 1.6 | On a sheet, tick two conditions and type an HP value (do not save), then tap a `?` | The rules open in a **new tab**; the sheet tab still has your unsaved edits |
| 1.7 | Hazel's sheet: page 2 (appearance) | Shows Gender/Faith only if set; nothing extra when blank |
| 1.8 | Treasure box on a sheet | Header is just "Treasure"; items are a bulleted list (a legacy single item shows as a bold name plus text) |

Notes:

## 2. The `?` rules links (8 min)

- [ ] **Hazel (2024):** tap `?` on Poisoned. Wording starts "While you have the Poisoned condition…" (2024).
- [ ] **Marigold (2014):** tap `?` on Poisoned. Short 2014 wording ("A poisoned creature has disadvantage…").
- [ ] **Exhaustion:** the `?` beside the Exhaustion selector opens its rule text; the existing per-level effects list still shows on the sheet.
- [ ] **Spellcasting page:** `?` appears beside SRD spells (Magic Missile, Shield, Scorching Ray, Ice Knife) in cantrips, prepared and always-prepared lists. Spells outside the SRD (for example Mind Spike, Melf's Acid Arrow) have **no** `?`.
- [ ] A spell page shows level and school, casting time, range, components, duration, classes, text, and "At higher levels" where it applies.
- [ ] Every rules page ends with the SRD credit ("This work includes material from the System Reference Document…") and a Back to characters link.
- [ ] **Phone (your iPhone):** `?` is easy to tap, the condition chips wrap without anything cut off, no sideways scrolling, rules pages read well.
- [ ] `/rules/2014/conditions/nope` and `/rules/2019/spells/light` give a plain 404, not an error trace.

Notes:

## 3. Character file checks (5 min)

- [ ] Copy a real file: `cp data/hazel_briar.yaml data/zz_broken.yaml`. Edit it: change `hp: max:` to `ten` (text) and set `edition: 2024` **without** quotes.
- [ ] Refresh the list: it shows `zz_broken` marked "needs fixing (2)"; every other character still opens.
- [ ] Open `/characters/zz_broken`: a page names `zz_broken.yaml` and both fields with "expected … found …". The PDF and Save routes for it also refuse cleanly.
- [ ] Break the YAML syntax instead (add an unclosed `[`): the page says "not valid YAML" and the list still loads.
- [ ] Fix or delete the file; it loads (or disappears) again.

Notes:

## 4. The script: creating (15 min)

Run from `codex/` as `python scripts/character.py`. Ctrl+C at any prompt must print "Cancelled. Nothing was saved."

- [ ] **Menu and flags:** with no flag it asks New / level-up / edit (N/L/E, Enter = new). `--new`, `--level-up` and `--edit` skip that question. Combining two of them is rejected.
- [ ] **Quick create** (`--new`, name `zz_quick`): edition is asked first, then the matching D&D Beyond guide link prints (2014 vs 2024 differ), then "Quick or detailed (Q/D) [quick]". Result opens in the app with no "needs fixing".
- [ ] **Prompts read clearly:** Features, Attacks and Allies show the explanation and an example entry; Treasure asks "one item per line"; a typo in a skill or ability name is explained and re-asked; a non-number at a number prompt is re-asked.
- [ ] **Detailed create with SRD** (`--new --online`, name `zz_wizard`, 2014): `wiz` finds Wizard and shows "From the SRD"; `evoc` finds the subclass; `elf` then offers High Elf; saving throws are pre-selected; the level 1 features are offered ("Add all?"); spell prompts accept `fire` for Fire Bolt; the CC BY credit prints at the end.
- [ ] **2024 variant:** repeat with edition 2024 (species wording, 2024 classes).
- [ ] **Offline fallback:** turn off the network (or Wi-Fi) and run with `--online`: it says it could not use the SRD and carries on with plain typing.
- [ ] **Without `--online`:** answering **N** to the SRD question makes no network request and the flow is the same as before.

Notes:

## 5. The script: level-up and edit (10 min)

Always on a **copy**: `cp data/hazel_briar.yaml data/zz_hazel.yaml`.

Level-up (`--level-up zz_hazel`):
- [ ] The class menu lists her class and "a new class (multiclass)".
- [ ] Hit points: Enter uses the average; a typed roll is used; the preview shows `hp.max` going up.
- [ ] ASI at level 4/8/12/16/19 is suggested. Raising a score already at 20 changes nothing (capped).
- [ ] The preview lists every changed field as old -> new, plus "Check:" warnings (attack bonuses, AC if Dexterity changed).
- [ ] Declining at "Save these changes?" leaves the file untouched (`cmp` with the original). Accepting writes it and creates `zz_hazel.yaml.bak` equal to the original.
- [ ] `state/` is never touched (check `state/zz_hazel.yaml` is unchanged or absent).
- [ ] The result opens in the app, `/pdf` works, and nothing says "needs fixing".

Edit (`--edit zz_hazel`):
- [ ] The nine-section menu appears; each prompt shows the current value; Enter keeps it and `-` clears it.
- [ ] Open "Ability scores and proficiencies", press Enter through everything: **"No changes were made."** and no file written.
- [ ] Change AC and add one equipment item: the preview shows exactly those; saving writes a `.bak`.
- [ ] Clear the Name with `-`: that section is rejected with the reason and your other edits remain.
- [ ] `--level-up` / `--edit` with no ID list your characters to pick from; a wrong ID lists what exists.

Notes:

## 6. Container and CI (10 min)

- [ ] `docker logs codex-dev 2>&1 | grep -i -E "error|traceback"` prints nothing (no "Control server error").
- [ ] `docker exec codex-dev python -m pip --version` fails with "No module named pip".
- [ ] `docker ps` shows `codex-dev` as `healthy`.
- [ ] Push the branch and open the single 1.4.x PR into `main`. Expect green: `codex tests` (check job + docker smoke test) and `require-version-bump`. A PR touching only docs starts none of them.
- [ ] After the final bump to plain `1.4.0`, merge, run the `Cut a release` workflow, and confirm the image build finishes (amd64 only, faster than before) and the tag is `v1.4.0`.
- [ ] Update the `codex-prod` stack to the new image, then repeat 1.1, 1.2 and 2 (first two bullets) against the live site, including on your phone.

Notes:

## 7. Clean up

- [ ] `rm -f data/zz_* data/*.bak state/zz_*`
- [ ] `git status` shows no stray character files; real characters are unchanged (`diff -r data /tmp/data-backup`).
- [ ] Close or delete leftover test containers: `docker ps` and `docker rm -f` anything you started by hand.

## Known limits (not bugs)

- Level-up and edit rewrite the file, so YAML comments in it are dropped (the script warns first); the `.bak` keeps the original.
- Attack bonuses, damage and Armor Class are flagged for review, not recalculated.
- Spell slot counts are typed in by hand.
- The 2024 Greater Invisibility has no upstream text, so it has no `?` link.
- Real devices differ from Chromium emulation: anything odd on your iPhone is worth reporting even if the desktop looks right.

## Result

- Date run:
- Version / commit:
- Passed all sections? yes / no
- Issues found (section number and what you saw):
