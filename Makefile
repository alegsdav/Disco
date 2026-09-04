UV ?= uv
CARGO ?= cargo
TERRAFORM ?= terraform

.PHONY: bootstrap check python-check rust-check terraform-check fixture-hashes

bootstrap:
	$(UV) sync --locked --all-packages --group dev

check: python-check rust-check terraform-check fixture-hashes

python-check:
	$(UV) run ruff check .
	$(UV) run mypy

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
