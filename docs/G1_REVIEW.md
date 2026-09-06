# G1 contract review

Status: pending receiving-owner exercise, joint approval, and merge with green CI.
Pipeline work (A2/A3, B4, and offline B2) has not started in this change.

## Changes to review before freezing

- Validation installs all locked Python workspace packages. Terraform's provider
  lock includes macOS ARM64 and Linux AMD64 checksums.
- All three timestamp fields (`FilingDetected.filed_at`, `observed_at`, and
  `RankedEvent.decision_time`) enforce UTC RFC-3339 syntax. JSON Schema tests
  enable format validation to check calendar dates as well as syntax.
- Probability, analogue median, and peer baseline allow explicit null, retaining
  required keys and numeric bounds. The novelty-only example no longer invents
  probability or zero volatility observations. Other scores remain numeric.
- Schemas and payload examples remain pre-G1 versions. The compatibility rule
  applies to subsequent changes after both owners freeze the contracts.

## Person A's receiving exercise

From a clean clone of the proposed B1 revision:

```sh
mise install uv@0.7.18 rust@1.88.0 terraform@1.12.2
mise exec uv@0.7.18 rust@1.88.0 terraform@1.12.2 -- make check
```

Build a small offline consumer against `contracts/examples/`: read all four
message types and produce a readable summary. For ranking, render null statistics
as “not available,” preserve measured zeros, and respect `should_alert: false`.
For discovery, tolerate unknown ticker and primary document; preserve the stable
filing identity across adapter observations. For parse requests, read the pinned
parser version and document hash. For parsed filings, inspect diagnostics and
verify snippet spans using Unicode character counts.

Record the consumer's path, command, tested commit, and observed output in this
review. The producer's own contract tests do not substitute for this exercise.

## Joint walkthrough and closure record

Review every field in the four schemas together, including identity derivation,
optional discovery metadata, raw and normalized document hashes, evidence
coordinates, timestamp precision, nullable statistics, versions, and closed-schema
consumer-first rollout. JSON Schema consumers must enable formats and separately
check evidence span arithmetic; see `contracts/README.md`.

- Person A consumer and clean-clone result: pending.
- Person A approval of the final contracts: pending.
- Person B approval of the final contracts: pending.
- B1 pull request and green CI run for the reviewed revision: pending.
- Merge commit on `main`: pending.

The receiving owner records closure only after all these items are complete.
