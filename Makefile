.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck deps-check test build dist-check check check-all verify workflow-check automation-test docs-build docs-serve codex-generate codex-check codex-native-test codex-upstream-check claude-native-test acp-native-test installed-test

DOCS_PORT ?= 3000

help: ## List development commands
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the locked Python environment and Git hooks
	uv sync --locked
	uv run --locked pre-commit install

format: ## Apply file hygiene and formatting hooks
	uv run --locked pre-commit run --all-files

lint: ## Run non-mutating Python, Markdown, and repository checks
	uv lock --check
	uv run --locked ruff check --no-fix .
	uv run --locked ruff format --check .
	uv run --locked mdformat --check --number README.md AGENTS.md CONTRIBUTING.md DEVELOPMENT.md MAINTAINERS.md SECURITY.md docs spec .agents .github
	uv run --locked python scripts/check_repository.py

typecheck: ## Type-check package and release tooling
	uv run --locked pyright

deps-check: ## Validate package dependency declarations
	uv run --locked deptry .

test: ## Run package and automation tests
	uv run --locked pytest --junitxml=test-results/pytest.xml

build: ## Build the wheel and source distribution
	uv build --out-dir dist

dist-check: build ## Check metadata, sdist rebuild, and isolated wheel imports
	uv run --locked python scripts/check_distribution.py

workflow-check: ## Validate GitHub Actions with the main repository's actionlint version
	docker run --rm -v "$(CURDIR):/repo" -w /repo rhysd/actionlint:1.7.12 -ignore 'unexpected key "queue" for "concurrency" section'

automation-test: ## Test PR change overview with Node.js (automation only)
	node --test .github/scripts/*.test.cjs

check: lint typecheck deps-check codex-check ## Run Python and repository static checks

check-all: check test dist-check ## Run all Python gates, including packaging

verify: check-all ## Validate this single-package repository

codex-generate: ## Regenerate private wire models from the committed schema (offline)
	uv run --locked python scripts/codex_protocol.py generate

codex-check: ## Check snapshot integrity and byte-identical wire generation (offline)
	uv run --locked python scripts/codex_protocol.py generate --check

codex-native-test: ## Exercise the pinned real Codex against a loopback model
	OHKIT_TEST_NATIVE=1 uv run --locked pytest tests/test_codex_native.py -q --junitxml=test-results/codex-native.xml

claude-native-test: ## Exercise the SDK-bundled Claude against a loopback model
	OHKIT_TEST_NATIVE=1 uv run --locked pytest tests/test_claude_native.py -q --junitxml=test-results/claude-native.xml

acp-native-test: ## Exercise a locked third-party ACP agent against a loopback model
	npm ci --prefix tests/fixtures/acp --ignore-scripts --no-audit --no-fund
	OHKIT_TEST_ACP_NATIVE=1 uv run --locked pytest tests/test_acp_native.py -q --junitxml=test-results/acp-native.xml

installed-test: build ## Run native suites against an isolated wheel installation
	npm ci --prefix tests/fixtures/acp --ignore-scripts --no-audit --no-fund
	uv run --locked python scripts/check_installed.py dist/ohkit-0.0.0-py3-none-any.whl

codex-upstream-check: ## Report latest stable Codex version/schema drift (network)
	uv run --locked python scripts/codex_protocol.py check-upstream

docs-build: ## Build and type-check the static documentation; validate links
	pnpm --dir website install --frozen-lockfile
	pnpm --dir website build
	pnpm --dir website typecheck

docs-serve: ## Preview documentation locally
	pnpm --dir website install --frozen-lockfile
	pnpm --dir website dev --port $(DOCS_PORT)
