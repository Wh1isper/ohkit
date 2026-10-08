# Data Conventions

## Canonical Terms

Use one owner and one name for each shared concept. [Thread, Run, and Turn](execution/01-thread-run.md#domain-model) are the execution vocabulary. Native `session` terms remain backend protocol vocabulary; do not add a competing public Session model. [Workspace](workspace/00-overview.md) names supplied I/O, not a conversation or environment registry.

References identify native resources within a backend scope. Handles represent live process-local ownership. Neither a reference nor an identifier grants authority. Native IDs, application IDs, and ohkit Run identity are distinct domains even when encoded as strings.

## Values and Authority

Public Python values use explicit types, immutable dataclass-style records, and discriminated event/result unions where variants have different meaning. Protocols describe small behavioral seams, not a class hierarchy for every native object. Credential material and private provider state do not appear as ordinary event or model-visible data.

Document whether a model is conceptual Python, a supported Python API, or a serialized format. Conceptual examples do not establish wire compatibility. A native Thread reference is not a universal history snapshot or a persistence schema.

Separate operation acceptance, observed execution, terminal outcome, resource cleanup, and caller persistence. Missing data stays unknown; partial observations do not become invented complete state.

## Compatibility Axes

The Python package, native harness, native protocol, and native history format have separate version owners. Do not invent a shared revision counter or assume that upgrading one upgrades the others. [API conventions](api-conventions.md) owns public-surface compatibility; [backend contracts](backends/README.md) own native mappings.
