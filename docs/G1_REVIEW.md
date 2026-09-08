# G1 contract review

Status: G1 closed on 2026-09-07 at the user's direction after both owner
approvals, the receiving exercise, passing final-revision CI, and merge.
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

### Receiving exercise result (2026-09-07)

Executed by Codex at Person A's request against clean local clone
`C:/Users/a1a2d/AppData/Local/Temp/disco-g1-a10326b`, created with
`git clone --no-hardlinks --branch b1-contracts-and-fixture-corpus . <clone>`.
Tested commit: `a10326b62594f2527d0adf9d921649e7e91d28b1`.
The clone's tracked files were unchanged. The new consumer was run from the
working repository against that clone using `--root`; it is not part of that SHA.

Consumer: `scripts/g1_consumer.py`. It uses the published JSON schemas with
format checking, without importing the producer's Pydantic models. Run from the
repository after bootstrap:

```sh
uv run --locked --all-packages python scripts/g1_consumer.py
```

On this Windows host, `make` was unavailable. After
`uv sync --locked --all-packages --group dev`, all underlying `make check`
commands were run in the clean clone, using its `.venv/Scripts/python.exe`
for Python and the existing pinned toolchain for Cargo and Terraform:

```text
python -m ruff check .                                    PASS
python -m mypy                                            PASS (14 files)
python -m disco_contracts.export --check                   PASS (4 schemas)
python -m pytest                                          PASS (128 tests)
python scripts/verify_fixture_hashes.py                    PASS (23 hashes)
cargo fmt --manifest-path rust-parser/Cargo.toml --all -- --check
cargo clippy --manifest-path rust-parser/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path rust-parser/Cargo.toml          PASS (0 Rust tests)
terraform -chdir=infra init -backend=false -lockfile=readonly
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate                           PASS
```

Toolchain: uv 0.7.18, Python 3.13.5, Rust 1.88.0, Terraform 1.12.2.
Dependency/provider setup required network access; the consumer itself is offline.
Consumer command from the clean clone:

```text
.venv/Scripts/python.exe C:/Users/a1a2d/Documents/Duit/scripts/g1_consumer.py --root .
```

Observed output included:

```text
daily-index: ticker=unknown; document=unknown
parser=rust-parser@0.1.0; sha256=3de40c5b1f6cf2ea62e4e4c22007bedc0a26f48c189d8a9344cc359df25cfaef
malformed_nodes_skipped: 14; verified spans=1
SUPPRESSED; probability=0.08; samples=412; median=0.011; peer=0.012
ALERT; probability=not available; samples=0; median=not available; peer=not available
PASS: 13 valid examples; 14 invalid examples rejected; 1 cross-adapter filing; 1 suppressed decision(s).
PASS: null differs from zero; Unicode code points differ from bytes.
```

The cross-adapter check derives a current-feed observation from the daily-index
example in memory, because the committed examples observe different filings.
It verifies the same event ID and different delivery keys. An additional Unicode
probe accepts code-point offsets and rejects UTF-8 byte offsets. The consumer's
null/zero rendering is checked separately. Ruff and strict mypy pass for the new
consumer as well.

Limits: span arithmetic is verified, but quotations cannot yet be compared with
the parser's normalized text artifact (B4). Suppression is an offline decision;
no Discord messages are sent. This result is technical evidence for Person A's
review, not either owner's approval or evidence of hosted CI. Re-exercise if the
reviewed contracts change.

## Joint walkthrough and closure record

Review every field in the four schemas together, including identity derivation,
optional discovery metadata, raw and normalized document hashes, evidence
coordinates, timestamp precision, nullable statistics, versions, and closed-schema
consumer-first rollout. JSON Schema consumers must enable formats and separately
check evidence span arithmetic; see `contracts/README.md`.

- Person A consumer and clean-clone result: passed at a10326b; evidence above.
- Person A approval of the final contracts: approved, reported by the user on
  2026-09-07 ("both of us approve").
- Person B approval of the final contracts: approved, reported by the user on
  2026-09-07 in the same instruction. No contract changes since the exercise.
- B1 pull request: [#2](https://github.com/alegsdav/Disco/pull/2).
- Final revision `648b99508aee81b99f00b5e0788f7fa25713c5c9` passed
  [CI](https://github.com/alegsdav/Disco/actions/runs/34178030623), including
  the independent consumer. Contracts were unchanged from the clean-clone exercise.
- Merge commit on `main`: `91ece0022c430c32b5b945a8cef3a57a7d675a76`.

Closure recorded by Codex on behalf of Person A under the user's instruction
to finalize the approved handoff. A2 and offline B2 may proceed; live B2 needs G2.
