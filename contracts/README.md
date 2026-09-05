# Contracts

Every service boundary in Disco is a message with a machine-checkable shape. This
directory holds those shapes, plus real example payloads so either lane can build
against a contract before the code that produces it exists.

| Contract | Produced by | Consumed by | Queue / store |
|---|---|---|---|
| `FilingDetected` | ingestion adapters (B2, B3) | intake service (A4) | `filing-discovery` |
| `ParseRequest` | intake service (A4) | parser Lambda (A5) | `parse-jobs` |
| `ParsedFiling` | Rust parser (B4, A5) | feature builder (B7) | S3 `parsed/` |
| `RankedEvent` | ranking (B8, B9) | Discord dispatcher (A7) | `alert-delivery` |

## Layout

```text
contracts/
  schemas/*.schema.json     generated, committed, language-neutral
  examples/<contract>/valid/*.json
  examples/<contract>/invalid/*.json
  python/                   the Pydantic models (source of truth) + tests
```

## Source of truth

The Pydantic models in `python/src/disco_contracts/` are authoritative.
`schemas/*.schema.json` is generated from them and committed so the Rust parser
and any future non-Python consumer read the same definitions.

```sh
make contracts        # regenerate the schema files
make contracts-check  # fail if they drift from the models (this runs in CI)
```

Python services import the models directly:

```python
from disco_contracts import FilingDetected

event = FilingDetected.model_validate(json.loads(message.body))
```

Everyone else reads `schemas/*.schema.json`.

### The two representations are not identical

Two rules cannot be expressed in JSON Schema, so the models enforce them and the
schemas do not:

- **Timestamps must be UTC.** A naive or offset timestamp is a well-formed
  `date-time` string; only the model rejects it.
- **Evidence offsets must match their text.** `char_end - char_start` must equal
  `len(text)`; JSON Schema has no cross-field arithmetic.

`contracts/python/tests/test_contracts.py` pins this: each invalid example is
asserted against both representations, and the two rules above are listed
explicitly as model-only. A consumer validating with JSON Schema alone gets a
weaker guarantee and should re-check those two properties itself.

## Compatibility rule

Once G1 is open, contracts are frozen against casual edits.

1. Propose the change in a PR against `contracts/` with the version bump and a
   migration note.
2. **Both owners approve.** No exceptions.
3. **Additive field → minor bump** (`1.0` → `1.1`). No migration of stored
   artifacts.
4. **Removal or type change → major bump** (`1.1` → `2.0`). The PR must state
   what happens to already-stored artifacts.
5. **Stored artifacts are never rewritten.** Readers handle both versions, or the
   old version is explicitly abandoned in writing.

### Why closed schemas change the deployment order

Every contract sets `additionalProperties: false`. A producer typo becomes a
validation failure instead of a silently dropped field, which is the behaviour
worth having in an ingestion pipeline.

The cost is real and worth stating: an old consumer rejects a payload carrying a
new field. So even for an additive minor bump, **deploy consumers before
producers**. Stored artifacts still never need rewriting — point 5 holds either
way — but the rollout is ordered.

## Identity derivation

`A3` implements these for the services. This is the definition it must match;
`test_contracts.py` holds the reference implementation and asserts every example
agrees with it.

```text
event_id        = "sha256:" + sha256(accession_number)
idempotency_key = "sha256:" + sha256(adapter + "|" + accession_number)
```

Both are computed over UTF-8 bytes and rendered as lowercase hex.

**`event_id` keys the filing.** An EDGAR accession number uniquely identifies one
submission, so the same filing seen by the current feed and by the daily index
derives the same `event_id` and deduplicates to one event — which is exactly A4's
exit criterion.

**`idempotency_key` keys one adapter's delivery.** It exists to tell a redelivery
of a single adapter's message apart from a genuine second observation by a
different adapter. Cross-adapter deduplication is `event_id`'s job, not this one's.

> **Deviation from the PRD.** `docs/DISCO_PRD.md` originally derived `event_id`
> from `accession | primary_document | content_hash`. That cannot be computed at
> discovery time: `FilingDetected` is emitted before anything is downloaded, so
> the content hash does not exist yet, and the daily index does not report the
> primary document filename at all. Deriving it from the accession number alone
> keeps the identifier stable from discovery through delivery. The content hash
> is still carried, on `ParseRequest.document_sha256` and
> `ParsedFiling.raw_document_sha256`, where it is genuinely known. The PRD has
> been updated to match.

## Evidence offsets

`ParsedFiling.evidence_snippets[].char_start` / `char_end` index into the
parser's **normalized text**, not the raw document. That text is not carried in
the message, so `ParsedFiling.normalized_text_sha256` identifies exactly which
normalization the offsets refer to, and `disco-parse --emit-text` (B4) writes the
text itself.

This matters for A7: an alert card claiming a verbatim quotation is only
checkable if the reader can reproduce the string the offsets point at.

## Examples

Each contract has at least three valid examples and at least one invalid one.
They are not toy data — accession numbers, CIKs, form types and document hashes
come from the committed corpus in `tests/fixtures/`, and a test asserts that
every document hash an example references is really in the manifest.

Invalid examples are named for the rule they break, for example
`filing_detected/invalid/accession-number-wrong-format.json`.

## Form types are not an enum

`form_type` is a bounded string, deliberately. EDGAR adds and renames form types
without notice, and the coverage plane must accept every one of them — an
unrecognised form type is a filing to store, not a message to reject.

Note that the daily index reports 13D/G filings as `SCHEDULE 13D` and
`SCHEDULE 13G` (with a space), not the `SC 13D` / `13D/G` shorthand used in the
PRD. B6's eligibility policy must match the index's spelling, not the shorthand.
