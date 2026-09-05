UV ?= uv
CARGO ?= cargo
TERRAFORM ?= terraform

.PHONY: bootstrap check python-check contracts-check test rust-check terraform-check \
	fixture-hashes contracts fixtures

bootstrap:
	$(UV) sync --locked --all-packages --group dev

check: python-check contracts-check test rust-check terraform-check fixture-hashes

python-check:
	$(UV) run ruff check .
	$(UV) run mypy

contracts-check:
	$(UV) run python -m disco_contracts.export --check

test:
	$(UV) run pytest

rust-check:
	$(CARGO) fmt --manifest-path rust-parser/Cargo.toml --all -- --check
	$(CARGO) clippy --manifest-path rust-parser/Cargo.toml --all-targets -- -D warnings
	$(CARGO) test --manifest-path rust-parser/Cargo.toml

terraform-check:
	$(TERRAFORM) -chdir=infra init -backend=false -lockfile=readonly
	$(TERRAFORM) -chdir=infra fmt -check -recursive
	$(TERRAFORM) -chdir=infra validate

fixture-hashes:
	$(UV) run python scripts/verify_fixture_hashes.py

# --- Regeneration targets. Not part of `check`; they write files. ---

contracts:
	$(UV) run python -m disco_contracts.export --write

# Requires DISCO_SEC_USER_AGENT and network access to sec.gov.
fixtures:
	$(UV) run python tests/fixtures/tools/build_corpus.py
