---
title: Codex protocol maintenance
description: Reproduce private wire models, test native upstream regressions, and review compatibility upgrades.
---

## One source, three boundaries

`protocol/codex/manifest.json` owns the tested Codex version, official Linux archive SHA-256, and selected schema SHA-256. The adapter's `Codex.tested_native_version` and the native test fixture derive their version from this baseline. The selected schema is checked in alongside the generated Python models; installing, importing, and building ohkit never downloads Codex or runs a generator.

- **Upstream owns wire fields.** `scripts/codex_protocol.py` exports JSON Schema with the exact native `app-server generate-json-schema --experimental` command. Its small method/type maps select the implemented surface and transitive definitions; they do not redefine fields. Request/notification method associations are checked against native envelopes. Request/response pairing is explicit because the export does not encode it.
- **Generated models own structural validation.** Private Pydantic v2 models retain native aliases, required/nullable distinctions, defaults, unions, and additive fields. Known types are strict; unknown enum variants are not silently accepted. Serialization excludes unset defaults but preserves explicit null. Public Thread options use `None` to inherit native configuration and therefore omit those parameters. Native decoding accepts only wire aliases, not Python attribute names. Approval grants and opaque tool payloads retain the original validated JSON instead of reserializing models: an unknown field colliding with a Python attribute must not acquire a new wire meaning or inject defaults.
- **The adapter owns behavior.** Typed RPC wrappers, Run ownership, steering evidence, offered-choice checks, handler lifetime, and failure/unknown-outcome handling remain handwritten. Schema validity alone does not establish authorization, foreground attribution, or semantic compatibility. Generated models are not a public API or a dependency of shared dataclass values.

The generator version is pinned in `pyproject.toml` and `uv.lock`; generation flags live only in the maintenance script. Do not edit generated files or patch individual wire fields. Add a needed native method/type to the selection maps and regenerate. The current generator reports unsupported Rust integer format annotations (`uint`, `uint16`, `uint32`, `uint64`); JSON Schema numeric bounds are retained, but Rust-width annotations alone are not range validators. This is not a complete JSON Schema validation engine.

## Executor protocol maintenance

The same native baseline covers external execution, but app-server schema export does **not** export exec-server messages. `ohkit/backends/codex/_exec_wire.py` is a deliberately small hand-maintained ingress model set, pinned to [exec-server protocol source](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/exec-server-protocol/src/protocol.rs). It rejects unknown operation requirements and preserves native aliases. Generated control models separately include `environment/add` and `environment/status`; do not add executor messages to the control ServerRequest map.

During a baseline upgrade, inspect executor defaults and behavior as well as shapes: file URI conversion, follow/recursive/force defaults, copy semantics, missing-file codes, environment policy, process output/exit/closed ordering, write deduplication, and optional capability requirements. Update the selected ingress models and real provider tests together. The bridge does not advertise unimplemented optional features or recover live executor sessions. Its [supported modes](workspace.md) remain narrower than the full native protocol.

## Routine checks

```bash
make codex-generate       # Offline regeneration from the checked-in snapshot
make codex-check          # Offline snapshot integrity and byte-for-byte generation check
make check-all            # Includes codex-check, strict typing, tests, and artifact checks
make codex-native-test    # Exact pinned executable + deterministic localhost model
make codex-upstream-check # Linux x86_64: test baseline and latest stable native release
```

The native fixture uses the same checksum-verifying download helper as maintenance. On another supported platform, set `OHKIT_CODEX_BINARY=/absolute/path/to/codex` to an exact-version executable. It still checks the native version. Tests isolate native home/configuration and use a loopback model, not model-provider credentials. CI runs native tests in a separate job so network/executable failures are distinct from offline package checks.

## Daily native regression check

The **Codex upstream** GitHub Action runs daily at **07:23 UTC** and supports manual dispatch with read-only repository permissions. It resolves OpenAI's latest stable GitHub release once, verifies official archive checksums, and runs the **same unchanged adapter, generated models, and native test suite** against the pinned baseline and the candidate executable. When both versions and archive digests match, one run supplies both results. The check never regenerates models or updates the manifest: testing after regeneration would answer a different question.

The baseline is a control for fixture or environment failures. Both runs must report the same nonempty test-case set without skipped tests or setup/teardown errors. The fixture checks each executable's exact expected version. Each suite has a five-minute deadline; expiry terminates its pytest/native process group and is inconclusive, not automatically an upstream regression. `OHKIT_CODEX_TEST_VERSION` is a maintenance-only fixture override requiring an explicit `OHKIT_CODEX_BINARY`; it does not relax adapter validation or change `Codex.tested_native_version`.

| Script exit | Status         | Meaning and response                                                                                                                                                                                      |
| ----------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0           | `passed`       | Baseline and candidate pass the covered native scenarios. Version/schema changes alone stay green.                                                                                                        |
| 1           | `regression`   | Baseline passes, candidate has test failures, and case coverage matches. Inspect the failing cases and logs before attributing the cause to Codex or the adapter.                                         |
| 2           | `inconclusive` | No healthy control, download/checksum failure, skipped/errored or mismatched cases, timeout, missing report, or pytest execution failure. Repair/rerun the check; this is not an incompatibility verdict. |

The workflow fails for a regression or an inconclusive **check**, not for a new version or schema drift. `make` may return its generic failure exit code; use the script directly for the 0/1/2 distinction. The Actions step summary and 30-day `codex-upstream` artifact retain `report.md`, machine-readable `result.json`, baseline/candidate `pytest.log` and `junit.xml`, and optional `schema.json`/`schema.diff`. Locally these live under `test-results/codex-upstream/`. Reused native results are identified in the summary and only have baseline logs. Schema comparison failure is visible as `schema: unavailable` but does not override completed native evidence.

### What this evidence does and does not establish

The native suite exercises initialization, thread start/resume/fork, streaming and usage, active steering consumed by a subsequent model request, interrupt and terminal settlement, real command accept/cancel effects, typed questions, and stdio/WebSocket ownership. It also exercises selected Workspace startup instructions, real file patching and commands, external readiness, cancellation, and endpoint reuse. It uses a deterministic localhost model, not authenticated live-provider behavior. It is a regression gate for these paths, **not a proof that every upstream message or configuration is compatible**. Native file/permission approval variants and other unexercised features still require targeted tests and source review when changed.

The official [app-server documentation](https://developers.openai.com/codex/app-server) describes generated schemas as specific to the executable version and gates experimental fields through `experimentalApi`; it does not make our strict consumer automatically forward-compatible. Optional fields, enum/union additions, removed fields, and changed runtime ordering have different effects. In particular, an added enum value may fail an existing strict decoder even while ordinary native tests pass. Schema diff therefore remains informational review evidence, never an automatic compatibility verdict. Do not build a second general-purpose schema compatibility engine or accept unknown decision/terminal variants merely to obtain a green check.

Schedule activation requires the workflow on the default branch. GitHub may delay scheduled jobs or disable them for inactivity; use manual dispatch when needed and configure Actions failure notifications. This is not a guaranteed-time alert service.

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
