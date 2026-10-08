.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck deps-check test build dist-check check check-all verify workflow-check automation-test docs-build docs-serve

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

check: lint typecheck deps-check ## Run Python and repository static checks

check-all: check test dist-check ## Run all Python gates, including packaging

verify: check-all ## Validate this single-package repository

docs-build: ## Build and type-check the static documentation; validate links
	pnpm --dir website install --frozen-lockfile
	pnpm --dir website build
	pnpm --dir website typecheck

docs-serve: ## Preview documentation locally
	pnpm --dir website install --frozen-lockfile
	pnpm --dir website dev --port $(DOCS_PORT)
