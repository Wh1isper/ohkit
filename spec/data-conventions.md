# Data Conventions

Use explicit domain names and one owner for each shared concept. Thread, Run, and Turn are the shared execution vocabulary; no execution schema or persistence contract is established by this bootstrap. Do not introduce a public Session synonym.

When adding a data contract, document types, authority, identity, lifecycle, compatibility, and whether it is conceptual or serialized. Separate process-local observations from durable state and operation acceptance from completion. Do not expose credentials or private provider state as ordinary model-visible data.
