"""``ParsedFiling`` — the Rust parser's output for one document.

Written to S3 by the parser Lambda and read by the feature builder. Evidence
snippets carry character offsets so an alert's quotation can be checked against
the filing by a reader who does not trust the system.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from ._base import DiscoModel, NonEmptyString, ParserVersion, Sha256Digest, Sha256Id

# 8-K item codes such as "2.02", or a section label for forms without items.
ItemCode = Annotated[str, StringConstraints(min_length=1, max_length=16)]


class Fact(DiscoModel):
    """One extracted value, normally an XBRL fact."""

    concept: NonEmptyString = Field(
        description="Taxonomy concept, for example us-gaap:Revenues."
    )
    value: str = Field(
        description=(
            "Verbatim value as a string. Never a float: XBRL monetary values "
            "exceed double precision and must survive a round trip unchanged."
        )
    )
    unit: str | None = Field(
        default=None, description="Unit reference, for example USD."
    )
    period_end: date | None = Field(
        default=None, description="End of the reported period."
    )


class EvidenceSnippet(DiscoModel):
    """A quotable passage, anchored by offsets into the normalized text."""

    section: NonEmptyString = Field(
        description='Section label, for example "Item 2.02".'
    )
    text: NonEmptyString = Field(
        description="The passage, verbatim from the normalized text."
    )
    char_start: int = Field(ge=0, description="Inclusive start offset.")
    char_end: int = Field(ge=0, description="Exclusive end offset.")

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("offset span must match the length of text")
        return self


class ParseDiagnostics(DiscoModel):
    """What the parse run cost and what it could not read."""

    bytes_read: int = Field(ge=0)
    parse_duration_ms: int = Field(ge=0)
    malformed_nodes_skipped: int = Field(
        ge=0,
        description=(
            "Nodes the parser recovered from rather than failing on. Must be "
            "non-zero for the malformed fixtures in tests/fixtures/malformed."
        ),
    )


class ParsedFiling(DiscoModel):
    """Normalized content extracted from one raw document."""

    schema_version: Literal["1.0"] = "1.0"

    event_id: Sha256Id
    parser_version: ParserVersion
    raw_document_sha256: Sha256Digest = Field(
        description="Digest of the raw document this output was produced from."
    )
    normalized_text_sha256: Sha256Digest = Field(
        description=(
            "Digest of the normalized plain text the parser derived. Every "
            "char_start/char_end below indexes into that text, so offsets are "
            "only meaningful alongside this digest. `disco-parse --emit-text` "
            "writes the text itself for verification."
        )
    )

    items: list[ItemCode] = Field(
        default_factory=list,
        description=(
            "Item codes present, for example 8-K items. "
            "Empty for forms without items."
        ),
    )
    facts: list[Fact] = Field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    diagnostics: ParseDiagnostics
