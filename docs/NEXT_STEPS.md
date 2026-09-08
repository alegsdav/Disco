# A2 and B2 handoff

Both owners approved B1's contracts on 2026-09-07. See [G1_REVIEW.md](G1_REVIEW.md)
for receiving evidence and final merge status. Start new work from updated main
after B1 merges; keep A2 and B2 in separate branches and review requests.

## Person A: A2 infrastructure skeleton

Suggested branch: `a2-infrastructure-skeleton`.

Build Terraform under `infra/` using the [PRD](DISCO_PRD.md) resource and key
design. First deliver reviewable configuration, then exercise it in development.

- Versioned raw and parsed S3 storage.
- DynamoDB on-demand state with separate development and production state.
- Standard queues `filing-discovery`, `parse-jobs`, `alert-delivery`, each with
  a dead-letter queue and redrive policy.
- Scheduler rules, narrowly scoped Lambda permissions, project tags, budgets,
  cost anomaly detection, and the `SYSTEM_ENABLED` configuration item.
- A minimal Lambda proving packaging, permissions, and structured logging.

Before applying: establish the intended AWS account, region, state backend,
budget amount and notification destination. Record these deployment choices;
do not invent an account or recipient. Verify apply/destroy in dev leaves no
orphans, logs reach CloudWatch, and the budget alarm can be exercised.

A2 alone does not open G2. Next, A3 supplies the shared SEC HTTP client, identity,
storage, idempotency, and queue helpers with a local mode. B must exercise those
helpers before G2 closes.

## Person B: B2 offline daily-index reader

Suggested branch: `b2-daily-index-offline`.

Start the offline part now; live collection and reconciliation wait for G2.

- Add saved daily master-index inputs with provenance and expected rows. B1's
  filing documents are not daily-index fixtures.
- Implement and test index parsing under `services/ingestion/`: preserve every
  supported index row, including unfamiliar form names; handle headers, blank
  lines, and malformed rows explicitly without silently dropping data.
- Build contract-valid discovery messages using an injected identity helper and
  observation clock. A3 owns production identity derivation and HTTP access;
  use the frozen contract definition for test doubles, not a second production
  identity implementation.
- Document the daily index's date-only filing information versus the contract's
  UTC timestamp. Agree and test an explicit convention before emitting messages;
  do not pretend a date is a known SEC acceptance time.
- Prove expected row counts offline. After G2, connect A3's helpers, add the manual
  live command and per-date reconciliation record, and prove a second run creates
  zero new events.

Offline tests cannot establish live coverage or durable deduplication. Those are
required before calling B2 complete. Build B3's fast poller after this safety net.

## Checks and documentation for both lanes

Run `make check`; it now includes A's independent message consumer. Update
[DEVELOPMENT.md](DEVELOPMENT.md) for technical instructions and
[DEVELOPMENT_BABY.md](DEVELOPMENT_BABY.md) for plain-language progress in each
code review. Keep work within the roadmap's ownership boundaries. Changes to
the frozen contracts require both approvals and the compatibility procedure.
