# API Conventions

## Public Surface

The target execution API is asynchronous and Python-first: concrete backend contexts, live Thread and Run objects, asynchronous event iteration, typed values, and typed interaction handlers. [Execution architecture](execution/00-overview.md) owns the primary usage shape. Blocking wrappers, a service wire API, a backend registry, and a serialized agent-definition language are not part of the initial boundary.

The bootstrap exports only `ohkit.__version__`. Specifications and conceptual examples do not advertise unimplemented imports. Each implemented public behavior requires its owning contract and observable tests.

Use upstream public primitives where they already own semantics. Keep native settings in typed backend-specific options; do not use an untyped universal settings bag to conceal incompatible behavior. Shared types and Workspace do not depend on a13n or a particular backend SDK. Backend SDK dependencies belong to optional backend integrations.

## Failure and Compatibility

Known rejection, unsupported behavior, native execution failure, unknown external outcome, and cleanup failure remain distinguishable. Failures after possible side effects do not imply rollback. Retrying mutations or launching replacement work requires established safe native semantics or caller reconciliation, not a generic retry policy.

Capability advertisement reflects the configured backend and provider, not merely the presence of a method. Explicitly requested unsupported behavior fails rather than silently changing lifecycle, authority, or execution target.

Public Python API compatibility and native compatibility are documented independently. Incompatible changes require the owning contract, tests, and migration explanation. Pre-alpha status permits iteration but does not justify undocumented semantic changes. Native additions are not automatically cross-backend guarantees.
