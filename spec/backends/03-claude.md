# Claude Backend

## Design Position

The Claude backend adapts the Claude Agent SDK's native conversation and execution behavior. Claude owns its agent loop, tools, configuration, and history. Ordinary execution is implemented while Workspace delegation remains excluded from this design.

## Logical Work Boundary

A native conversation maps to a Thread. Input submission, result messages, interrupt behavior, and native idle/turn boundaries must be interpreted together to establish the logical Run boundary. The first `ResultMessage` is not assumed to settle every admitted input when native follow-up work remains.

Additional input can be natively buffered or scheduled into another native Turn without violating ohkit's no-public-queue rule, provided it belongs to the same active Run. Before advertising steering, the adapter must verify admission and completion races and account for every admitted input. Merely writing a user message to the SDK connection is insufficient evidence that ohkit's steering contract has been met.

History resume preserves native conversation continuity within its native scope. It does not restore pending handlers, process resources, or an old active Run. Interrupt acceptance is not terminal evidence. Native permission interactions follow the shared [interaction contract](../execution/02-observation-interaction.md).

## SDK Ownership and Supported Surface

The adapter allocates a native session UUID and owns one SDK client/process per Run. It passes a single-message asynchronous input iterable, keeps native permission routing configured, and consumes the SDK's message stream to EOF. The SDK owns background-agent accounting, session-state interpretation, and input closure. Multiple native result messages can therefore belong to the same Run. The final result is published only after SDK disconnection; forced cleanup without complete evidence is unknown, not successful completion.

Later Runs resume native history in a new process. Idle Threads do not retain native process resources. Creating or reopening a Thread selects history locally; the next Run validates that selection through the native executable. Native refusal is not replaced with empty history. This is history continuity, not live-process continuity.

The initial adapter accepts text and projects complete assistant message blocks. Child-agent messages retain native attribution rather than entering the parent's final answer. Native results remain observable; final usage is the last native result's reported usage, not a fabricated sum of turn and message statistics. An earlier failed or aborted result is not erased by a later normal result. Explicit aborted terminal reasons and matching SDK error results followed by native exit code 1 retain cancellation or failure evidence when no subsequent work was observed. EOF after unfinished main-thread work is unknown even when an earlier Turn supplied a result.

Steering and fork remain unavailable. Native SDK options configure tools, models, hooks, and permissions, while ohkit owns history selection, its approval callback, input format, and output format. Conflicting options are rejected. Approval handlers offer only action-scoped allow/deny; native permission suggestions are retained as data and are not automatically applied. Native callback cancellation withdraws the request without sending a stale response.

## Workspace Exclusion

This backend does not accept a supplied Workspace. Native hooks can control or observe tool execution without establishing a transparent filesystem/process executor replacement. Custom MCP tools are a different tool surface, not a faithful replacement for all native file and shell behavior.

Consequently, this design adds neither a Claude replacement-tool framework nor a claim that disabling built-in tools relocates all native I/O. Callers use Claude's own supported runtime and permission configuration. A future Workspace bridge requires a separately established native execution seam and coverage contract.

## Upstream Basis

The boundary is informed by Claude Agent SDK Python `v0.2.164`, commit `2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf`:

- [Client conversation and response operations](https://github.com/anthropics/claude-agent-sdk-python/blob/2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf/src/claude_agent_sdk/client.py).
- [Native query and control routing](https://github.com/anthropics/claude-agent-sdk-python/blob/2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf/src/claude_agent_sdk/_internal/query.py).

The source baseline is not a completed adapter validation or a shipped steering-support claim.
