"""Shared field types and the base model every Disco contract derives from."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

# A bare lowercase SHA-256 hex digest, used where the field name already says
# what was hashed (``document_sha256``).
Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

# A prefixed digest, used for identifiers that travel between services and
# benefit from being self-describing (``event_id``, ``idempotency_key``).
Sha256Id = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]

# EDGAR accession number in dashed form: 10-digit filer prefix, 2-digit year,
# 6-digit sequence.
AccessionNumber = Annotated[str, StringConstraints(pattern=r"^\d{10}-\d{2}-\d{6}$")]

# Zero-padded 10-digit Central Index Key.
Cik = Annotated[str, StringConstraints(pattern=r"^\d{10}$")]

# EDGAR form type exactly as the index reports it, for example "8-K",
# "SCHEDULE 13G/A". Not an enum: EDGAR adds form types without notice, and the
# coverage plane must accept every one of them.
FormType = Annotated[str, StringConstraints(min_length=1, max_length=40)]

S3Uri = Annotated[
    str, StringConstraints(pattern=r"^s3://[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]/.+")
]

ParserVersion = Annotated[
    str, StringConstraints(pattern=r"^rust-parser@\d+\.\d+\.\d+$")
]

SchemaVersion = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+$")]

NonEmptyString = Annotated[str, StringConstraints(min_length=1)]

# An RFC-3339 timestamp that must carry an offset and must be UTC.
UtcTimestamp = Annotated[datetime, "UTC RFC-3339 timestamp"]


class DiscoModel(BaseModel):
    """Base for every contract artifact.

    ``extra="forbid"`` is deliberate. A closed schema turns a producer typo into
    a validation failure instead of a silently dropped field. The cost is that
    consumers must be deployed before producers start emitting a new field; see
    the compatibility rule in ``contracts/README.md``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def _require_utc(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("timestamps must carry a UTC offset")
            if value.utcoffset() != timedelta(0):
                raise ValueError("timestamps must be expressed in UTC")
        return value
