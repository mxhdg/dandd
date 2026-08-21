# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repo is a personal D&D 5e campaign notebook. It contains no code, build system, or tests — only Markdown (and one YAML data file) documenting characters, dungeons, and homebrew guides. There is no `statling` package anymore: it was a Python YAML→Markdown character sheet renderer that lived here and has since been removed (see git history if you need the old implementation for reference).

There are no commands to build, lint, or test — treat this as a plain content/documentation repo.

## Structure

- `characters/` — character sheets. `2014_elowen_turnerleaf.yaml` is structured data (ability scores, saving throws, skills, combat, equipment, etc.) that was previously the input to the now-removed renderer; the `.md` files in this directory are the corresponding human-readable sheets (`2014_elowen_turnerleaf.md` and an older `elowen_turnerleaf.md`). Since there's no renderer, the YAML and Markdown versions are maintained independently — if you edit one to reflect a character change, update the other by hand to keep them in sync.
- `dungeon/` — session/dungeon-crawl prep notes (`dungeon.md`, `monsters.md`, `mtg_cards.md`, `temp.md`), including rules for integrating Magic: The Gathering booster-pack cards into encounters.
- `guides/` — standalone homebrew rules guides, e.g. `tarot_based_characters.md` (using tarot spreads/archetypes for character creation).

When editing content in this repo, match the existing Markdown conventions of the file you're in (e.g. the ASCII-art stat blocks in character sheets, the heading/section structure in dungeon prep docs) rather than introducing a new format.
