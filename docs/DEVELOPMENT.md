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

`make check` installs only the locked Python environment and Terraform provider when they are not already cached, then runs Python linting and type checks, Rust formatting/lints/tests, Terraform formatting/validation, and fixture hash verification.

The fixture verifier expects `tests/fixtures/manifest.json` when B1 lands. Its stable format is:

```json
{
  "files": [
    {"path": "sample/filing.txt", "sha256": "<lowercase SHA-256>"}
  ]
}
```

Until that manifest exists, the check succeeds without verifying fixtures. It does not download SEC fixtures or contact AWS.

## Pull requests

Keep each pull request scoped to one roadmap phase or contract change. Run `make check`, describe behavior and limits, and include tests for changed behavior. Contract changes require both owners and must follow the compatibility procedure in `docs/ROADMAP.md`.

Repository administrators must protect `main` and require the `check` workflow before merging; GitHub branch protection cannot be configured from this repository.
