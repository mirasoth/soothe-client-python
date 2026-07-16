# Makefile for soothe-client-python
#
# Common developer and release tasks. Run `make help` to list targets.

SHELL := /bin/bash

PKG_NAME    := soothe-client-python
PKG_VERSION := $(shell cat VERSION 2>/dev/null || echo 0.0.0)

.DEFAULT_GOAL := help

.PHONY: help sync sync-dev install clean distclean \
	format format-check lint lint-fix fix \
	test test-unit test-examples test-examples-offline test-integration test-coverage \
	typecheck build pack-check verify \
	publish publish-dry publish-test \
	version-patch version-minor version-major \
	check all

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help: ## Show this help message
	@echo "$(PKG_NAME)@$(PKG_VERSION)"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Install / clean
# ---------------------------------------------------------------------------

sync: ## Sync runtime dependencies with uv
	uv sync
	@echo "✓ Dependencies synced"

sync-dev: ## Sync runtime + dev extras
	uv sync --extra dev
	@echo "✓ Dev dependencies synced"

install: sync-dev ## Alias for sync-dev

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage coverage.xml
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean"

distclean: clean ## Clean plus local .venv (if present)
	rm -rf .venv
	@echo "✓ Distclean"

# ---------------------------------------------------------------------------
# Format / lint
# ---------------------------------------------------------------------------

format: sync-dev ## Format source, tests, and examples with ruff
	uv run ruff format src/ tests/ examples/
	@echo "✓ Formatted"

format-check: sync-dev ## Check formatting (CI)
	uv run ruff format --check src/ tests/ examples/
	@echo "✓ Format check passed"

lint: sync-dev ## Lint with ruff
	uv run ruff check src/ tests/ examples/
	@echo "✓ Lint passed"

lint-fix: sync-dev ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/ examples/
	@echo "✓ Lint fixes applied"

fix: lint-fix format ## lint-fix + format

typecheck: sync-dev ## Run mypy on the package
	uv run mypy src/soothe_client
	@echo "✓ Typecheck passed"

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

test: test-unit test-examples-offline ## Run unit + offline example tests (not live/integration)

test-unit: sync-dev ## Run unit tests
	uv run pytest tests/unit -q
	@echo "✓ Unit tests passed"

test-examples-offline: sync-dev ## Run offline appkit example tests (no daemon)
	uv run pytest examples/appkit -q
	@echo "✓ Offline example tests passed"

EXAMPLE_SCRIPTS := \
	examples/01_hello.py \
	examples/02_stream_turn.py \
	examples/03_text_completion.py \
	examples/04_multi_turn.py \
	examples/05_pool_service.py \
	examples/06_jobs.py

test-examples: ## Run live daemon examples 01–06 (requires soothed at SOOTHE_WS_URL)
	@echo "Requires soothed at $${SOOTHE_WS_URL:-ws://127.0.0.1:8765}"
	@set -euo pipefail; \
	for f in $(EXAMPLE_SCRIPTS); do \
		echo ""; \
		echo "========== $$f =========="; \
		uv run python "$$f"; \
	done
	@echo ""
	@echo "✓ All live examples passed"

test-integration: sync-dev ## Live daemon tests (skip if soothed unreachable)
	uv run pytest tests/integration -v
	@echo "✓ Integration tests finished"

test-coverage: sync-dev ## Unit tests with coverage report
	uv run pytest tests/unit --cov=soothe_client --cov-report=term-missing --cov-report=html
	@echo "✓ Coverage report in htmlcov/"

# ---------------------------------------------------------------------------
# Build / verify / publish
# ---------------------------------------------------------------------------

build: clean sync-dev ## Build sdist + wheel into dist/
	uv build --out-dir dist
	@echo "✓ Built $(PKG_NAME)@$(PKG_VERSION)"
	@ls -la dist/

pack-check: build ## List files that would be published
	@echo ">>> Artifacts for $(PKG_NAME)@$(PKG_VERSION):"
	@ls -la dist/
	@python -c "import tarfile,glob; \
p=glob.glob('dist/*.tar.gz')[0]; \
print('sdist:', p); \
[print(' ', m.name) for m in tarfile.open(p).getmembers() if m.isfile()][:40]"

verify: format-check lint typecheck test build ## Full pre-publish verification
	@echo ""
	@echo "✓ All verification checks passed for $(PKG_NAME)@$(PKG_VERSION)"
	@echo "  Next: make publish-dry"
	@echo "        make publish"

publish-dry: build ## Dry-run PyPI publish (no upload)
	uv publish --dry-run dist/*
	@echo "✓ Dry-run complete"

publish: verify ## Publish to PyPI (requires UV_PUBLISH_TOKEN or trusted publisher)
	@echo ">>> Publishing $(PKG_NAME)@$(PKG_VERSION) to PyPI..."
	uv publish dist/*
	@echo "✓ Published"

publish-test: build ## Publish to TestPyPI
	uv publish dist/* --index-url https://test.pypi.org/simple/
	@echo "✓ Published to TestPyPI"

# ---------------------------------------------------------------------------
# Version bumps (edits VERSION only; commit/tag yourself)
# ---------------------------------------------------------------------------

version-patch: ## Bump patch (x.y.Z)
	@python -c "from pathlib import Path; \
v=Path('VERSION').read_text().strip().split('.'); \
v[2]=str(int(v[2])+1); Path('VERSION').write_text('.'.join(v)+'\n'); \
print('VERSION ->', '.'.join(v))"

version-minor: ## Bump minor (x.Y.0)
	@python -c "from pathlib import Path; \
v=Path('VERSION').read_text().strip().split('.'); \
v[1]=str(int(v[1])+1); v[2]='0'; Path('VERSION').write_text('.'.join(v)+'\n'); \
print('VERSION ->', '.'.join(v))"

version-major: ## Bump major (X.0.0)
	@python -c "from pathlib import Path; \
v=Path('VERSION').read_text().strip().split('.'); \
v[0]=str(int(v[0])+1); v[1]='0'; v[2]='0'; Path('VERSION').write_text('.'.join(v)+'\n'); \
print('VERSION ->', '.'.join(v))"

# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

check: format-check lint typecheck test-unit ## Quick CI-style checks (no build)
	@echo "✓ Check passed"

all: verify ## Alias for verify
