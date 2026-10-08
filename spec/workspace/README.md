# Workspace Contracts

Workspace is the caller-supplied execution and filesystem boundary. It is not a conversation, native protocol, or virtual operating system.

| Document                                     | Owns                                                                       |
| -------------------------------------------- | -------------------------------------------------------------------------- |
| [Architecture overview](00-overview.md)      | Dependency inversion, routing, binding, lifetime, and downstream embedding |
| [Files and processes](01-files-processes.md) | Byte I/O, process semantics, requirements, and failures                    |

Read [execution](../execution/README.md) for logical work and [backends](../backends/README.md) for the native bridges. A backend's Workspace integration does not imply that every native I/O path is intercepted.
