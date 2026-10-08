# Execution Contracts

Execution is the common application-facing boundary. Read these documents in order:

| Document                                                     | Owns                                                                                |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| [Architecture overview](00-overview.md)                      | Design position, components, and primary flow                                       |
| [Thread and Run](01-thread-run.md)                           | Identities, admission, steering, cancellation, completion, and history continuation |
| [Observation and interaction](02-observation-interaction.md) | Event/result meaning, live decisions, and stream behavior                           |

[Workspace](../workspace/README.md) owns supplied I/O and its resources. [Backends](../backends/README.md) own native mappings and feature availability. Native terms such as ACP `session` remain protocol vocabulary, not a second public conversation model.
