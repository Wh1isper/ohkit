# Engineering Standards

## Code Quality and Design

Read the relevant code, contracts, and tests before proposing a change. Prefer simple, maintainable implementations and one owner for shared behavior. Fix causes rather than hiding symptoms. Do not add speculative abstraction, compatibility shims, configuration, or defensive layers without a concrete requirement. Keep external primitives when they already own the semantics.

Separate observations from durable facts and execution acceptance from completion. State failures and unknown outcomes explicitly at public boundaries. Never log credentials or infer authorization from a successful connection. Keep unrelated changes out of the diff.

## Python

Python 3.13 is the minimum supported interpreter. Use uv and the committed lockfile, Ruff formatting and linting, Pyright, and function-style pytest tests. Prefer explicit `isinstance` checks over indirect type inference. Add type annotations at public and cross-module boundaries; include the `py.typed` marker. Prefer focused tests of observable behavior over mocks of implementation details.

Runtime dependencies belong in `[project.dependencies]`; developer tools belong in the `dev` group. Adding a dependency requires a concrete use case. A pure Python build must not require Node.js, Rust, or a frontend bundle. Automation-only Node scripts do not become runtime dependencies.

## Naming

Use `ohkit` for the repository, distribution, and Python import. Use domain names rather than host-specific plumbing in public interfaces. Thread, Run, and Turn are the shared vocabulary; do not introduce Session as a competing public concept. This vocabulary does not establish unimplemented schemas or lifecycle guarantees.

## Automation

GitHub-owned actions use readable major-version tags. Workflows default to read-only permissions; grant write permissions only to the jobs that need them. Privileged PR automation may read metadata and trusted base scripts, not execute untrusted head code. Release credentials are restricted to the publication Environment. Reuse the release version parser and notes generator rather than maintaining separate interpretations.

## Compatibility

Pre-alpha status is not an excuse for undocumented incompatible behavior. Once an API is implemented, keep its accepted contract and tests together and describe incompatible changes and migration in the PR. Until then, do not advertise backend support or invent placeholder APIs.
