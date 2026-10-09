---
title: Codex protocol maintenance
description: Reproduce private wire models, detect upstream drift, and review a native compatibility upgrade.
---

## One source, three boundaries

`protocol/codex/manifest.json` owns the tested Codex version, official Linux archive SHA-256, and selected schema SHA-256. The adapter's `Codex.tested_native_version` and the native test fixture derive their version from this baseline. The selected schema is checked in alongside the generated Python models; installing, importing, and building ohkit never downloads Codex or runs a generator.

- **Upstream owns wire fields.** `scripts/codex_protocol.py` exports JSON Schema with the exact native `app-server generate-json-schema --experimental` command. Its small method/type maps select the implemented surface and transitive definitions; they do not redefine fields. Request/notification method associations are checked against native envelopes. Request/response pairing is explicit because the export does not encode it.
- **Generated models own structural validation.** Private Pydantic v2 models retain native aliases, required/nullable distinctions, defaults, unions, and additive fields. Known types are strict; unknown enum variants are not silently accepted. Serialization excludes unset defaults but preserves explicit null. Public Thread options use `None` to inherit native configuration and therefore omit those parameters. Native decoding accepts only wire aliases, not Python attribute names. Approval grants and opaque tool payloads retain the original validated JSON instead of reserializing models: an unknown field colliding with a Python attribute must not acquire a new wire meaning or inject defaults.
- **The adapter owns behavior.** Typed RPC wrappers, Run ownership, steering evidence, offered-choice checks, handler lifetime, and failure/unknown-outcome handling remain handwritten. Schema validity alone does not establish authorization, foreground attribution, or semantic compatibility. Generated models are not a public API or a dependency of shared dataclass values.

The generator version is pinned in `pyproject.toml` and `uv.lock`; generation flags live only in the maintenance script. Do not edit generated files or patch individual wire fields. Add a needed native method/type to the selection maps and regenerate. The current generator reports unsupported Rust integer format annotations (`uint`, `uint16`, `uint32`, `uint64`); JSON Schema numeric bounds are retained, but Rust-width annotations alone are not range validators. This is not a complete JSON Schema validation engine.

## Routine checks

```bash
make codex-generate       # Offline regeneration from the checked-in snapshot
make codex-check          # Offline snapshot integrity and byte-for-byte generation check
make check-all            # Includes codex-check, strict typing, tests, and artifact checks
make codex-native-test    # Exact pinned executable + deterministic localhost model
make codex-upstream-check # Network: compare the latest stable native release
```

The native fixture uses the same checksum-verifying download helper as maintenance. On another supported platform, set `OHKIT_CODEX_BINARY=/absolute/path/to/codex` to an exact-version executable. It still checks the native version. Tests isolate native home/configuration and use a loopback model, not model-provider credentials. CI runs native tests in a separate job so network/executable failures are distinct from offline package checks.

## Daily upstream signal

The **Codex upstream** GitHub Action runs daily at **07:23 UTC** and supports manual dispatch. It has read-only repository permissions. It queries OpenAI's latest stable GitHub release, verifies the official asset checksum, exports the same selected schema, and compares both version and definitions against the tested baseline. It does not modify the baseline, create Issues/PRs, or upgrade dependencies.

The report is written to the Actions step summary and retained in the `codex-upstream` artifact for 30 days. Locally it appears under `test-results/codex-upstream/`: `report.md`, machine-readable `result.json`, and, when comparison completes, `schema.json` and `schema.diff`.

| Script exit | Status         | Meaning and response                                                                                                                                                  |
| ----------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0           | `current`      | Version and selected schema match. This is not a live-provider test.                                                                                                  |
| 1           | `drift`        | Version changed, selected definitions differ, or a selected native method/type disappeared. Review before upgrading; a version-only change can still affect behavior. |
| 2           | `inconclusive` | Network, download, checksum, or export failed. Fix or rerun the check; do not treat it as compatibility evidence.                                                     |

Both nonzero statuses fail the Action so drift cannot become a silent green check. `make` itself may return its generic failure exit code; use the script directly when automating the 0/1/2 distinction. Schedule activation requires this workflow on the default branch. GitHub may delay scheduled jobs or disable them for inactivity; use manual dispatch when needed and configure your GitHub Actions failure notifications. This is a maintenance signal, not a guaranteed-time alert service.

## Reviewed upgrade

Choose a stable `X.Y.Z` release explicitly:

```bash
uv run --locked python scripts/codex_protocol.py update --version X.Y.Z
# Or use an exact-version binary already installed for your platform:
uv run --locked python scripts/codex_protocol.py update --version X.Y.Z --binary /path/to/codex
make check-all codex-native-test
make workflow-check automation-test
make docs-build
```

The update prepares the export, generated code, version constant, and upstream license/notice before replacing the baseline files. Download or generation failure does not publish a partial new baseline. Inspect `git diff` after any interrupted filesystem write; this is not a transactional repository update.

Review the snapshot and generated diff together. Inspect required/nullability/default changes, enum additions, input correlation, approval decisions, and terminal semantics. Adapt the thin runtime mappings and controlled fixtures where needed; add regression tests rather than loosening validation until tests pass. Update the compatibility statement and version-specific source evidence in the [Codex guide](codex.md) when changing the baseline. Keep a version-sensitive contract tied to evidence, not a blind tag substitution.

Commit the manifest, snapshot, generated models/version, upstream license/notice, adapter/tests, and documentation as one reviewed change. The [third-party notices](https://github.com/Wh1isper/ohkit/blob/main/THIRD_PARTY_NOTICES.md) describe the Apache-2.0-derived portions; wheel and sdist checks preserve their attribution. A pure Python wheel rebuild uses only committed generated code, not the development schema exporter. Merge only after review and CI; publication remains the separate [release procedure](releasing.md).
