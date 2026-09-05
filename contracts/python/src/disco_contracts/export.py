"""Generate ``contracts/schemas/*.schema.json`` from the Pydantic models.

``--check`` verifies the committed schemas match the models and is what
``make check`` runs; it never writes. ``--write`` regenerates them.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any

from . import CONTRACTS

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
SCHEMA_ID_BASE = "https://github.com/alegsdav/Disco/contracts/schemas"


def schema_for(name: str) -> str:
    model = CONTRACTS[name]
    schema: dict[str, Any] = model.model_json_schema(mode="serialization")
    # Prepended rather than assigned so the identifying keys sort to the top of
    # the committed file and diffs stay readable.
    identified: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{SCHEMA_ID_BASE}/{name}.schema.json",
        **schema,
    }
    return json.dumps(identified, indent=2, sort_keys=True) + "\n"


def path_for(name: str) -> Path:
    return SCHEMA_DIR / f"{name}.schema.json"


def write() -> int:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name in CONTRACTS:
        target = path_for(name)
        # newline="" so the file is byte-identical regardless of platform;
        # --check compares it byte for byte.
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(schema_for(name))
        print(f"wrote {target.name}")
    return 0


def check() -> int:
    failures = 0
    for name in CONTRACTS:
        target = path_for(name)
        expected = schema_for(name)
        actual = ""
        if target.is_file():
            actual = target.read_text(encoding="utf-8", newline="")
        if actual == expected:
            continue
        failures += 1
        print(f"{target.name} is out of date:")
        diff = difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"committed/{target.name}",
            tofile=f"generated/{target.name}",
        )
        print("".join(diff))
    if failures:
        print(
            f"\n{failures} schema(s) differ from the models. "
            "Run: uv run python -m disco_contracts.export --write"
        )
        return 1
    print(f"{len(CONTRACTS)} schemas match their models.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write", action="store_true", help="Regenerate the schema files."
    )
    group.add_argument(
        "--check", action="store_true", help="Fail if they are out of date."
    )
    arguments = parser.parse_args()
    return write() if arguments.write else check()


if __name__ == "__main__":
    raise SystemExit(main())
