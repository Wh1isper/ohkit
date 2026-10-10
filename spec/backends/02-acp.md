# ACP Backend

## Design Position

The ACP backend is a client of an Agent Client Protocol agent. It maps stable ACP conversation control to ohkit execution and supplies optional filesystem and terminal callbacks through Workspace. It does not expose Codex executor messages to ACP or require an ACP provider to implement the entire Codex filesystem surface.

The initial contract targets stable ACP v1. Draft protocol revisions and agent-specific extensions do not silently change the common lifecycle.

## Conversation and Control

A native ACP session maps to a Thread. A `session/prompt` request establishes foreground work; its final response and stop reason provide completion evidence. Session updates describe progress, not independent completion. `session/cancel` requests cancellation; native cleanup and the final prompt outcome remain distinct.

Stable ACP has no general active-steering primitive with ohkit's accepted-input contract. Steering is unavailable by default. A negotiated extension can enable it only with explicit semantics and verification; a concurrent or later prompt is not an implicit substitute.

The adapter owns one agent subprocess and SDK connection per live Thread. History continuation uses stable `session/resume`, or `session/load` when only load is advertised. Replayed history is not new Run output. `session/fork` remains unstable in the supported SDK and is unavailable even when advertised. The initial adapter accepts text inputs only.

Permission requests route to the caller's typed handler. ACP choices use native kind and scope, retaining the exact option ID, label, and `allow_once`, `allow_always`, `reject_once`, or `reject_always` value; an `always` hint does not invent a known session or persistent scope. Only an offered choice can be returned. Missing, failed, or cancelled handlers return the native cancelled outcome.

An ACP prompt has no separate acceptance receipt. Entering a Run admits its one prompt locally; the final prompt response supplies its outcome. Native rejection produces a failed result, while lost response evidence produces unknown. All stable stop reasons other than `cancelled` represent normal native termination and remain available as the result's native status; this does not assert goal fulfillment.

## Workspace Mapping

| Native callback | Workspace projection                                                                   |
| --------------- | -------------------------------------------------------------------------------------- |
| Read text file  | Read bytes, decode strict UTF-8, apply requested line range                            |
| Write text file | Encode UTF-8 and replace contents, creating required parents where supported           |
| Create terminal | Start argv consisting of command followed by args; return an adapter-owned terminal ID |
| Terminal output | Return a retained cumulative text snapshot and truncation state                        |
| Wait for exit   | Observe process exit, independently of final output availability                       |
| Kill            | Request termination while retaining the terminal and its output                        |
| Release         | Terminate if necessary, close resources, and invalidate the terminal ID                |

The ACP adapter uses the session cwd when terminal creation omits cwd. Environment entries overlay the target's base environment. These are explicit ohkit policies, not claims that ACP specifies those defaults. The adapter does not add shell parsing to command and args.

Text file projection preserves line endings and rejects invalid encoding rather than modifying file bytes. Terminal display uses incremental UTF-8 decoding with replacement for invalid bytes. Its output limit is byte-based; leading truncation respects character boundaries. Provider output loss makes truncation observable rather than returning a falsely complete snapshot. Reading output does not consume it.

## Lifetime and Coverage

Callbacks carry native session identity, not an ohkit Run ID. Terminal handles remain valid until release or binding close; foreground prompt completion is not a terminal-release fence. Cancellation keeps callback routing alive for cleanup. Conversation-scoped handles are not all killed merely because one Run ends.

Only implemented callbacks are advertised. ACP agents may use these client capabilities; their presence does not guarantee that every native file or command path is delegated. An application requiring stronger coverage must verify the chosen agent or enforce confinement outside the adapter.

[Workspace](../workspace/00-overview.md) owns paths, target routing, borrowed-provider lifetime, and resource ownership. Native terminal IDs and snapshots remain internal to this backend.

## Upstream Basis

Stable protocol evidence is pinned to `agent-client-protocol` commit `1c2b84c785c923ed283a4e7ea3badb2422596418`:

- [Filesystem callbacks](https://github.com/agentclientprotocol/agent-client-protocol/blob/1c2b84c785c923ed283a4e7ea3badb2422596418/docs/protocol/v1/file-system.mdx).
- [Terminal lifecycle](https://github.com/agentclientprotocol/agent-client-protocol/blob/1c2b84c785c923ed283a4e7ea3badb2422596418/docs/protocol/v1/terminals.mdx).
- [Prompt and cancellation](https://github.com/agentclientprotocol/agent-client-protocol/blob/1c2b84c785c923ed283a4e7ea3badb2422596418/docs/protocol/v1/prompt-turn.mdx).
