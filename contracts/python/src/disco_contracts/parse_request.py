"""``ParseRequest`` — intake stored a document and wants it parsed.

Emitted by the intake service onto the ``parse-jobs`` queue, only for form types
the parse eligibility policy admits (B6). Everything else stays coverage-only:
metadata retained, document stored, never parsed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import DiscoModel, FormType, ParserVersion, S3Uri, Sha256Digest, Sha256Id


class ParseRequest(DiscoModel):
    """A stored raw document, addressed for parsing."""

    schema_version: Literal["1.0"] = "1.0"

    event_id: Sha256Id
    raw_document_s3_uri: S3Uri = Field(
        description="Versioned S3 location of the immutable raw document."
    )
    document_sha256: Sha256Digest = Field(
        description=(
            "Digest of the raw document bytes as stored. The parser must verify "
            "this before parsing; a mismatch means the object was replaced."
        )
    )
    form_type: FormType
    parser_version: ParserVersion = Field(
        description="Parser build the request targets, for example rust-parser@0.1.0."
    )
