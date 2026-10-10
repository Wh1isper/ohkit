# Backend Contracts

Backends adapt native harness behavior to [execution](../execution/README.md) and, where supported, [Workspace](../workspace/README.md). The overview establishes common admission rules; each backend document owns its native mapping.

| Document                           | Owns                                                             |
| ---------------------------------- | ---------------------------------------------------------------- |
| [Backend overview](00-overview.md) | Compatibility, capability admission, and implementation evidence |
| [Codex](01-codex.md)               | App-server control and exec-server Workspace bridge              |
| [ACP](02-acp.md)                   | Stable ACP conversation control and client callbacks             |
| [Claude](03-claude.md)             | Agent SDK lifecycle boundary and explicit Workspace exclusion    |

Codex control and its hosted Workspace bridge, stable ACP with optional Workspace callbacks, and ordinary Claude execution are implemented. Availability follows verified behavior, not this catalog. The [Codex](../../docs/codex.md), [ACP](../../docs/acp.md), and [Claude](../../docs/claude.md) user guides own compatibility baselines and available modes.
