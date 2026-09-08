"""``FilingDetected`` — an adapter observed a filing on EDGAR.

Emitted by every ingestion adapter onto the ``filing-discovery`` queue. This is
the coverage plane's unit of work: one message per EDGAR submission, regardless
of whether that submission will ever be parsed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import (
    AccessionNumber,
    Cik,
    DiscoModel,
    FormType,
    NonEmptyString,
    Sha256Id,
    UtcTimestamp,
)

Adapter = Literal["current-feed", "daily-index", "vendor-stream"]


class FilingSource(DiscoModel):
    """Which adapter saw the filing, and at which URI."""

    adapter: Adapter = Field(description="Ingestion adapter that observed the filing.")
    source_uri: NonEmptyString = Field(
        description=(
            "The EDGAR URI the adapter read. For daily-index this is the full "
            "submission text file; for current-feed it is the filing index page."
        )
    )


class FilingDetected(DiscoModel):
    """A filing observed on EDGAR, before anything has been downloaded."""

    schema_version: Literal["1.1"] = "1.1"

    event_id: Sha256Id = Field(
        description=(
            'sha256 of the accession number, prefixed "sha256:". Stable from '
            "discovery onward and identical across adapters, so the same filing "
            "seen twice deduplicates to one event."
        )
    )
    idempotency_key: Sha256Id = Field(
        description=(
            'sha256 of "<adapter>|<accession_number>", prefixed "sha256:". '
            "Distinguishes a redelivery of one adapter's message from a genuine "
            "second observation by a different adapter."
        )
    )

    accession_number: AccessionNumber
    cik: Cik = Field(description="Zero-padded CIK of the filer the index attributed.")
    ticker: str | None = Field(
        default=None,
        description="Ticker when known. Most EDGAR filers have none; null is normal.",
    )
    form_type: FormType
    primary_document: str | None = Field(
        default=None,
        description=(
            "Filename of the primary document within the submission, when the "
            "adapter already knows it. The daily index does not report it, so "
            "intake resolves it after the fact."
        ),
    )

    filed_at: UtcTimestamp = Field(description="Filing timestamp reported by EDGAR.")
    observed_at: UtcTimestamp = Field(description="When the adapter saw it.")
    source: FilingSource
