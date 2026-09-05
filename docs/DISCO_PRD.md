# Disco — Revised PRD and Architecture Guideline

> Status: design guideline, not an immutable implementation specification. Pin exact package and provider versions in lockfiles, and re-check vendor pricing before deployment.

## 1. Executive Summary

Disco is an AWS-native regulatory-event intelligence pipeline. It ingests the **entire SEC EDGAR filing universe**, persists an immutable source record for every observed filing, parses selected documents, ranks research relevance, and delivers evidence-backed Discord alerts.

The system is deliberately split into two planes:

- **Coverage plane:** capture and reconcile every EDGAR filing, including filers without a ticker. This is an ingestion/audit requirement, not a promise that every filing is material.
- **Research plane:** parse, score, and notify according to configurable form, issuer, and score policies. Its default output is high-signal alerts; an `all_filings` Discord channel may be enabled, but will be extremely noisy.

Disco is a research tool, not investment advice, execution software, or a generic LLM summarizer. An alert must cite its primary filing, relevant verbatim snippet, model and schema versions, feature contributions, and historical analogue statistics.

### Important ingestion reality

The SEC does **not** provide a guaranteed push webhook for every filing. Its official daily and full EDGAR indexes cover all public filings, while a current-filings feed is a pull-based, best-effort low-latency source. Therefore the recommended no-vendor-loss architecture is: frequent current-feed polling plus mandatory official daily-index reconciliation. SEC documents daily indexes and full indexes as its public coverage mechanism. [SEC: Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

## 2. Technology Stack and Selection Rationale

| Layer | Preferred choice | Why | Viable alternative |
|---|---|---|---|
| IaC | Terraform + AWS provider, version constrained | Portable, reviewable plans; provider lock file prevents accidental upgrades. | AWS CDK; not selected because Terraform better exposes infrastructure skills. |
| Python runtime | Python 3.13, ARM64 Lambda | Supported on Amazon Linux 2023 through 2029; strong data/ML ecosystem. | Python 3.14 after team validation. |
| Python services | `boto3`, `aws-lambda-powertools`, `pydantic>=2`, `httpx`, `orjson` | Typed contracts, structured logs, efficient HTTP/JSON. | Standard library only for minimal MVP. |
| Rust runtime | Rust stable + `provided.al2023` ARM64 Lambda | Native AOT binary, no Python binding layer. | Lambda container image if dependencies outgrow ZIP packaging. |
| Rust parsing | `quick-xml` 0.41+, `serde`, `serde_json`, `aws-sdk-s3`, `lambda_runtime` | `quick-xml` has a streaming StAX-style reader designed for documents that cannot fit in memory. | `lxml` baseline only; do not make it production parser. |
| HTML extraction | Rust `scraper` plus bounded text normalization | Keeps parsing ownership in one runtime. | `html5ever` if malformed HTML compatibility proves inadequate. |
| Embeddings | Python `fastembed` with a pinned local ONNX model | Local inference avoids paid LLM/API dependence; produce vectors only for eligible documents. | TF-IDF baseline for first release; Bedrock embeddings only if model operations justify cost. |
| ML | scikit-learn Logistic Regression + calibration; LightGBM 4.7+ challenger | Interpretable baseline first; LightGBM only if it improves walk-forward metrics. | Logistic Regression remains production model if challenger fails. |
| Tabular research | Polars + PyArrow | Efficient columnar historical computations. | Pandas for notebooks/small prototypes. |
| API/Discord | API Gateway HTTP API + Python Lambda; Discord HTTP interactions and webhook delivery | No persistent Discord Gateway process. Discord requires initial interaction acknowledgement within 3 seconds. | Gateway bot only if a later feature truly needs gateway events. |
| Storage/state | S3 versioned buckets + DynamoDB on-demand | Immutable data lake plus low-ops idempotency/state table. | Iceberg/Athena only after query volume justifies it. |

AWS currently supports Python 3.13 on AL2023 and recommends OS-only runtimes such as `provided.al2023` for native Rust binaries. [AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) [OS-only runtimes](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-provided.html) `quick-xml` is specifically appropriate for streaming large XML, although its documented encoding limitations must be tested against real filings. [quick-xml documentation](https://docs.rs/quick-xml/latest/quick_xml/)

## 3. Target Architecture

```text
EventBridge Scheduler (every 1–5 min)        EventBridge Scheduler (daily)
          |                                               |
          v                                               v
  Current-feed poller Lambda                    Official-index reconciler Lambda
          |                                               |
          +-------------------- FilingDetected -----------+
                                       |
                                       v
                              SQS Standard: filing-discovery
                                       |
                                       v
                          Python intake Lambda / rate limiter
                           |                    |
              immutable source data             | ParseRequest
                           v                    v
                     S3 raw/versioned       SQS Standard: parse-jobs ──> DLQ
                                                |
                                                v
                                    Rust parser Lambda (quick-xml)
                                                |
                          ParsedFiling JSON to S3 + event state to DynamoDB
                                                |
                                                v
                                  Python ranker / feature builder
                                                |
                                                v
                            SQS Standard: alert-delivery ──> DLQ
                                                |
                                                v
                          Discord webhook dispatcher Lambda

Discord slash commands -> API Gateway HTTP API -> Python command Lambda -> DynamoDB/S3
```

Use **Standard SQS**, not FIFO, for SEC-wide ingestion: ordering across unrelated filers is not meaningful and throughput matters. Idempotency makes at-least-once delivery safe. Reserve FIFO only for a future issuer-specific ordered workflow.

### Ingestion adapters

1. `CurrentFeedAdapter`: polls current filings for low-latency candidates and advances a cursor/checkpoint.
2. `DailyIndexAdapter`: parses SEC `master` daily index files, creates missing events, and marks reconciliation complete.
3. `VendorStreamAdapter` (optional): isolates a paid vendor stream behind the same `FilingDetected` contract.

The daily reconciler is authoritative for completeness. A paid sec-api.io stream advertises WebSocket delivery of new filings and all-filer coverage, but its own pricing page notes that pull RSS is not a complete real-time source. A persistent WebSocket consumer is not a natural Lambda workload; use it only through a vendor webhook offering or a separately authorized non-serverless connector. [sec-api Stream API](https://sec-api.io/docs/stream-api/) [sec-api pricing](https://sec-api.io/pricing)

## 4. Data Contracts and Storage

All artifacts carry `schema_version`, UTC RFC-3339 timestamps, deterministic IDs, and a SHA-256 content hash.

> The shapes below are the design intent. The **normative** definitions are the Pydantic models in `contracts/python/`, with `contracts/schemas/*.schema.json` generated from them and committed for non-Python consumers. Where this section and `contracts/` disagree, `contracts/` wins and this section is a bug. See [contracts/README.md](../contracts/README.md) for the compatibility rule.

### `FilingDetected`

```json
{
  "schema_version": "1.1",
  "event_id": "sha256:<sha256 of accession_number>",
  "idempotency_key": "sha256:<sha256 of adapter|accession_number>",
  "accession_number": "0000000000-26-000001",
  "cik": "0000000000",
  "ticker": null,
  "form_type": "8-K",
  "primary_document": null,
  "filed_at": "2026-09-03T20:42:00Z",
  "observed_at": "2026-09-03T20:45:00Z",
  "source": {"adapter": "daily-index", "source_uri": "https://www.sec.gov/..."}
}
```

**Identity.** `event_id` is derived from the accession number alone, because `FilingDetected` is emitted at discovery — before anything is downloaded — and the daily index does not report the primary document filename. An earlier draft derived it from `accession | primary_document | content_hash`; neither of those two components exists at the moment the message is created. The accession number already uniquely identifies an EDGAR submission, so a filing seen by both the current feed and the daily index derives one `event_id` and deduplicates to one event. The content hash is still carried on `ParseRequest.document_sha256` and `ParsedFiling.raw_document_sha256`, where it is genuinely known.

`idempotency_key` includes the adapter, so a redelivery of one adapter's message is distinguishable from a second, independent observation. Cross-adapter deduplication is `event_id`'s job.

`primary_document` is optional: the current feed knows it, the daily index does not, and intake resolves it when absent.

### `ParseRequest`

```json
{
  "schema_version": "1.0",
  "event_id": "sha256:...",
  "raw_document_s3_uri": "s3://disco-raw/sec/year=2026/month=09/day=03/accession=.../filing.sgml",
  "document_sha256": "...",
  "form_type": "8-K",
  "parser_version": "rust-parser@0.1.0"
}
```

### `ParsedFiling`

```json
{
  "schema_version": "1.0",
  "event_id": "sha256:...",
  "parser_version": "rust-parser@0.1.0",
  "raw_document_sha256": "...",
  "normalized_text_sha256": "...",
  "items": ["2.02", "9.01"],
  "facts": [{"concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "value": "13507000000", "unit": "USD", "period_end": "2026-07-26"}],
  "evidence_snippets": [{"section": "Item 2.02", "text": "...", "char_start": 0, "char_end": 300}],
  "diagnostics": {"bytes_read": 18238124, "parse_duration_ms": 412, "malformed_nodes_skipped": 3}
}
```

**Evidence offsets.** `char_start` and `char_end` index into the parser's normalized text, not the raw document. That text is not carried in the message, so `normalized_text_sha256` pins which normalization the offsets refer to and `disco-parse --emit-text` writes the text itself. Without this, an alert's "verbatim snippet with character offsets" cannot actually be checked by a reader, which is the requirement in §9.

### `RankedEvent`

```json
{
  "schema_version": "1.0",
  "event_id": "sha256:...",
  "decision_time": "2026-09-03T20:42:00Z",
  "feature_schema_version": "1.0",
  "model_version": "lgbm-volatility-v0.2.1",
  "scores": {"materiality": 0.78, "novelty": 0.84, "prob_unusual_vol": 0.62, "final": 0.79},
  "feature_contributions": [{"feature": "novelty_cosine_distance", "contribution": 0.24}],
  "historical_analogues": {"sample_size": 37, "median_next_session_rv": 0.031, "peer_baseline_rv": 0.018},
  "alert_policy": "high_signal_v1",
  "should_alert": true
}
```

### DynamoDB keys

```text
PK=EVENT#<event_id>                 SK=METADATA
PK=EVENT#<event_id>                 SK=RANK#<model_version>
PK=EVENT#<event_id>                 SK=ALERT#<policy_version>
PK=SOURCE#SEC#<yyyy-mm-dd>          SK=RECONCILIATION#<index_name>
PK=CONFIG                            SK=POLICY#<policy_name>
```

Conditional `PutItem` with `attribute_not_exists(PK)` and `attribute_not_exists(SK)` is mandatory at every deduplication boundary.

## 5. Processing and ML Guideline

### Rust parser

The parser reads from S3, streams SGML/XML/XBRL using `quick-xml::Reader`, emits normalized facts/snippets, and writes `ParsedFiling` to S3. It must not load an entire filing into memory, invoke Python, or call an LLM. It must expose a local CLI for fixture-driven tests and benchmarks.

### Ranking

1. Rules: form type, 8-K item, filing-time, document length/change, issuer history.
2. Novelty: cosine distance between the new document embedding and an **issuer-local** historical embedding index.
3. ML: calibrated Logistic Regression baseline; LightGBM challenger for `P(next-session realized volatility is abnormal)`.
4. Explainability: Logistic Regression coefficient contributions or LightGBM SHAP contributions; no generated explanation may replace evidence.

Start with only forms that have meaningful corporate-event semantics (`8-K`, `10-Q`, `10-K`, `6-K`, Forms `3`/`4`/`5`, and Schedules 13D/13G). Retain all other form metadata in the coverage plane, but do not pay to parse every exhibit before a measured need exists.

Match the index's own spelling, not the shorthand above: the daily index reports these as `SCHEDULE 13D` and `SCHEDULE 13G` (with a space, and with `/A` suffixes for amendments), not `SC 13D` or `13D/G`. B6's eligibility policy is matched against the index string, so the shorthand would silently match nothing.

## 6. Point-in-Time Integrity and Backtesting

Every feature has `effective_at`, `available_at`, `observed_at`, and `source_version`. Backtest invariant:

```text
feature.available_at <= decision_time < label_window_start
```

Use ALFRED vintages—not present-day revised FRED observations—for macro features in historical experiments. ALFRED retains original releases and subsequent revisions. [ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html)

Use chronological expanding/rolling walk-forward splits. Fit embeddings, feature scalers, thresholds, calibration, and model parameters only on each training slice. Report PR-AUC, Precision@k, Brier score, calibration, baseline lift, and results stratified by form type and period. A model that fails to beat a novelty baseline is a valid result and should not ship.

## 7. Cost Model and Options

Costs are regional and usage-dependent; calculate the final estimate in the AWS Pricing Calculator before deployment. Do not claim the system is always free.

| Item | Recommended configuration | Illustrative monthly cost driver | Free/lower-cost alternative |
|---|---|---|---|
| SEC metadata/raw filings | Official SEC indexes + EDGAR downloads | $0 vendor cost; engineering cost and SEC rate limit | This is the default. |
| Real-time all-filing feed | sec-api.io Personal/Startup | $55 monthly or $49/month billed annually, plus download overage | Current-feed polling + daily official reconciliation. |
| Lambda | ARM64, batch SQS messages, right-size memory | requests plus GB-seconds; raw parsing volume dominates | Batch, benchmark, and process only eligible forms. |
| SQS | Standard queues + DLQs | request count; first 1M requests/month currently free | Batch records and put S3 keys—not documents—in messages. |
| EventBridge Scheduler | 1–5 minute poll + daily reconciliation | 14M invocations/month currently free, then $1/M | Keep a single schedule; do not make one schedule per issuer. |
| S3 | Versioned raw/parsed buckets | GB-month storage, PUT/GET, retrieval, egress | Lifecycle raw data to Glacier/Deep Archive after retention period. |
| DynamoDB | On-demand event/alert state | writes, reads, and storage | TTL transient checkpoints; retain source truth in S3. |
| API Gateway | HTTP API for commands only | request/data-transfer volume | Lambda Function URL if API Gateway features are not required. |
| Discord | Interactions + webhooks | $0 service cost | N/A. |
| Embeddings | Local ONNX model in Lambda image | Lambda memory/duration and ECR storage | TF-IDF novelty baseline. |

AWS documents EventBridge Scheduler’s 14M free monthly invocations, SQS’s 1M free monthly requests, and Lambda’s per-request/per-GB-second pricing. [EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/) [SQS pricing](https://aws.amazon.com/sqs/pricing/) [Lambda/S3 pricing](https://aws.amazon.com/s3/pricing/)

**Cost controls are recommendations, not hard constraints:** tag every Terraform resource with `project=disco`; configure AWS Budgets and Cost Anomaly Detection; use lifecycle policies; set Lambda reserved concurrency; and add a `SYSTEM_ENABLED` configuration switch. Avoid NAT Gateway and provisioned concurrency unless a measured requirement justifies them.

## 8. Collaboration, Delivery, and Benchmarks

### Ownership

| Owner | Directories | Deliverables |
|---|---|---|
| Person A — Platform/SWE | `infra/`, `services/command-api/`, `services/dispatcher/`, `services/ingestion/` (runtime shell), `scripts/`, `tests/integration/` | Terraform, queues, state, commands, deployment, telemetry, fault handling. |
| Person B — Data/Quant | `contracts/`, `rust-parser/`, `services/ingestion/` (adapters), `services/ranking/`, `tests/fixtures/`, `reports/` | Adapters, parser, contracts, features, models, event studies, validation. |

Root build configuration (`pyproject.toml`, `Makefile`, `.github/workflows/`) is A's, but B necessarily touches it when adding a Python package or a check stage. Those edits are called out explicitly in the pull request rather than treated as trespass.

No owner edits the other owner’s directory without a PR agreement. Both approve contract changes. Keep `main` protected and require lint, test, contract-validation, and Terraform-validation checks.

### Three-week implementation target

1. **Week 1:** Terraform skeleton; current + daily-index adapters; fixtures; Rust parser CLI; mocked end-to-end Discord alert.
2. **Week 2:** S3/DynamoDB idempotency; Standard SQS/DLQ; production Rust Lambda; parse eligibility policy; novelty baseline; reconciliation dashboard.
3. **Week 3:** point-in-time dataset; walk-forward evaluation; alert evidence cards; failure-injection tests; cost dashboard; benchmark report.

### Resume-grade benchmark protocol

Compare a Python `lxml` baseline with the Rust `quick-xml` parser on a versioned corpus: 25 8-Ks, 25 10-Qs, 25 10-Ks, and 10 malformed files. Run 30 warm repetitions per file on the same ARM64 Lambda memory setting.

Report p50/p95 latency, peak RSS (`/usr/bin/time -v` locally and Lambda `Max Memory Used` in production), throughput, GB-seconds per filing, correctness against golden outputs, malformed-document recovery, and cold-start versus warm behavior. Include corpus SHA, runtime versions, Git SHA, memory allocation, and exact command line. Do not quote a performance improvement until measured.

## 9. Definition of Done

The first credible release ingests all observed SEC index events, reconciles them against the authoritative daily index, stores immutable source artifacts, parses selected high-value filings via Rust, produces reproducible point-in-time ranking records, and sends Discord alerts whose claims can be independently checked from the filing itself.
