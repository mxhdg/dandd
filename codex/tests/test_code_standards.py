"""Enforces the project's code standards (see CLAUDE.md, "Code standards").

flake8's max-complexity (see .flake8) covers branching; this covers function
length and the leading-underscore rule, which flake8 has no built-in check for.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SOURCE_FILES = [ROOT / "app.py", ROOT / "scripts" / "new_character.py"]

# One job per function: if a function outgrows this, it is almost certainly
# doing more than one thing. Pure data tables (e.g. a defaults dict) are the
# only reason to be near the limit.
MAX_FUNCTION_LINES = 30

# Public by necessity: a script's entry point, and methods overriding a base
# class (WeasyPrint's URLFetcher.fetch). Flask routes and hooks are public too
# but are recognised by their decorator instead of being listed here.
ALLOWED_PUBLIC = {"main", "fetch"}


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def _cases():
    return [
        pytest.param(fn, id=f"{path.name}::{fn.name}")
        for path in SOURCE_FILES
        for fn in _functions(path)
    ]


@pytest.mark.parametrize("fn", _cases())
def test_function_is_private_unless_it_must_be_public(fn):
    is_registered = bool(fn.decorator_list)
    assert (
        fn.name.startswith("_") or is_registered or fn.name in ALLOWED_PUBLIC
    ), f"{fn.name} should start with an underscore"


@pytest.mark.parametrize("fn", _cases())
def test_function_stays_short_enough_to_do_one_thing(fn):
    length = fn.end_lineno - fn.lineno + 1
    assert length <= MAX_FUNCTION_LINES, (
        f"{fn.name} is {length} lines (max {MAX_FUNCTION_LINES}); "
        "split it into single-purpose helpers"
    )
