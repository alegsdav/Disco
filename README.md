# SignalWatch

SignalWatch is a Discord tool that keeps an eye on new SEC filings and turns the important ones into readable research alerts.

Public companies file documents with the SEC whenever they report earnings, change leadership, announce major events, or disclose other information investors may want to know. There are a lot of these documents every day, and most are not worth stopping everything to read. SignalWatch is being built to collect filings, preserve the original source, and highlight the ones that look unusual or potentially important.

Each alert will link directly to the SEC filing and show the supporting text that caused it to be flagged. The goal is to make alerts useful to investigate, not to tell anyone what to buy or sell.

The project is also a hands-on way to learn how real data systems are built. It uses AWS services to move work through a reliable pipeline, Rust to efficiently parse messy filing documents, and Python to rank events and evaluate whether the ranking methods work on historical data.

## Project status

SignalWatch is in its design and scaffolding stage. The detailed design, proposed technology choices, costs, and implementation plan are in [the PRD](docs/SIGNALWATCH_PRD.md).

## Repository layout

```text
contracts/       Shared data formats between services
docs/            Product and architecture documentation
infra/           Cloud infrastructure definitions
rust-parser/     Filing parser written in Rust
services/        Python services for ingestion, ranking, alerts, and commands
tests/           Test fixtures and automated tests
reports/         Benchmark and evaluation results
```

## Disclaimer

SignalWatch is for educational and research use. It does not provide financial advice or execute trades.
