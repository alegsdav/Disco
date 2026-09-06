"""Contract validation: every example is checked against both representations.

The Pydantic models and the generated JSON Schema must agree, so each example is
validated twice — once through the model, once through ``jsonschema``. A schema
that accepts what the model rejects (or the reverse) is a bug in the export.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from disco_contracts import CONTRACTS, DiscoModel
from disco_contracts.export import path_for
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "manifest.json"
)


def examples(validity: str) -> list[tuple[str, Path]]:
    found = [
        (name, path)
        for name in CONTRACTS
        for path in sorted((EXAMPLES / name / validity).glob("*.json"))
    ]
    assert found, f"no {validity} examples found under {EXAMPLES}"
    return found


def load(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def validator_for(name: str) -> Draft202012Validator:
    schema = json.loads(path_for(name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def ids(cases: list[tuple[str, Path]]) -> list[str]:
    return [f"{name}/{path.stem}" for name, path in cases]


VALID = examples("valid")
INVALID = examples("invalid")


@pytest.mark.parametrize(("name", "path"), VALID, ids=ids(VALID))
def test_valid_example_passes_the_model(name: str, path: Path) -> None:
    model: type[DiscoModel] = CONTRACTS[name]
    model.model_validate(load(path))


@pytest.mark.parametrize(("name", "path"), VALID, ids=ids(VALID))
def test_valid_example_passes_the_schema(name: str, path: Path) -> None:
    errors = sorted(validator_for(name).iter_errors(load(path)), key=str)
    assert not errors, "\n".join(error.message for error in errors)


@pytest.mark.parametrize(("name", "path"), INVALID, ids=ids(INVALID))
def test_invalid_example_is_rejected_by_the_model(name: str, path: Path) -> None:
    model: type[DiscoModel] = CONTRACTS[name]
    with pytest.raises(ValidationError):
        model.model_validate(load(path))


@pytest.mark.parametrize(("name", "path"), INVALID, ids=ids(INVALID))
def test_invalid_example_is_rejected_by_the_schema(name: str, path: Path) -> None:
    # Cross-field offset arithmetic has no standard JSON Schema equivalent.
    model_only = {"parsed_filing/snippet-span-does-not-match-text"}
    case = f"{name}/{path.stem}"
    errors = list(validator_for(name).iter_errors(load(path)))
    if case in model_only:
        assert not errors, f"{case} is now schema-detectable; remove it from model_only"
    else:
        assert errors, f"{case} was accepted by the schema"


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_every_contract_has_enough_examples(name: str) -> None:
    valid = list((EXAMPLES / name / "valid").glob("*.json"))
    invalid = list((EXAMPLES / name / "invalid").glob("*.json"))
    assert len(valid) >= 3, (
        f"{name} needs at least 3 valid examples, found {len(valid)}"
    )
    assert len(invalid) >= 1, (
        f"{name} needs at least 1 invalid example, found {len(invalid)}"
    )


@pytest.mark.parametrize(("name", "path"), VALID, ids=ids(VALID))
def test_valid_example_round_trips(name: str, path: Path) -> None:
    model: type[DiscoModel] = CONTRACTS[name]
    instance = model.model_validate(load(path))
    reloaded = model.model_validate(json.loads(instance.model_dump_json()))
    assert reloaded == instance


# --- Identity derivation ------------------------------------------------------
#
# A3 implements event_id and idempotency_key for the services. This is the
# reference the implementation must match; see contracts/README.md.


def derive_event_id(accession_number: str) -> str:
    return "sha256:" + hashlib.sha256(accession_number.encode("utf-8")).hexdigest()


def derive_idempotency_key(adapter: str, accession_number: str) -> str:
    material = f"{adapter}|{accession_number}".encode()
    return "sha256:" + hashlib.sha256(material).hexdigest()


FILING_DETECTED_VALID = [path for name, path in VALID if name == "filing_detected"]


@pytest.mark.parametrize("path", FILING_DETECTED_VALID, ids=lambda p: p.stem)
def test_identity_fields_match_the_documented_derivation(path: Path) -> None:
    payload = load(path)
    accession = str(payload["accession_number"])
    adapter = str(payload["source"]["adapter"])
    assert payload["event_id"] == derive_event_id(accession)
    assert payload["idempotency_key"] == derive_idempotency_key(adapter, accession)


def test_the_same_filing_from_two_adapters_shares_one_event_id() -> None:
    accession = "0001320461-25-000012"
    assert derive_event_id(accession) == derive_event_id(accession)
    assert derive_idempotency_key("daily-index", accession) != derive_idempotency_key(
        "current-feed", accession
    )


# --- Examples are anchored to the committed corpus ----------------------------


def test_document_hashes_reference_real_fixtures() -> None:
    manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    known = {entry["sha256"] for entry in manifest["files"]}

    referenced: set[str] = set()
    for name, path in VALID:
        payload = load(path)
        for field in ("document_sha256", "raw_document_sha256"):
            if field in payload:
                referenced.add(str(payload[field]))

    assert referenced, "no example references a stored document"
    unknown = referenced - known
    assert not unknown, (
        f"examples reference documents not in the corpus: {sorted(unknown)}"
    )


@pytest.mark.parametrize(
    ("name", "example", "field"),
    [
        ("filing_detected", "8-k-from-daily-index", "filed_at"),
        ("filing_detected", "8-k-from-daily-index", "observed_at"),
        ("ranked_event", "alerting-8-k", "decision_time"),
    ],
)
@pytest.mark.parametrize(
    ("timestamp", "valid"),
    [
        ("2025-02-14T12:00:00Z", True),
        ("2025-02-14T12:00:00.123456+00:00", True),
        ("2025-02-14T12:00:00", False),
        ("2025-02-14T12:00:00+01:00", False),
        ("2025-02-14T12:00:00-00:00", False),
        ("2025-02-30T12:00:00Z", False),
        ("2025-02-14T25:00:00Z", False),
        ("2025-02-14 12:00:00Z", False),
        ("2025-02-14", False),
        (1739534400, False),
        ("1739534400", False),
        ("not-a-timestamp", False),
    ],
)
def test_timestamp_wire_contract(
    name: str, example: str, field: str, timestamp: object, valid: bool
) -> None:
    payload = load(EXAMPLES / name / "valid" / f"{example}.json")
    payload[field] = timestamp
    assert validator_for(name).is_valid(payload) == valid
    if valid:
        CONTRACTS[name].model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            CONTRACTS[name].model_validate(payload)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("scores", "prob_unusual_vol"),
        ("historical_analogues", "median_next_session_rv"),
        ("historical_analogues", "peer_baseline_rv"),
    ],
)
@pytest.mark.parametrize("value", [None, 0.0, 0.5, -0.1, "N/A"])
def test_unavailable_ranking_values(section: str, field: str, value: object) -> None:
    payload = load(EXAMPLES / "ranked_event" / "valid" / "alerting-8-k.json")
    payload[section][field] = value
    valid = value is None or value in (0.0, 0.5)
    assert validator_for("ranked_event").is_valid(payload) == valid
    if valid:
        result = CONTRACTS["ranked_event"].model_validate(payload)
        assert json.loads(result.model_dump_json())[section][field] == value
    else:
        with pytest.raises(ValidationError):
            CONTRACTS["ranked_event"].model_validate(payload)
    del payload[section][field]
    assert not validator_for("ranked_event").is_valid(payload)
    with pytest.raises(ValidationError):
        CONTRACTS["ranked_event"].model_validate(payload)
