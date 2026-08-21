# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repo is mostly D&D 5e campaign content (character sheets, dungeon notes, guides) plus one real software project: **statling**, a Python tool that renders YAML character data into Markdown character sheets via Jinja2. All commands below are run from the `statling/` directory unless noted.

- `statling/` — the Python package (source of truth for all code work)
- `characters/` — YAML character data + the Markdown sheets rendered from it (repo root, not inside `statling/`)
- `guides/`, `dungeon/` — freeform campaign/worldbuilding notes, not consumed by any code

## Commands

Run from `statling/`:

```bash
pip install -e ".[dev]"     # dev install (also done automatically in the devcontainer)

make format                 # ruff format + ruff check --fix (default formatter)
make lint                   # ruff check
make type-check             # mypy .
make test                   # pytest -v
make check                  # ruff format --check + ruff check + mypy (fast pre-commit check)
make all                    # format, lint, type-check, test

# single test file/case (once tests exist)
pytest -v path/to/test_file.py::test_name
```

Traditional-tool equivalents (`make format-trad`, `make lint-trad`, `make check-trad` → black/isort/flake8) exist for compatibility but ruff is the default and preferred toolchain — use it unless asked otherwise.

Rendering a character sheet (the core functionality):

```bash
# from statling/, using the installed console script
statling ../characters/2014_elowen_turnerleaf.yaml -o output/test.md

# or without installing, as a module from the repo root
python -m statling.render characters/2014_elowen_turnerleaf.yaml -o output.md
```

Note the path difference: the console script and `make render-test` are meant to be run from inside `statling/` (paths are relative to `../characters`), while `python -m statling.render` from the repo root uses paths relative to the repo root.

## Architecture

The whole rendering pipeline is intentionally small and lives in two files:

- **`statling/render.py`** — everything: the `CharacterRenderer` class (loads YAML with `yaml.safe_load`, renders via a Jinja2 `Environment` configured with `trim_blocks`/`lstrip_blocks`) and the `main()` CLI entrypoint (registered as the `statling` console script in `pyproject.toml`, and re-exported through `statling/__main__.py` for `python -m statling.render`).
- **`statling/templates/*.j2`** — Jinja2 templates that receive the parsed YAML dict as top-level template variables (i.e. `character_data` is unpacked via `template.render(**character_data)`, so YAML keys like `name`, `ability_scores`, `skills` are referenced directly in templates, not via a wrapper object).

Data flow: YAML file → `yaml.safe_load` → dict → `template.render(**dict)` → Markdown string → stdout or file.

When adding a new template or extending the YAML schema, treat `characters/2014_elowen_turnerleaf.yaml` as the canonical example of the expected shape (ability scores, saving throws, skills, combat, weapons, features, equipment, personality, companion, appearance, advancement — see `statling/README.md` for the full field list). Templates are plain Jinja2 with no custom filters/globals registered, so new templates must only rely on builtin Jinja2 syntax and whatever the YAML provides directly.

Packaging: `statling` targets Python 3.10–3.14 (runtime deps: PyYAML, Jinja2), uses `setuptools` via `pyproject.toml`, and ships templates as package data (`statling = ["templates/*.j2", "py.typed"]`). Code style is enforced at 79-char line length (ruff/black/flake8/mypy configs all agree), and mypy runs in strict mode (`disallow_untyped_defs`, etc.) — new functions need full type annotations.
