# Disco — Build Roadmap (Two-Person Plan)

> Ordered by **dependency, not calendar**. Work is split into two lanes that run in parallel, joined by numbered **gates** where one person's output blocks the other's next step.
>
> Companion: [DISCO_PRD.md](DISCO_PRD.md). The PRD defines *what* is built; this defines *who builds it, in what order, and what has to be true before the other person can proceed*.

## The two lanes

| | Person A — Platform / SWE | Person B — Data / Quant |
|---|---|---|
| **Owns** | `infra/`, `services/command-api/`, `services/dispatcher/`, `services/ingestion/` (runtime shell), `scripts/`, `tests/integration/` | `contracts/`, `rust-parser/`, `services/ingestion/` (adapters), `services/ranking/`, `tests/fixtures/`, `reports/` |
| **Responsible for** | Terraform, queues, state, packaging, deployment, telemetry, Discord surface, fault handling, cost | EDGAR adapters, parser, schemas, features, models, event studies, validation |
| **Optimizes for** | Nothing is lost, nothing is duplicated, everything is observable | Nothing is wrong, nothing leaks the future, every claim is measured |

Neither person edits the other's directories without a PR agreement. Contract changes in `contracts/` require both approvals.

---

## Gate map

```text
   PERSON A                          GATES                       PERSON B
   ────────                          ─────                       ────────

   A1  Toolchain & CI  ───────────►  G0 toolchain green ──────►  (B unblocked)
        │                                                             │
        └──────────────────────────  G1 contracts v1  ◄───────────────┤ JOINT
                                          │                           │
   A2  Infra skeleton                     │                     B1  Fixture corpus
        │                                 │                           │
   A3  Platform libraries ─────────►  G2 dev infra + libs ──────►  B2  Daily-index adapter
        │                                                             │
        │                                                        B3  Current-feed adapter
   A4  Intake & queue wiring  ◄──────  G3 adapters emit  ◄────────────┤
        │                                                             │
        │                                                        B4  Rust parser CLI
        │                                                             │
   A5  Parser Lambda  ◄─────────────  G4 CLI + goldens  ◄────────  B5  Benchmark
        │                                                             │
   A6  Coverage observability                                    B6  Parse eligibility
        │                                                             │
        └──────────────────────────►  G5 parsed corpus  ─────────►  B7  Feature store
                                                                      │
                                                                 B8  Novelty baseline
                                                                      │
   A7  Discord dispatcher  ◄────────  G6 RankedEvent  ◄───────────────┤
        │                                                             │
   A8  Slash commands                                             B9  Model & eval
        │
   A9  Failure injection
        │
   A10 Cost & operations
```

**Critical path:** `A1 → G0 → G1 → A2 → A3 → G2 → B2 → B3 → G3 → A4 → G4* → A5 → G5 → B7 → B8 → G6 → A7`
(*G4 requires B4, which B builds in parallel with B2/B3.*)

---

## Gate protocol

A gate is **not** open when the producing person says it's done. A gate is open when **all four** hold:

1. **Merged to `main`** with CI green (lint, unit tests, contract validation, `terraform validate`).
2. **Documented** — a short section in the repo stating the interface, how to run it, and its known limits.
3. **Independently exercised** — the *receiving* person has run it from a clean clone and confirmed the exit criteria themselves.
4. **Versioned** — if the gate is a contract or an artifact format, its `schema_version` / `parser_version` is pinned and any future change follows the compatibility rule in G1.

Point 3 is the one that gets skipped and the one that matters. A gate that only its author can run is not a gate.

**When a gate slips.** The blocked person does not idle and does not start work in the other person's directories. Every blocked phase below lists a *Fallback* — work that is genuinely useful and does not depend on the gate. Most fallbacks are fixture-driven: build against committed example payloads instead of live upstream output.

---

# Person A — Platform / SWE

## A1 — Toolchain & CI baseline
**Blocked by:** nothing · **Opens:** G0

**Goal:** Anyone can clone the repo and get a reproducible environment; CI blocks bad merges.

**Steps**
1. Pin the toolchain: Python 3.13 with a lockfile (`uv` or `pip-tools`), Rust stable via `rust-toolchain.toml`, Terraform version constraint, AWS provider lock file.
2. Establish the workspace layout: `services/*` as Python packages, `rust-parser/` as a Cargo workspace, `contracts/` as language-neutral schema files.
3. One command runs everything: `ruff` + `mypy`, `cargo fmt` + `clippy` + `cargo test`, `terraform fmt` + `validate`. Wrap in a `Makefile` or task runner that CI invokes identically.
4. Wire CI on `main`; protect the branch and require the checks.
5. Add the fixture-hash verification job (it will be empty until B1 lands — wire it now so B doesn't have to touch CI).

**Exit criteria**
- A fresh clone passes `make check` with no network beyond package installs.
- CI is red on a deliberately introduced lint error and blocks merge.
- **B has run `make check` successfully on their own machine.**

> **This is the one phase where B is fully blocked with no fallback.** Do it first and do it fast — a rough-but-working toolchain that B can use beats a polished one that lands later. Refine it afterward.

---

## A2 — Infrastructure skeleton
**Blocked by:** G0, G1 · **Opens:** (feeds G2)

**Goal:** The PRD's AWS topology exists, empty, deployable and destroyable.

**Steps**
1. Terraform modules: versioned S3 buckets (raw, parsed), DynamoDB on-demand table with the PRD key design, Standard SQS queues (`filing-discovery`, `parse-jobs`, `alert-delivery`) each with a DLQ and redrive policy, EventBridge Scheduler rules, per-Lambda scoped IAM roles.
2. Separate `dev` and `prod` state with no shared mutable resources. B works only in `dev`.
3. Tag everything `project=disco`. Add AWS Budgets and Cost Anomaly Detection in the same apply.
4. Add the `SYSTEM_ENABLED` flag as a DynamoDB `CONFIG` item.
5. Deploy a trivial "hello" Lambda through the full path to prove packaging, IAM, and logging.

**Exit criteria**
- `terraform apply` then `destroy` runs clean in `dev` with no orphans.
- Structured Powertools logs reach CloudWatch.
- A budget alarm exists and has fired once in a test.

**Fallback if G1 is slow:** build the infrastructure that doesn't encode contract shapes — buckets, queues, IAM, scheduler, budgets. Only the DynamoDB key design and Lambda event shapes depend on contracts.

---

## A3 — Shared platform libraries
**Blocked by:** A2 · **Opens:** **G2**

**Goal:** B writes adapters and rankers as pure logic, against helpers A owns and tests.

This phase exists specifically so that B never writes AWS plumbing. Ship it deliberately, not as a byproduct.

**Steps**
1. **HTTP client** — SEC rate limiting and User-Agent compliance in one place, shared across concurrent invocations (reserved concurrency plus a token budget). B's adapters call this, never `httpx` directly.
2. **Identity module** — the deterministic `event_id` and `idempotency_key` derivations from the PRD, implemented once with unit tests. Never re-implemented per service.
3. **Storage accessors** — `put_raw`, `put_parsed`, `get_*` over versioned S3 with the PRD's partition scheme; conditional `PutItem` helpers for DynamoDB that make `attribute_not_exists` the default, not an option.
4. **Queue helpers** — publish/consume with batch and partial-batch-failure handling.
5. **Local mode** — every helper works against LocalStack or a temp directory so B can run adapters with no AWS credentials.

**Exit criteria**
- B can write and unit-test an adapter with zero AWS-specific code and no credentials.
- Idempotency helpers have tests proving a second write is a no-op, not an error.
- **B has imported the libraries and run a toy adapter locally.** → **G2 opens**

---

## A4 — Intake service & queue wiring
**Blocked by:** **G3** (B's adapters emit `FilingDetected`) · **Opens:** (feeds G5)

**Goal:** Discovered filings become immutable stored source records, exactly once.

**Steps**
1. Consume `filing-discovery`. Conditional `PutItem` for dedup before any download.
2. Download the primary document via A3's rate-limited client; write to versioned S3 with the content hash recorded.
3. Emit `ParseRequest` for forms in B's eligibility policy (B6); record everything else as coverage-only.
4. Batch consumption with partial batch failure so one bad message doesn't fail a batch.
5. Prove the DLQ path with a deliberately poisoned message.

**Exit criteria**
- A filing discovered by *both* the current feed and the daily index yields exactly one event and one raw S3 object.
- Replaying a day of discovery events creates no duplicate writes and no new S3 versions.

**Fallback while waiting on G3:** build and test the entire intake path against the committed `FilingDetected` fixtures from B1. The adapter is the *source* of these messages; the intake service does not care where they came from. This phase should be ~90% complete before G3 opens.

---

## A5 — Parser Lambda packaging & wiring
**Blocked by:** **G4** (B's parser CLI + goldens + benchmark) · **Opens:** (feeds G5)

**Goal:** B's parser runs on `parse-jobs` at production volume.

**Steps**
1. Package the Rust binary for `provided.al2023` ARM64. The CLI and the Lambda handler share one library — A wraps, A does not fork.
2. Consume `parse-jobs` in batches with partial batch failure reporting.
3. Write `ParsedFiling` to S3 and event state to DynamoDB, both idempotently via A3's helpers.
4. Right-size memory **using B's benchmark numbers** (B5), not by guessing. Set reserved concurrency.
5. Confirm Lambda `Max Memory Used` is consistent with the benchmark's local peak RSS — a large divergence means the packaging or the benchmark is wrong.

**Exit criteria**
- A day of eligible filings parses end to end with zero unhandled errors; the DLQ contains only messages put there on purpose.
- Memory setting is justified by a number in `reports/`.

**Fallback while waiting on G4:** build the Lambda handler and queue wiring against a stub binary that echoes a fixture `ParsedFiling`. Swap the real binary in when G4 opens.

---

## A6 — Coverage observability
**Blocked by:** A4 · **Opens:** **G5**

**Goal:** Prove from a dashboard that nothing was lost.

**Steps**
1. Emit metrics: events discovered per adapter, dedup hits, download failures, bytes stored, reconciliation gap per day, parse success rate.
2. Build the reconciliation dashboard: per-day index rows vs. events created vs. events missing, and time-to-reconcile.
3. Alarm on: reconciliation gap > 0 after the daily run, DLQ depth > 0, download error rate, `SYSTEM_ENABLED` off while schedules are armed.
4. Build the DLQ replay tool — B will need it and should not have to ask A to run it.

**Exit criteria**
- An intentionally dropped message appears as a gap and fires an alarm; the replay tool closes the gap.
- **B can query the parsed corpus in S3 and read the coverage dashboard without A's help.** → **G5 opens**

---

## A7 — Discord dispatcher
**Blocked by:** **G6** (B's `RankedEvent` stream) · **Opens:** nothing

**Goal:** Evidence-backed alerts reach Discord, exactly once.

**Steps**
1. Consume `alert-delivery`; render the evidence card: primary filing link, verbatim snippet with character offsets, scores, feature contributions, historical analogue stats, model and schema versions.
2. Enforce idempotent delivery via the `ALERT#<policy_version>` DynamoDB item.
3. Handle Discord rate limits with backoff; failures go to the DLQ, not a retry loop that hammers the webhook.
4. Ship the high-signal channel only. Gate `all_filings` behind explicit config and label it noisy.

**Exit criteria**
- Every field of the card is independently verifiable against the linked filing by a reader who doesn't trust the system.
- Replaying the delivery queue sends zero duplicate messages.

**Fallback while waiting on G6:** build the full renderer and idempotency path against fixture `RankedEvent` payloads, posting to a private test channel. Only the input source is missing.

---

## A8 — Slash commands
**Blocked by:** A7 · **Opens:** nothing

**Goal:** Query and configure the system from Discord.

**Steps**
1. API Gateway HTTP API → Python command Lambda. Verify Discord's request signature.
2. Acknowledge within Discord's 3-second window; defer anything slower to a follow-up message.
3. Read commands first (look up an event, an issuer, today's coverage stats), then config commands (policy thresholds, channel routing).
4. Authorize config-mutating commands; read commands can stay open to the channel.

**Exit criteria**
- No command exceeds the 3-second acknowledgement budget under cold start.
- An unauthorized user cannot change a policy.

> Coordinate step 3 with B: the config commands write the `POLICY#<policy_name>` items that B's ranking reads. Agree on the policy schema in `contracts/` before implementing the mutation path — this is a small, easily-missed contract dependency.

---

## A9 — Failure injection
**Blocked by:** A7 · **Opens:** nothing

**Steps**
1. Inject: SEC 429/503, S3 write failure, DynamoDB conditional-check failure, parser OOM, Discord 429 and 500, malformed message on every queue.
2. For each, assert the expected outcome — retry, DLQ, alarm, or clean no-op. Nothing silently drops.
3. Test `SYSTEM_ENABLED=false` as a true kill switch across every scheduled entry point.
4. Run a full-day replay from raw S3 and confirm rebuilt state matches production state.

**Exit criteria** — a documented failure matrix where every row has an observed outcome matching its expected one.

---

## A10 — Cost & operations
**Blocked by:** A9 · **Opens:** nothing

**Steps**
1. Cost dashboard by tag; per-filing cost broken out by Lambda, S3, DynamoDB, SQS.
2. S3 lifecycle rules to Glacier / Deep Archive after the retention period.
3. DynamoDB TTL on transient checkpoints; source truth stays in S3.
4. Runbook: replay a DLQ, backfill a missed day, roll back a model version, disable the system.

**Exit criteria**
- Measured cost per 1,000 filings, published — not estimated.
- **B has followed the runbook end to end without A's help.**

---

# Person B — Data / Quant

## B1 — Contracts & fixture corpus
**Blocked by:** G0 · **Opens:** **G1** (contracts, joint) and feeds everything

**Goal:** Every service boundary has a machine-checkable schema and real example payloads.

This is the highest-leverage phase in the project. A's intake, parser wiring, and dispatcher are all built against these fixtures *before* B's live code exists — which is what keeps A unblocked.

**Steps**
1. Write JSON Schema (or Pydantic exported to JSON Schema) for `FilingDetected`, `ParseRequest`, `ParsedFiling`, `RankedEvent`, each carrying `schema_version`.
2. Write the compatibility rule into `contracts/README.md`: additive fields are a minor bump; any removal or type change is a major bump requiring both approvals.
3. Build the corpus in `tests/fixtures/`: real filings covering `8-K`, `10-Q`, `10-K`, `6-K`, Forms 3/4/5, 13D/G, plus deliberately malformed and truncated documents. Record source URI, retrieval timestamp, and SHA-256 in a committed manifest.
4. **Publish example payloads for every contract, not just schemas.** A needs concrete `FilingDetected`, `ParsedFiling`, and `RankedEvent` JSON to build against. Treat these as a deliverable, not a test artifact.
5. Add contract-validation tests: every fixture validates, and at least one invalid fixture is rejected.

**Exit criteria**
- Every PRD contract has a schema, ≥3 valid fixtures, ≥1 rejected invalid fixture.
- The corpus manifest is committed and CI verifies the hashes.
- **A has built something against the example payloads.** → **G1 opens**

---

## B2 — Daily-index reconciler
**Blocked by:** **G2** (A's dev infra + platform libraries) · **Opens:** (feeds G3)

**Goal:** The authoritative completeness mechanism, before any low-latency path exists.

**Steps**
1. Implement `DailyIndexAdapter`: fetch the SEC daily `master` index, parse it, emit one `FilingDetected` per row.
2. Use A3's rate-limited HTTP client and identity module. Do not write your own.
3. Unit-test against saved index fixtures; add a manual dev command for live SEC data.
4. Write a reconciliation record per `(date, index_name)` to DynamoDB: run complete, rows observed, events created.

**Exit criteria**
- For a chosen historical date, event count matches index row count exactly.
- Re-running the same date creates zero new events — idempotency proven, not assumed.

**Fallback while waiting on G2:** the index parsing logic is a pure function from index text to `FilingDetected[]`. Build and fully test it offline against saved index files. Only the S3/DynamoDB/SQS wiring needs G2.

> **Build this before the current-feed poller.** The reconciler is the safety net; a low-latency path without it silently loses filings and you cannot tell.

---

## B3 — Current-feed adapter
**Blocked by:** B2 · **Opens:** **G3**

**Goal:** Low-latency discovery, with the safety net already in place.

**Steps**
1. Implement `CurrentFeedAdapter` with a durable cursor so restarts neither re-emit nor skip.
2. Publish through the *same* code path as the daily adapter — one publish function, two sources.
3. Measure current-feed coverage against index coverage for a live day and write down the gap.

**Exit criteria**
- A live day's reconciliation report shows current-feed vs. index coverage with the gap explained.
- **A has consumed real `FilingDetected` messages off `filing-discovery`.** → **G3 opens**

---

## B4 — Rust parser CLI
**Blocked by:** G1 (contracts) · **Opens:** (feeds G4)

**Goal:** A parser that is correct and benchmarkable before it is ever a Lambda.

This phase depends only on contracts and fixtures — **not on G2**. Run it in parallel with B2/B3 whenever A's infrastructure work is the bottleneck.

**Steps**
1. Streaming `quick-xml` reader for SGML/XML/XBRL. Hard requirement: never load a whole filing into memory.
2. `scraper`-based HTML extraction with bounded text normalization.
3. Emit `ParsedFiling`: items, facts, evidence snippets with character offsets, diagnostics.
4. Expose `disco-parse <file> --out <json>` — usable in tests and benchmarks with no AWS dependency.
5. Generate golden outputs across the corpus; make golden diffs a CI failure.
6. Malformed documents recover and increment `malformed_nodes_skipped`. Never panic.
7. **Structure the crate as a library plus a thin CLI**, so A can wrap the library in a Lambda handler without forking logic.

**Exit criteria**
- Every fixture parses; malformed fixtures produce partial output plus non-zero skip counts.
- Peak RSS is bounded and measured on the largest fixture.
- Golden outputs are committed and stable across runs.

---

## B5 — Parser benchmark
**Blocked by:** B4 · **Opens:** **G4**

**Goal:** A defensible performance claim — or the honest absence of one.

**Steps**
1. Implement the Python `lxml` baseline producing the same `ParsedFiling` shape.
2. Run the PRD protocol: 25 8-K, 25 10-Q, 25 10-K, 10 malformed; 30 warm repetitions per file; identical ARM64 memory setting.
3. Record p50/p95 latency, peak RSS, throughput, GB-seconds per filing, correctness vs. golden, malformed recovery, cold vs. warm.
4. Publish to `reports/` with corpus SHA, runtime versions, Git SHA, memory allocation, and exact command line.

**Exit criteria**
- The report is reproducible from the committed corpus.
- No performance number appears anywhere in the repo that isn't backed by it.
- **A has the memory-sizing number they need for A5.** → **G4 opens**

---

## B6 — Parse eligibility policy
**Blocked by:** B4 · **Opens:** nothing (A4 consumes it)

**Goal:** Decide what gets parsed, separately from what gets stored.

**Steps**
1. Start with forms carrying real corporate-event semantics: `8-K`, `10-Q`, `10-K`, `6-K`, Forms 3/4/5, 13D/G.
2. Express the policy as data in `contracts/`, not as a conditional in A's intake code — A reads it, B owns it.
3. Everything else stays coverage-only: metadata retained, document stored, not parsed.

**Exit criteria** — A's intake service reads the policy file and B can change parse eligibility without a change in A's directories.

---

## B7 — Point-in-time feature store
**Blocked by:** **G5** (A's parsed corpus at volume in S3) · **Opens:** (feeds G6)

**Goal:** Features that cannot leak the future, by construction.

**Steps**
1. Every feature carries `effective_at`, `available_at`, `observed_at`, `source_version`.
2. Implement `available_at <= decision_time < label_window_start` as a *library function*, asserted in every feature-building path — not a convention people remember.
3. Build features in Polars: form type, 8-K item, filing time-of-day, document length and delta, issuer filing history.
4. Macro features from **ALFRED vintages**, never present-day FRED revisions.
5. Write a leakage test suite that deliberately constructs violations and confirms the check rejects them.

**Exit criteria**
- The leakage suite fails loudly on constructed violations.
- A feature table rebuilt from S3 artifacts alone matches a prior build byte for byte at the same versions.

**Fallback while waiting on G5:** build the invariant library, the leakage test suite, and the ALFRED ingestion against the local golden `ParsedFiling` outputs from B4. Only the volume is missing, not the shape.

---

## B8 — Novelty baseline
**Blocked by:** B7 · **Opens:** **G6**

**Goal:** The simplest ranking that could work — the bar every model must clear.

**Steps**
1. **TF-IDF novelty first:** cosine distance from the new document to the *issuer-local* history. No embeddings yet.
2. Rules scoring: form type, item codes, timing, length change.
3. Emit `RankedEvent` with `should_alert` from a fixed threshold policy, published to `alert-delivery`.
4. Only if TF-IDF proves insufficient, add `fastembed` with a pinned local ONNX model — and re-measure.

**Exit criteria**
- Novelty scores are reproducible from the feature store.
- A historical week's alert set is inspectable and defensible filing by filing.
- **A has consumed real `RankedEvent` messages off `alert-delivery`.** → **G6 opens**

> **Open G6 on the baseline, not the model.** A's entire delivery lane (A7, A8, A9, A10) is downstream of this gate. Holding it until B9 finishes would idle A for the whole model-development phase, and would couple shipping an alert product to the model working at all.

---

## B9 — Model & walk-forward evaluation
**Blocked by:** B8 · **Opens:** nothing

**Goal:** Know whether the model actually beats the baseline.

**Steps**
1. Build the labeled dataset: `P(next-session realized volatility is abnormal)` with peer-relative baselines.
2. Chronological expanding/rolling walk-forward splits. Fit embeddings, scalers, thresholds, and calibration **only** within each training slice.
3. Calibrated Logistic Regression baseline first. LightGBM as a challenger only after the LR baseline is complete and evaluated.
4. Report PR-AUC, Precision@k, Brier score, calibration curves, and lift over the novelty baseline — stratified by form type and period.
5. Explainability: LR coefficient contributions or LightGBM SHAP, attached to every `RankedEvent`.

**Exit criteria**
- The evaluation report is in `reports/` and reproducible from a single command.
- **A model that fails to beat the novelty baseline does not ship.** The baseline stays in production and the negative result is written down.

> Shipping a new model version is a *config change* (`model_version` on `RankedEvent`), not a deployment A has to coordinate. Confirm this with A during A8 so the rollback path exists before it's needed.

---

# Coordination

## Joint checkpoints

Four moments where both people must be in the room. Everything else is asynchronous.

| Checkpoint | When | Decision |
|---|---|---|
| **Contract freeze** | G1 | Field-by-field walkthrough of all four schemas. Cheapest possible time to be wrong. |
| **Interface handshake** | G2 | A demos the platform libraries; B writes a toy adapter live. Surfaces bad ergonomics before B builds three adapters on them. |
| **Parser handoff** | G4 | B walks A through the library boundary and benchmark numbers; they agree the memory setting together. |
| **Alert review** | G6 | Both read a week of real alerts filing by filing and agree they're defensible before anything goes to a live channel. |

## Contract change procedure

Once G1 is open, contracts are frozen against casual edits.

1. Propose in a PR against `contracts/` with the version bump and a migration note.
2. Both approve. Additive change → minor bump, no migration. Removal or type change → major bump, and the PR must state what happens to already-stored artifacts.
3. Stored artifacts are never rewritten. Readers handle both versions, or the old version is explicitly abandoned in writing.

## Blocked-work rules

1. **Never idle, never trespass.** Every blocked phase above has a Fallback. Work it.
2. **Build against fixtures, not against people.** If you're waiting on the other person's output, you're usually waiting on the *source* of a message whose *shape* you already have. Build against B1's example payloads.
3. **Escalate a slipping gate in a day, not a week.** A gate is a promise to another person, not a personal task. If it will slip, say so while there's still time to re-plan the fallback.
4. **The receiving person closes the gate.** The producer doesn't get to declare it open. See the gate protocol above.

## Anti-pattern this plan is built to prevent

> One person builds infrastructure for weeks while the other waits, then both integrate at the end and discover the shapes don't match.

The defenses, in order of importance: contracts and example payloads land in B1 before either lane goes deep (G1); A's platform libraries are an explicit deliverable rather than an accident (G2), so B never writes AWS code; and every blocked phase has fixture-driven fallback work so neither lane's slippage stalls the other.

---

# Definition of Done

| PRD requirement | Phase | Owner |
|---|---|---|
| Ingests all observed SEC index events | B3, A4 | B + A |
| Reconciles against the daily index with a provable zero gap | B2, A6 | B + A |
| Stores immutable source artifacts | A4 | A |
| Parses selected high-value filings via Rust at production volume | B4, A5 | B + A |
| Produces reproducible point-in-time ranking records | B7, B8 | B |
| Sends Discord alerts whose every claim is checkable from the filing | A7 | A |

## Deliberate deferrals

Each is cheap to add later and expensive to add early.

| Deferred | Until | Owner |
|---|---|---|
| `fastembed` / ONNX embeddings | TF-IDF novelty is measured and shown insufficient (B8) | B |
| LightGBM | The calibrated LR baseline is complete and evaluated (B9) | B |
| Vendor stream (`sec-api.io`) | Poll + reconcile latency is measured and shown inadequate (B3) | B |
| Iceberg / Athena | Query volume justifies it | A |
| `all_filings` Discord channel | Someone explicitly asks for the noise | A |
| FIFO queues | A genuine issuer-ordered workflow exists | A |

## The recurring principle

**Correct path before fast path.** The daily reconciler precedes the poller. The parser CLI precedes the parser Lambda. The novelty baseline precedes the model. The benchmark precedes any performance claim. Each ordering exists because reversing it makes the system's correctness unverifiable — and in a two-person project, unverifiable work is work the other person cannot safely build on.
