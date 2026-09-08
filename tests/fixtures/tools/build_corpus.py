"""Download the Disco fixture corpus from SEC EDGAR and write its manifest.

The corpus is committed to the repository; this script exists so the corpus is
reproducible and so new fixtures are added by editing data, not by hand-copying
files. ``make check`` never runs it and never contacts the SEC.

Usage::

    DISCO_SEC_USER_AGENT="Your Name your.email@example.com" \
        python tests/fixtures/tools/build_corpus.py

    python tests/fixtures/tools/build_corpus.py --manifest-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent.parent
SELECTION = Path(__file__).resolve().parent / "selection.json"
MANIFEST = FIXTURES / "manifest.json"

# SEC asks automated clients to stay under 10 requests per second and to
# identify themselves with a contact string.
# https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
REQUEST_INTERVAL_SECONDS = 0.2


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def user_agent() -> str:
    agent = os.environ.get("DISCO_SEC_USER_AGENT", "").strip()
    if not agent:
        raise SystemExit(
            "Set DISCO_SEC_USER_AGENT to a contact string, for example:\n"
            '  DISCO_SEC_USER_AGENT="Jane Doe jane@example.com"'
        )
    return agent


def fetch(url: str, agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": agent})
    time.sleep(REQUEST_INTERVAL_SECONDS)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload: bytes = response.read()
    return payload


# --- Derived malformed fixtures ---------------------------------------------
#
# Each transform is deterministic, so a derived fixture's hash is stable across
# rebuilds. The parser (B4) must recover from every one of these without
# panicking, and must report a non-zero malformed_nodes_skipped count.


def truncate_mid_tag(payload: bytes) -> bytes:
    """Cut at 60% of the document, then extend so it ends inside an open tag."""
    cut = len(payload) * 60 // 100
    opened = payload.find(b"<", cut)
    if opened == -1:
        return payload[:cut]
    return payload[: opened + 3]


def strip_closing_tags(payload: bytes) -> bytes:
    """Remove every closing div and the trailing body/html tags."""
    stripped = payload.replace(b"</div>", b"").replace(b"</DIV>", b"")
    for tail in (b"</html>", b"</HTML>", b"</body>", b"</BODY>"):
        stripped = stripped.replace(tail, b"")
    return stripped


def inject_invalid_utf8(payload: bytes) -> bytes:
    """Insert bytes that cannot appear in valid UTF-8."""
    midpoint = len(payload) // 2
    return payload[:midpoint] + b"\xff\xfe" + payload[midpoint:]


def break_xml_nesting(payload: bytes) -> bytes:
    """Close the root element immediately, orphaning every child element."""
    root = payload.find(b"<ownershipDocument")
    if root == -1:
        root = payload.find(b"<?xml")
    marker = payload.find(b">", root)
    return payload[: marker + 1] + b"</ownershipDocument>" + payload[marker + 1 :]


def empty(payload: bytes) -> bytes:
    return b""


DERIVED: list[dict[str, Any]] = [
    {
        "path": "malformed/truncated-mid-tag.htm",
        "derived_from": "filings/8-k/0001320461-25-000012.htm",
        "transform": truncate_mid_tag,
        "description": "8-K cut at 60% of its bytes, ending inside an unterminated tag",
    },
    {
        "path": "malformed/unclosed-tags.htm",
        "derived_from": "filings/8-k/0001104659-25-013467.htm",
        "transform": strip_closing_tags,
        "description": "8-K with every closing div and trailing body/html tag removed",
    },
    {
        "path": "malformed/invalid-utf8.xml",
        "derived_from": "filings/form-4/0001415889-25-004217.xml",
        "transform": inject_invalid_utf8,
        "description": "Form 4 with two invalid UTF-8 bytes injected at its midpoint",
    },
    {
        "path": "malformed/broken-xml-nesting.xml",
        "derived_from": "filings/form-4/0000950170-25-020428.xml",
        "transform": break_xml_nesting,
        "description": "Form 4 whose root closes immediately, orphaning its children",
    },
    {
        "path": "malformed/empty.txt",
        "derived_from": "filings/6-k/0001140625-25-000028.htm",
        "transform": empty,
        "description": "Zero-byte document",
    },
]


def destination(entry: dict[str, str]) -> Path:
    name = f"{entry['accession_number']}.{entry['ext']}"
    return FIXTURES / "filings" / entry["slug"] / name


def download_corpus(selection: list[dict[str, str]]) -> None:
    agent = user_agent()
    for entry in selection:
        target = destination(entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = fetch(entry["url"], agent)
        except urllib.error.HTTPError as error:  # pragma: no cover - network path
            raise SystemExit(f"{entry['url']} -> HTTP {error.code}") from error
        target.write_bytes(payload)
        print(f"{len(payload):>9}  {target.relative_to(FIXTURES).as_posix()}")


def derive_malformed() -> None:
    for spec in DERIVED:
        source = FIXTURES / str(spec["derived_from"])
        if not source.is_file():
            raise SystemExit(
                f"Cannot derive {spec['path']}: {spec['derived_from']} is missing"
            )
        target = FIXTURES / str(spec["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        transform: Callable[[bytes], bytes] = spec["transform"]
        target.write_bytes(transform(source.read_bytes()))
        print(f"{target.stat().st_size:>9}  {spec['path']}")


def build_manifest(
    selection: list[dict[str, str]], retrieved_at: str
) -> dict[str, Any]:
    previous: dict[str, str] = {}
    if MANIFEST.is_file():
        existing: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
        previous = {
            item["path"]: item["retrieved_at"]
            for item in existing.get("files", [])
            if "retrieved_at" in item
        }

    files: list[dict[str, Any]] = []
    for entry in selection:
        relative = destination(entry).relative_to(FIXTURES).as_posix()
        payload = destination(entry).read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
                "kind": "primary_document",
                "form_type": entry["form_type"],
                "cik": entry["cik"],
                "accession_number": entry["accession_number"],
                "company": entry["company"],
                "filed": entry["filed"],
                "source_uri": entry["url"],
                "retrieved_at": previous.get(relative, retrieved_at),
            }
        )

    for spec in DERIVED:
        relative = str(spec["path"])
        payload = (FIXTURES / relative).read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
                "kind": "derived",
                "derived_from": spec["derived_from"],
                "description": spec["description"],
            }
        )

    return {"files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Disco fixture corpus.")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Rebuild derived fixtures and the manifest without contacting the SEC.",
    )
    arguments = parser.parse_args()

    selection: list[dict[str, str]] = json.loads(SELECTION.read_text(encoding="utf-8"))
    if not arguments.manifest_only:
        download_corpus(selection)
    derive_malformed()

    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_manifest(selection, retrieved_at)
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(manifest, indent=2) + "\n")
    total = sum(int(item["bytes"]) for item in manifest["files"])
    print(f"\nmanifest.json: {len(manifest['files'])} fixtures, {total} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
