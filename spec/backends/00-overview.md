# Backend Architecture

## Design Position

A backend translates a native harness into ohkit's execution model. It does not replace the harness with an ohkit agent loop. The adapter owns protocol correlation, feature negotiation, lifecycle mapping, and any native Workspace bridge.

A shared API does not imply identical backend capabilities. Ordinary execution, active steering, history resume, fork, live questions, and Workspace delegation are independently supported behaviors. The configured native version, mode, and supplied provider determine availability.

## Backend Boundaries

| Backend | Control boundary               | Workspace boundary                          | Important limitation                                           |
| ------- | ------------------------------ | ------------------------------------------- | -------------------------------------------------------------- |
| Codex   | App-server requests and events | Application-hosted ohkit exec-server bridge | Versioned executor requirements exceed file read/write alone   |
| ACP     | Stable ACP client connection   | Client filesystem and terminal callbacks    | Agent use of callbacks is not universal I/O interception       |
| Claude  | Claude Agent SDK               | No Workspace bridge in this design          | Native hooks do not establish transparent executor replacement |

The Workspace interface does not import any of these protocols. Native libraries are backend-specific dependencies, isolated from the shared values and extension seams. ohkit's wheel contains Python code and does not require a Rust build. A backend SDK dependency may supply its native executable; this does not make that executable or its agent loop an ohkit implementation.

## Admission and Compatibility

Before accepting work, the adapter checks the selected mode and known requirements. Explicitly requested unsupported behavior fails; no silent steering-to-new-prompt conversion, remote-to-local execution fallback, or weaker sandbox mode is permitted. A requirement encountered only in a later native request is checked before that operation executes.

Each adapter declares its tested native version range and relevant feature assumptions when implemented. Optional protocol fields do not imply support merely because a parser accepts them. Unknown native methods, enum values, or terminal semantics must not become fabricated success. Native protocol version, Python package version, and native history format are independent compatibility axes.

Backend-specific options use typed backend-owned values or upstream types when appropriate. There is no universal untyped settings bag or promise that one backend's policy can be reproduced by another.

## Completion Evidence

An adapter establishes which native facts end a logical Run and how accepted in-flight input is settled. A socket closing, one model response, one tool result, or an arbitrary idle interval is not a substitute for that contract. Native background resources have their own ownership and completion boundaries.

Lost submission acknowledgement or connection failure after possible effects is reported as uncertain. Automatic replay is allowed only where the native operation has established safe retry semantics; a generic reconnect loop is not an execution recovery contract.

## Verification Boundary

Support claims require observable tests of the advertised behavior. A native integration test with a deterministic model isolates protocol and tool-routing behavior; it is not proof of a real model, production provider, or every native mode. Source inspection establishes a candidate mapping, not runtime compatibility.

For Workspace integration, evidence must cover selected-target routing, faithful file/process semantics, cleanup, and rejection of unsupported requirements. For steering, it must cover the completion race and accepted-input accounting. Where evidence is incomplete, capability availability remains limited rather than expanding the common contract speculatively.
