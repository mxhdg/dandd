"""Enforces the project's code standards (see CLAUDE.md, "Code standards").

flake8's max-complexity (see .flake8) covers branching; this covers function
length and the leading-underscore rule, which flake8 has no built-in check for.
"""

import ast
from pathlib import Path

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


def _all_functions():
    return [(path, fn) for path in SOURCE_FILES for fn in _functions(path)]


def test_functions_are_private_unless_they_must_be_public():
    offenders = [
        f"{path.name}::{fn.name}"
        for path, fn in _all_functions()
        if not (
            fn.name.startswith("_") or fn.decorator_list or fn.name in ALLOWED_PUBLIC
        )
    ]
    assert not offenders, f"these should start with an underscore: {offenders}"


def test_functions_stay_short_enough_to_do_one_thing():
    offenders = [
        f"{path.name}::{fn.name} ({fn.end_lineno - fn.lineno + 1} lines)"
        for path, fn in _all_functions()
        if fn.end_lineno - fn.lineno + 1 > MAX_FUNCTION_LINES
    ]
    assert not offenders, (
        f"over {MAX_FUNCTION_LINES} lines; split into single-purpose helpers: "
        f"{offenders}"
    )


def test_test_functions_carry_no_decorators():
    # Cases are looped inside each test body; shared setup lives in conftest.py
    # fixtures. So no test_* function may be decorated (parametrize, skip, ...).
    tests_dir = Path(__file__).parent
    offenders = [
        f"{path.name}::{fn.name}"
        for path in sorted(tests_dir.glob("test_*.py"))
        for fn in _functions(path)
        if fn.name.startswith("test_") and fn.decorator_list
    ]
    assert not offenders, f"move decorator cases into the test body: {offenders}"
