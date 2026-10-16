#!/usr/bin/env python3
"""Rebuild the bundled rules text in rules/ from the free SRD (maintainer tool).

    python scripts/build_rules.py [--refresh]

Downloads the standard conditions and every spell for both rules editions
(srd-2014, srd-2024) from the Open5e API, and writes rules/spells-<edition>.json
and rules/conditions-<edition>.json. The sheet's "?" links read those files, so
the running app never needs the network. Commit the result; rerun when you want
fresh text. --refresh ignores the 30-day download cache.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # srd_lookup.py
from srd_lookup import (  # noqa: E402
    ATTRIBUTION,
    DOCUMENTS,
    SrdUnavailable,
    load_conditions,
    load_spell_details,
)

RULES_DIR = Path(__file__).parent.parent / "rules"


def _write_bundle(kind, edition, entries):
    path = RULES_DIR / f"{kind}-{edition}.json"
    bundle = {"edition": edition, "attribution": ATTRIBUTION, "entries": entries}
    RULES_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(bundle, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return path


def _with_text(entries, kind, edition):
    """Entries that have rule text; a page with nothing on it is not worth a link."""
    kept = [entry for entry in entries if entry["text"].strip()]
    for entry in entries:
        if entry not in kept:
            print(f"  skipped {kind} {entry['name']} ({edition}): the SRD has no text")
    return kept


def _build_edition(edition, refresh):
    conditions = _with_text(load_conditions(edition, refresh), "condition", edition)
    spells = _with_text(load_spell_details(edition, refresh), "spell", edition)
    _write_bundle("conditions", edition, conditions)
    _write_bundle("spells", edition, spells)
    print(f"{edition}: {len(conditions)} conditions, {len(spells)} spells")


def _parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--refresh", action="store_true", help="ignore the 30-day download cache"
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    try:
        for edition in DOCUMENTS:
            _build_edition(edition, args.refresh)
    except SrdUnavailable as err:
        print(f"Could not build the rules files: {err}")
        sys.exit(1)
    print(f"Wrote {RULES_DIR}. Review and commit the changes.")


if __name__ == "__main__":
    main()
