---
title: ohkit
description: An independent Python programming interface for agent harnesses.
---

ohkit is an independent Python programming interface for agent harnesses. Its design separates conversation continuity, foreground work, and the file and process operations used by a native agent.

**Pre-alpha implementation:** this source checkout implements typed asynchronous Thread/Run execution and Codex app-server control. Earlier published bootstrap releases expose version metadata only. Workspace I/O, executor bridges, ACP, and Claude adapters remain design contracts, not available APIs. Conceptual examples are explicitly labeled.

## Start here

- [Getting started](getting-started.md): install from source and run a configured Codex backend.
- [Execution](execution.md): streams, terminal results, active control, and live decisions.
- [Codex](codex.md): native options, transport ownership, and tested compatibility.
- [Application-hosted executor](examples/application-hosted-executor.md): the design example for serving multiple project Workspaces from one application.
- [Documentation maintenance](documentation.md): preview, validate, and deploy this site.
- [Releasing](releasing.md): prepare and publish Python artifacts.

## Design boundaries

Native harnesses own their agent loops, tools, Turns, and native history. ohkit owns the common execution boundary and protocol adapters. Applications own policy, durable scheduling, persistence, deployment, and Workspace providers.

A Thread preserves conversation continuity. A Run represents one accepted unit of foreground work and may span native Turns. A Workspace supplies file and process operations; it is not an agent loop or a virtual operating system.

The [accepted specifications](https://github.com/Wh1isper/ohkit/tree/main/spec) own these contracts. Unimplemented target contracts do not imply backend compatibility; the [Codex guide](codex.md) owns the current implementation boundary and validation evidence.

## Project

Wh1isper maintains ohkit as an independent public project. Browse the [repository](https://github.com/Wh1isper/ohkit) or read the [contribution guide](https://github.com/Wh1isper/ohkit/blob/main/CONTRIBUTING.md).
