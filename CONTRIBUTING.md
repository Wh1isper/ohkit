# Contributing

## Repository Language

Canonical code, comments, documentation, Issues, pull requests, and commits are written in English. Use Markdown and Mermaid where they clarify a boundary or flow; do not add decorative emoji.

## Setup

Install Git, Python 3.13, and uv. Clone the repository and run `make install` to synchronize `uv.lock` and install pre-commit hooks. Node.js 24 and pnpm 10.30.3 are needed for the documentation website; Node.js also runs repository automation tests. Docker is needed for the pinned actionlint command. None is a Python package build or runtime dependency.

## Workflow

Read [engineering standards](DEVELOPMENT.md) and the owning [specification](spec/README.md). Discuss unresolved product, architecture, security, or compatibility decisions in Issues before treating them as accepted contracts. Routine fixes do not need a separate Issue. Keep implementation, tests, docs, and automation coherent and focused.

Use feature branches and pull requests for changes to `main`. Main permits squash merging only. Use `type(scope): imperative summary` for commit subjects and PR titles; use `!` for an incompatible change and describe impact and migration. Do not invent author attribution. Draft PRs skip code CI; marking ready runs checks.

## Local Validation

| Command                          | Purpose                                                        |
| -------------------------------- | -------------------------------------------------------------- |
| `make install`                   | Locked environment and hooks                                   |
| `make format`                    | File hygiene, Ruff, Markdown formatting                        |
| `make check`                     | Lock, lint, formatting, repository links, typing, dependencies |
| `make test`                      | Package and release-tool tests                                 |
| `make dist-check`                | Build, inspect artifacts, rebuild sdist, isolated install      |
| `make check-all` / `make verify` | All Python gates                                               |
| `make workflow-check`            | GitHub Actions syntax and expressions                          |
| `make automation-test`           | PR overview tests                                              |
| `make docs-build`                | Static documentation, navigation, and internal links           |
| `make docs-serve`                | Local documentation preview                                    |

Choose local checks from actual changed behavior. Run downstream checks when a shared change affects them. Reuse passing checks while relevant inputs are unchanged. CI runs the complete applicable gates. Do not claim unexecuted checks passed or bypass hooks. `make format` operates on tracked files, so newly created files must be staged before the all-files hook pass.

## Documentation Changes

`spec/` records accepted technical contracts, not proposals or progress. `docs/` contains user documentation, explicitly labeled design examples, and runbooks. Keep each fact under one owner and link to it. Start site pages with `title` and `description` front matter; do not repeat the title as a top-level heading. Keep paragraphs on one source line. Use relative Markdown file links between documentation pages and repository URLs for guides outside `docs/`. Update the relevant `docs/**/meta.json` navigation when adding, moving, or removing a page. Format Markdown with `uv run --locked mdformat --number` and run `make docs-build`. See [documentation maintenance](docs/documentation.md) for the isolated `website/` build, preview, Mermaid conventions, and Cloudflare Pages setup. Fumadocs and Next.js produce a static export; no production Node.js service is required.

## Writing Issues and Pull Requests

Open with the concrete user or integrator outcome and the relevant context, not a work log. Explain material trade-offs and compatibility effects. Use a small diagram or table only when clearer than prose. Keep validation evidence concise; GitHub checks own CI status. Follow the PR template and check only verified items. Human review must not be asserted on another person's behalf.

## PR Labels

On opening or marking a PR ready, title-based automation assigns `enhancement`, `bug`, `documentation`, or `chore` if no type label exists, plus `breaking-change` when applicable. Existing type labels are preserved; correct them if scope changes. `chore` and `skip-changelog` omit PRs from release notes unless marked breaking. Do not hide user-visible changes under `chore`. A separate trusted-base workflow publishes a file-level change overview and never executes PR-head code with write permissions.

## Releases

Source versions stay `0.0.0`. Releases are independently versioned for ohkit and use stable `X.Y.Z` or `X.Y.Z-rc.N` tags. A release tag must target a commit with passing CI. See the [release procedure](docs/releasing.md) for Environment setup, artifact validation, immutable tags, and publication. CI configuration does not authorize creating a release.
