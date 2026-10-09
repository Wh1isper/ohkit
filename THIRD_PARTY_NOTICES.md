# Third-party notices

## OpenAI Codex protocol

The schema snapshot in `protocol/codex/schema.json` is selected from the official OpenAI Codex app-server JSON Schema export. `ohkit/backends/codex/_generated.py` is a Python/Pydantic translation generated from that snapshot, not handwritten OpenAI source. The pinned upstream version and archive/schema checksums are recorded in `protocol/codex/manifest.json`.

Upstream: <https://github.com/openai/codex>. Copyright OpenAI. These derived portions are licensed under Apache-2.0; ohkit's own code remains MIT licensed. The original [Apache License](third-party/codex/LICENSE) and upstream [NOTICE](third-party/codex/NOTICE) are preserved with the distribution. The upstream NOTICE also describes components of Codex itself; ohkit does not bundle the Codex executable or the Ratatui library.

The transformation selects the adapter's request, response, and notification schemas and their referenced definitions, combines them without field rewrites, and generates private Python classes with snake-case attributes and native JSON aliases. Generated classes inherit ohkit's strict validation and additive-field preservation policy. Maintenance instructions are in [Codex protocol maintenance](docs/codex-protocol.md).
