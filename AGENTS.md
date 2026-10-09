# Repository Guide

ohkit is an independent, pure Python programming interface for agent harnesses. Typed async execution and Codex app-server control are implemented; Workspace I/O and other backend adapters remain specification-only. Read the owning implementation and compatibility documentation rather than treating all accepted target contracts as available features.

## Sources of Truth

- [CONTRIBUTING.md](CONTRIBUTING.md) owns setup, contribution workflow, validation, and releases.
- [DEVELOPMENT.md](DEVELOPMENT.md) owns code quality and naming.
- [spec/README.md](spec/README.md) indexes accepted contracts; [Repository Model](spec/repository-model.md) owns repository boundaries.
- [docs/index.md](docs/index.md) indexes user and operator documentation. `docs/**/meta.json` owns site navigation; `website/` builds the static Fumadocs site; [documentation maintenance](docs/documentation.md) owns build and deployment.
- [MAINTAINERS.md](MAINTAINERS.md) owns reviewer routing.

Read relevant contracts, implementation, and tests before changing a surface. Write canonical content in English. Skills summarize workflows; they do not grant authority or replace the owning documents.

## Scope and Authorization

Carry requested implementation through proportionate validation. Ask only when missing information materially affects correctness, scope, or authorization. An audit is read-only unless fixes are requested. Editing does not authorize commits, pushes, GitHub writes, publication, or destructive operations. Preserve unrelated work and secrets; never bypass denied operations.

Keep material unresolved design decisions in Issues, not accepted specifications. Creating an Issue requires authorization. Use scoped English Conventional Commits and the repository PR template. Keep one coherent implementation mainline; use independent review for material boundary, security, persistence, concurrency, or recovery changes, not as a ritual before every commit.

## Package and Release Boundaries

The repository, distribution, and import are `ohkit`. Python 3.13 and `uv` own the package toolchain. There is no dependency on Agent Foundation, Harness, or Pydantic AI. Source version stays `0.0.0`; `release/ohkit-vX.Y.Z` or `release/ohkit-vX.Y.Z-rc.N` injects the version only in the release checkout. Read [releasing](docs/releasing.md) before publication changes. Never put credentials in the repository.

## Validation

Use focused tests during development and `make check-all` for package-wide changes. `make verify` is the same single-package gate, not an impact-routing system. Workflow changes additionally use `make workflow-check` and `make automation-test`. Reuse successful checks when their inputs remain unchanged. Report actual results and unavailable checks accurately.
