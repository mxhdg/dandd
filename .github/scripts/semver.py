"""SemVer 2.0.0 parsing and precedence comparison, shared by the sheet-app
version-bump and release workflows (see semver.org for the spec this follows).
"""

import re

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<buildmetadata>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def parse(version):
    match = _SEMVER_RE.fullmatch(version)
    return match.groupdict() if match else None


def _prerelease_identifier_key(identifier):
    return (0, int(identifier)) if identifier.isdigit() else (1, identifier)


def precedence_key(version):
    """Sort key implementing SemVer precedence (build metadata is ignored)."""
    parsed = parse(version)
    if parsed is None:
        raise ValueError(f"not a valid SemVer 2.0.0 version: {version!r}")
    core = (int(parsed["major"]), int(parsed["minor"]), int(parsed["patch"]))
    prerelease = parsed["prerelease"]
    if prerelease is None:
        return (core, 1, [])
    identifiers = [_prerelease_identifier_key(p) for p in prerelease.split(".")]
    return (core, 0, identifiers)
