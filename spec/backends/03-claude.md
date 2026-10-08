# Claude Backend

## Design Position

The Claude backend adapts the Claude Agent SDK's native conversation and execution behavior. Claude owns its agent loop, tools, configuration, and history. Ordinary execution remains a backend target even though Workspace delegation is excluded from this design.

## Logical Work Boundary

A native conversation maps to a Thread. Input submission, result messages, interrupt behavior, and native idle/turn boundaries must be interpreted together to establish the logical Run boundary. The first `ResultMessage` is not assumed to settle every admitted input when native follow-up work remains.

Additional input can be natively buffered or scheduled into another native Turn without violating ohkit's no-public-queue rule, provided it belongs to the same active Run. Before advertising steering, the adapter must verify admission and completion races and account for every admitted input. Merely writing a user message to the SDK connection is insufficient evidence that ohkit's steering contract has been met.

History resume preserves native conversation continuity within its native scope. It does not restore pending handlers, process resources, or an old active Run. Interrupt acceptance is not terminal evidence. Native permission interactions follow the shared [interaction contract](../execution/02-observation-interaction.md).

## Workspace Exclusion

This backend does not accept a supplied Workspace. Native hooks can control or observe tool execution without establishing a transparent filesystem/process executor replacement. Custom MCP tools are a different tool surface, not a faithful replacement for all native file and shell behavior.

Consequently, this design adds neither a Claude replacement-tool framework nor a claim that disabling built-in tools relocates all native I/O. Callers use Claude's own supported runtime and permission configuration. A future Workspace bridge requires a separately established native execution seam and coverage contract.

## Upstream Basis

The boundary is informed by Claude Agent SDK Python `v0.2.164`, commit `2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf`:

- [Client conversation and response operations](https://github.com/anthropics/claude-agent-sdk-python/blob/2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf/src/claude_agent_sdk/client.py).
- [Native query and control routing](https://github.com/anthropics/claude-agent-sdk-python/blob/2f38c69e1d9fb4aea24f7714cb4a7460dc41d2cf/src/claude_agent_sdk/_internal/query.py).

The source baseline is not a completed adapter validation or a shipped steering-support claim.
