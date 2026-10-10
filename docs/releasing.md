---
title: Releasing ohkit
description: Prepare, validate, and publish an authorized Python release.
---

## One-Time Setup

The GitHub Actions Environment is `ohkit-pypi`. Add a PyPI API token as its `PYPI_TOKEN` secret. For a first publication, use a token capable of creating the project; after publication, replace it with an ohkit-scoped token. Do not copy another repository's secrets or commit credentials. Only tags matching `release/ohkit-v*` may deploy to this Environment.

Creating the Environment or storing its secret does not publish anything. Publication starts only when an explicitly authorized release tag is pushed.

## Prepare and Publish

1. Select a reviewed `main` commit with passing CI. Confirm the intended package/version and explicit publication authorization.

2. Keep source `pyproject.toml` and `uv.lock` at `0.0.0`. Use stable `X.Y.Z` or `X.Y.Z-rc.N` with a positive RC number. Optionally add curated notes at `.github/release-notes/ohkit/<version>.md` before tagging.

3. Create and push the tag. For example, only when authorized:

   ```bash
   git tag -a release/ohkit-v0.1.0-rc.1 <validated-commit> -m "ohkit 0.1.0-rc.1"
   git push origin release/ohkit-v0.1.0-rc.1
   ```

4. Monitor the **Release ohkit** workflow. Build injects the version in its checkout, verifies the lock, builds and checks the wheel and sdist, then uploads them. Publish downloads those exact artifacts and uses the Environment token. The final job creates a GitHub Release with matching assets and channel-scoped notes. RC versions become `0.1.0rc1` in Python metadata and are marked prerelease on GitHub.

5. Verify the published PyPI metadata, GitHub Release, and an isolated package install. Source versions remain unchanged.

Release CI does not duplicate the full lint/test suite; tag only a commit whose normal CI has passed. Release tags are immutable. Never retag a published version or overwrite artifacts.

## Retry and Notes

Inspect the outcome before retrying a failed workflow. `uv publish --check-url` reconciles already uploaded artifacts; an existing GitHub Release is left unchanged. Authentication or network errors are failures, not evidence that no release exists. Rerun the original workflow when appropriate; use a new version for changed artifacts.

Stable notes compare with the previous stable ancestor release. RC notes compare with the previous RC for that target, otherwise the previous stable release. The first release uses an honest bootstrap description unless curated notes are supplied. Labels classify merged PRs; direct commits and unlabelled historical PRs use Conventional Commit fallback. `chore` and `skip-changelog` labels omit PRs unless breaking. Curated notes prepend generated notes for later releases.

## Local Rehearsal

In a disposable copy (never the source checkout), run:

```bash
uv run --locked python scripts/prepare-release-version.py ohkit 0.1.0-rc.1
uv lock --check
uv build
uv run --locked python scripts/check_distribution.py
```

Repeat with a stable version from a fresh copy. This tests packaging only and publishes nothing.

For executable consumption checks, use `make installed-test` in the development checkout, or test a rehearsed wheel directly:

```bash
npm ci --prefix tests/fixtures/acp --ignore-scripts --no-audit --no-fund
uv run --locked python scripts/check_installed.py /path/to/ohkit-0.1.0-py3-none-any.whl
```

This creates a temporary consumer environment, installs the wheel and test runner with normally resolved runtime dependencies, and copies only tests, examples, and fixture tooling—not the `ohkit/` source. A test-session assertion verifies imports come from that environment. It exercises Codex and Claude native suites, the locked third-party ACP agent, and deterministic ACP callback/error scenarios. Node.js 24 is needed for the ACP fixture; no production model credentials are used. `OHKIT_CODEX_BINARY` can point to an already verified binary of the documented baseline. Results are written to `test-results/installed-native.xml`.

Before the first runtime release, ensure release notes describe all three backends, their actual capability limits, and the difference from the metadata-only bootstrap. Confirm the private security-reporting contact and maintainer metadata. Successful local rehearsal establishes artifact readiness; select the final reviewed commit and verify its CI before tagging.
