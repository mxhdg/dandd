"""Keeps CHANGELOG.md in step with the version in pyproject.toml."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
HEADING = re.compile(
    r"^## \[(\d+)\.(\d+)\.(\d+)\] - (\d{4}-\d{2}-\d{2}|unreleased)$", re.M
)
SECTIONS = {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}


def _version():
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def _entries():
    return [
        (tuple(int(n) for n in m.groups()[:3]), m.group(4))
        for m in HEADING.finditer(CHANGELOG)
    ]


def test_the_current_version_has_a_changelog_entry():
    base = tuple(int(n) for n in re.match(r"(\d+)\.(\d+)\.(\d+)", _version()).groups())
    assert base in [
        version for version, _ in _entries()
    ], f"add a '## [x.y.z] - date' entry for {_version()} to CHANGELOG.md"


def test_entries_are_newest_first_and_only_the_newest_may_be_unreleased():
    entries = _entries()
    versions = [version for version, _ in entries]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    dates = [date for _, date in entries]
    assert "unreleased" not in dates[1:]
    released = [d for d in dates if d != "unreleased"]
    assert released == sorted(released, reverse=True)


def test_changelog_only_uses_the_standard_section_names():
    used = set(re.findall(r"^### (.+)$", CHANGELOG, re.M))
    assert used <= SECTIONS, used - SECTIONS
