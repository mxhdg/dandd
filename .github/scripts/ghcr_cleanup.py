"""Pick stale codex image versions in ghcr for deletion (see ghcr-cleanup.yml).

A published tag is an OCI index that points at untagged child manifests (the
platform image and its provenance/SBOM attestations), and cosign adds
`sha256-<digest>.sig` tags for the signature. Age and tags alone would delete
those children and break the tag, so every digest a kept tag reaches is kept
too. If a kept tag's manifest can't be read, nothing is deleted.
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

KEEP_TAG = re.compile(r"^(latest|v\d+\.\d+\.\d+.*)$")
COSIGN_TAG = re.compile(r"^sha256-([0-9a-f]{64})\.[a-z]+$")
MAX_AGE = timedelta(days=30)
_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def _tags(version):
    return version.get("metadata", {}).get("container", {}).get("tags", [])


def _is_kept_by_tag(version):
    return any(KEEP_TAG.match(tag) for tag in _tags(version))


def _cosign_target(version):
    """Digest a cosign `.sig`/`.att`/`.sbom` tag on this version belongs to."""
    for tag in _tags(version):
        match = COSIGN_TAG.match(tag)
        if match:
            return f"sha256:{match.group(1)}"
    return None


def _child_digests(manifest):
    return [m["digest"] for m in manifest.get("manifests", [])]


def _reachable(manifests_by_root):
    """Every digest a kept tag reaches: the roots and their children."""
    keep = set()
    for root, manifest in manifests_by_root.items():
        keep.add(root)
        keep.update(_child_digests(manifest))
    return keep


def _stale_ids(versions, keep_digests, now):
    cutoff = now - MAX_AGE
    stale = []
    for version in versions:
        created = datetime.fromisoformat(version["created_at"].replace("Z", "+00:00"))
        if created >= cutoff or _is_kept_by_tag(version):
            continue
        if version["name"] in keep_digests:
            continue
        if _cosign_target(version) in keep_digests:
            continue
        stale.append(str(version["id"]))
    return stale


def _registry_token(repository):
    request = urllib.request.Request(
        f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repository}:pull"
    )
    if os.environ.get("GH_TOKEN"):
        credentials = f"{os.environ['OWNER']}:{os.environ['GH_TOKEN']}".encode()
        request.add_header("Authorization", "Basic " + base64.b64encode(credentials).decode())
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["token"]


def _fetch_manifest(repository, token, digest):
    """The manifest JSON, or {} when the registry no longer has it (404)."""
    request = urllib.request.Request(
        f"https://ghcr.io/v2/{repository}/manifests/{digest}",
        headers={"Authorization": f"Bearer {token}", "Accept": _ACCEPT},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise


def _list_versions(owner, package):
    result = subprocess.run(
        ["gh", "api", "--paginate", f"/users/{owner}/packages/container/{package}/versions", "--jq", ".[]"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def main():
    owner = os.environ["OWNER"]
    package = "dandd%2Fcodex"
    repository = f"{owner}/dandd/codex"
    versions = _list_versions(owner, package)
    token = _registry_token(repository)
    roots = [v["name"] for v in versions if _is_kept_by_tag(v)]
    manifests = {d: _fetch_manifest(repository, token, d) for d in roots}
    keep = _reachable(manifests)
    stale = _stale_ids(versions, keep, datetime.now(timezone.utc))
    print(f"{len(versions)} versions, {len(roots)} kept by tag, {len(keep)} digests protected")
    print(f"{len(stale)} stale: {','.join(stale) or '-'}")
    if "--dry-run" in sys.argv:
        return
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        fh.write(f"ids={','.join(stale)}\n")


if __name__ == "__main__":
    main()
