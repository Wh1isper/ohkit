# Backend Contracts

Backends adapt native harness behavior to [execution](../execution/README.md) and, where supported, [Workspace](../workspace/README.md). The overview establishes common admission rules; each backend document owns its native mapping.

| Document                           | Owns                                                             |
| ---------------------------------- | ---------------------------------------------------------------- |
| [Backend overview](00-overview.md) | Compatibility, capability admission, and implementation evidence |
| [Codex](01-codex.md)               | App-server control and exec-server Workspace bridge              |
| [ACP](02-acp.md)                   | Stable ACP conversation control and client callbacks             |
| [Claude](03-claude.md)             | Agent SDK lifecycle boundary and explicit Workspace exclusion    |

These are design targets, not claims that adapters ship in the bootstrap package. Availability follows implemented and verified behavior, not this catalog.
