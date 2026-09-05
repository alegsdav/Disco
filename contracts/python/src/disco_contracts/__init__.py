"""Disco data contracts.

The Pydantic models here are the source of truth. ``contracts/schemas/*.json``
is generated from them by ``python -m disco_contracts.export`` and committed so
that non-Python consumers (the Rust parser) read the same definitions. CI fails
if the two drift apart.
"""

from __future__ import annotations

from ._base import (
    AccessionNumber,
    Cik,
    DiscoModel,
    FormType,
    ParserVersion,
    S3Uri,
    Sha256Digest,
    Sha256Id,
)
from .filing_detected import Adapter, FilingDetected, FilingSource
from .parse_request import ParseRequest
from .parsed_filing import EvidenceSnippet, Fact, ParsedFiling, ParseDiagnostics
from .ranked_event import FeatureContribution, HistoricalAnalogues, RankedEvent, Scores

#: Every top-level contract, keyed by the stem of its schema and example files.
CONTRACTS: dict[str, type[DiscoModel]] = {
    "filing_detected": FilingDetected,
    "parse_request": ParseRequest,
    "parsed_filing": ParsedFiling,
    "ranked_event": RankedEvent,
}

__all__ = [
    "CONTRACTS",
    "AccessionNumber",
    "Adapter",
    "Cik",
    "DiscoModel",
    "EvidenceSnippet",
    "Fact",
    "FeatureContribution",
    "FilingDetected",
    "FilingSource",
    "FormType",
    "HistoricalAnalogues",
    "ParseDiagnostics",
    "ParseRequest",
    "ParsedFiling",
    "ParserVersion",
    "RankedEvent",
    "S3Uri",
    "Scores",
    "Sha256Digest",
    "Sha256Id",
]
