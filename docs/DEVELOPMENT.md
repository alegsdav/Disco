# Development

## Prerequisites

- GNU Make
- [uv](https://docs.astral.sh/uv/) 0.7.18
- Rust 1.88.0 (installed automatically by `rustup` from `rust-toolchain.toml`)
- Terraform 1.12.2

## Validate the repository

Run the same command locally and in CI:

```sh
make check
```

`make check` installs only the locked Python environment and Terraform provider when they are not already cached, then runs, in order:

| Target | What it checks |
|---|---|
| `python-check` | `ruff` lint and `mypy --strict` |
| `contracts-check` | `contracts/schemas/*.json` still match the Pydantic models |
| `test` | `pytest` — contract validation across every example payload |
| `rust-check` | `cargo fmt --check`, `clippy -D warnings`, `cargo test` |
| `terraform-check` | `terraform init -backend=false`, `fmt -check`, `validate` |
| `fixture-hashes` | SHA-256 of every file in `tests/fixtures/manifest.json` |

It does not download SEC fixtures, contact AWS, or reach the network beyond package installs.

## Regeneration targets

These write files and are deliberately outside `make check`:

```sh
make contracts   # regenerate contracts/schemas/ from the Pydantic models
make fixtures    # re-download the fixture corpus (needs DISCO_SEC_USER_AGENT)
```

If `contracts-check` fails, run `make contracts` and commit the result. See
[contracts/README.md](../contracts/README.md) for the compatibility rule that
governs when a schema may change at all.

## Fixtures

The corpus in `tests/fixtures/` is committed — 23 files, 4.5 MB — so tests run
offline. `manifest.json` records `path` and `sha256` for each, plus provenance
the verifier ignores. See [tests/fixtures/README.md](../tests/fixtures/README.md).

## Pull requests

Keep each pull request scoped to one roadmap phase or contract change. Run `make check`, describe behavior and limits, and include tests for changed behavior. Contract changes require both owners and must follow the compatibility procedure in `docs/ROADMAP.md`.

Repository administrators must protect `main` and require the `check` workflow before merging; GitHub branch protection cannot be configured from this repository.
