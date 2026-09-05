"""Verify fixture content hashes recorded by the fixture corpus manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fixture:
        for chunk in iter(lambda: fixture.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_entries(manifest_path: Path) -> list[dict[str, str]]:
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("manifest must contain a files array")

    normalized_entries: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each manifest entry must be an object")
        path = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(path, str) or not isinstance(expected_hash, str):
            raise ValueError("each entry requires string path and sha256 fields")
        normalized_entries.append({"path": path, "sha256": expected_hash})
    return normalized_entries


def verify(manifest_path: Path) -> int:
    if not manifest_path.exists():
        print(f"No fixture manifest at {manifest_path}; nothing to verify.")
        return 0

    failures = 0
    for entry in load_entries(manifest_path):
        fixture_path = manifest_path.parent / entry["path"]
        if not fixture_path.is_file():
            print(f"Missing fixture: {entry['path']}")
            failures += 1
            continue
        if sha256(fixture_path) != entry["sha256"].lower():
            print(f"Hash mismatch: {entry['path']}")
            failures += 1
    if failures:
        return 1

    print(f"Verified {len(load_entries(manifest_path))} fixture hashes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/manifest.json"),
    )
    arguments = parser.parse_args()
    return verify(arguments.manifest)


if __name__ == "__main__":
    raise SystemExit(main())
