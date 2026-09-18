#!/usr/bin/env python3
"""Build a verified manifest for the dinkster-aimdo native wheel matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

WHEEL_PATTERN = re.compile(
    r"^dinkster_aimdo-(?P<version>[^-]+)-(?P<python>[^-]+)-"
    r"(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)
EXPECTED_PLATFORM_GROUPS = {
    "linux-aarch64": frozenset({"manylinux2014_aarch64", "manylinux_2_17_aarch64"}),
    "linux-x86_64": frozenset({"manylinux2014_x86_64", "manylinux_2_17_x86_64"}),
    "windows-amd64": frozenset({"win_amd64"}),
    "windows-arm64": frozenset({"win_arm64"}),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    wheels: list[Path],
    *,
    repository: str,
    release_tag: str,
    version: str,
    source_commit: str,
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a lowercase 40-character SHA")
    if release_tag != f"v{version}":
        raise ValueError("release tag must be v followed by the package version")

    entries: list[dict[str, object]] = []
    platform_groups: set[str] = set()
    for wheel in sorted(wheels, key=lambda path: path.name):
        if not wheel.is_file():
            raise ValueError(f"wheel is not a file: {wheel}")
        match = WHEEL_PATTERN.fullmatch(wheel.name)
        if match is None:
            raise ValueError(f"invalid dinkster-aimdo wheel filename: {wheel.name}")
        if match["version"] != version:
            raise ValueError(f"wheel version does not match release: {wheel.name}")
        if match["python"] != "cp39" or match["abi"] != "abi3":
            raise ValueError(f"wheel does not use the cp39 stable ABI: {wheel.name}")
        platform_tags = match["platform"].split(".")
        platform_group = next(
            (
                name
                for name, expected_tags in EXPECTED_PLATFORM_GROUPS.items()
                if frozenset(platform_tags) == expected_tags
            ),
            None,
        )
        if platform_group is None:
            raise ValueError(f"unexpected wheel platform: {match['platform']}")
        if platform_group in platform_groups:
            raise ValueError(f"duplicate wheel platform: {platform_group}")
        platform_groups.add(platform_group)
        entries.append(
            {
                "abi_tag": match["abi"],
                "filename": wheel.name,
                "platform_tags": platform_tags,
                "python_tag": match["python"],
                "sha256": sha256_file(wheel),
                "size": wheel.stat().st_size,
            }
        )

    missing = EXPECTED_PLATFORM_GROUPS.keys() - platform_groups
    if missing:
        raise ValueError("native wheel matrix is incomplete: missing " + ", ".join(sorted(missing)))

    return {
        "package": "dinkster-aimdo",
        "release_tag": release_tag,
        "schema_version": 1,
        "source_commit": source_commit,
        "source_repository": repository,
        "version": version,
        "wheels": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("wheels", type=Path, nargs="+")
    args = parser.parse_args()

    manifest = build_manifest(
        args.wheels,
        repository=args.repository,
        release_tag=args.release_tag,
        version=args.version,
        source_commit=args.source_commit,
    )
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
