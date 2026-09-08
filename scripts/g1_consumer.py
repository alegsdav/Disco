"""Offline receiving-owner exercise, independent of the producer's models."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


def statistic(value: float | None) -> str:
    return "not available" if value is None else f"{value:g}"


def validate(validator: Draft202012Validator, payload: dict[str, Any]) -> None:
    validator.validate(payload)
    for snippet in payload.get("evidence_snippets", []):
        if snippet["char_end"] - snippet["char_start"] != len(snippet["text"]):
            raise ValueError("Evidence span does not match Unicode character count")


def exercise(root: Path) -> None:
    accepted = rejected = suppressed = 0
    observations: dict[str, list[tuple[str, str]]] = {}
    validators = {}
    for schema_path in sorted((root / "contracts/schemas").glob("*.schema.json")):
        kind = schema_path.name.removesuffix(".schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validators[kind] = validator
        examples = root / "contracts/examples" / kind
        for path in sorted((examples / "valid").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            validate(validator, data)
            accepted += 1
            print(f"{kind}/{path.stem}: schema={data['schema_version']}")
            if kind == "filing_detected":
                accession = data["accession_number"]
                adapter = data["source"]["adapter"]
                expected = "sha256:" + hashlib.sha256(accession.encode()).hexdigest()
                if data["event_id"] != expected:
                    raise ValueError("Unstable filing identity")
                delivery = hashlib.sha256(f"{adapter}|{accession}".encode()).hexdigest()
                if data["idempotency_key"] != "sha256:" + delivery:
                    raise ValueError("Incorrect delivery identity")
                observations.setdefault(accession, []).append((adapter, expected))
                ticker = data.get("ticker") or "unknown"
                print(f"  {accession} via {adapter}; ticker={ticker}"
                      f"; document={data.get('primary_document') or 'unknown'}")
            elif kind == "parse_request":
                print(f"  parser={data['parser_version']}; "
                      f"sha256={data['document_sha256']}")
                print(f"  source={data['raw_document_s3_uri']}")
            elif kind == "parsed_filing":
                print(f"  diagnostics={data['diagnostics']}; "
                      f"verified spans={len(data['evidence_snippets'])}")
            elif kind == "ranked_event":
                action = "ALERT" if data["should_alert"] else "SUPPRESSED"
                suppressed += not data["should_alert"]
                stats = data["historical_analogues"]
                probability = statistic(data['scores']['prob_unusual_vol'])
                print(f"  {action}; probability={probability}"
                      f"; samples={stats['sample_size']}; "
                      f"median={statistic(stats['median_next_session_rv'])}; "
                      f"peer={statistic(stats['peer_baseline_rv'])}")
        for path in sorted((examples / "invalid").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            try:
                validate(validator, data)
            except (ValueError, ValidationError):
                rejected += 1
            else:
                raise ValueError(f"Accepted invalid example: {path}")

    # The committed adapters observe different filings. Derive a second observation
    # of the daily-index filing without changing the producer's examples.
    path = root / "contracts/examples/filing_detected/valid/8-k-from-daily-index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    accession = data["accession_number"]
    original_key = data["idempotency_key"]
    data["source"]["adapter"] = "current-feed"
    data["idempotency_key"] = "sha256:" + hashlib.sha256(
        f"current-feed|{accession}".encode()
    ).hexdigest()
    validate(validators["filing_detected"], data)
    if data["idempotency_key"] == original_key:
        raise ValueError("Adapter delivery keys must differ")
    observations[accession].append(("current-feed", data["event_id"]))
    shared = [rows for rows in observations.values() if len({a for a, _ in rows}) > 1]
    if not shared or any(len({event for _, event in rows}) != 1 for rows in shared):
        raise ValueError("Cross-adapter identity exercise failed")
    if statistic(None) != "not available" or statistic(0.0) != "0" or not suppressed:
        raise ValueError("Ranking display/suppression exercise failed")

    # Exercise code points explicitly; fixture quotations are predominantly ASCII.
    path = next((root / "contracts/examples/parsed_filing/valid").glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["evidence_snippets"] = [
        {"section": "probe", "text": "Aé📈", "char_start": 5, "char_end": 8}
    ]
    validate(validators["parsed_filing"], data)
    data["evidence_snippets"][0]["char_end"] = 5 + len("Aé📈".encode())
    try:
        validate(validators["parsed_filing"], data)
    except ValueError:
        pass
    else:
        raise ValueError("Byte offsets were accepted as character offsets")
    print(f"PASS: {accepted} valid examples; {rejected} invalid examples rejected; "
          f"{len(shared)} cross-adapter filing; {suppressed} suppressed decision(s).")
    print("PASS: null differs from zero; Unicode code points differ from bytes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    exercise(parser.parse_args().root)
