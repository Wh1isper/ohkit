# API Conventions

The bootstrap public surface exports only `ohkit.__version__`, derived from installed distribution metadata. It exposes no agent execution or backend API. Future public behavior requires an accepted owning contract, implementation, and observable tests together; backend internals do not automatically become cross-provider guarantees.

Use upstream public primitives where they already own semantics. Introduce shared abstractions only for established cross-provider requirements. Public failures must distinguish known failure from unknown outcome when external side effects are possible. Compatibility and migration implications belong in the owning API contract and release notes.
