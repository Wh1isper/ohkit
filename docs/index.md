---
title: ohkit
description: An independent Python programming interface for agent harnesses.
---

ohkit is an independent Python programming interface for agent harnesses. Its design separates conversation continuity, foreground work, and the file and process operations used by a native agent.

**Pre-alpha bootstrap:** the published package currently exposes version metadata only. Thread, Run, Workspace, and backend execution are accepted design concepts, not shipped APIs. Examples on this site are explicitly marked when they describe future interfaces.

## Start here

- [Getting started](getting-started.md): install the bootstrap and understand what is available.
- [Application-hosted executor](examples/application-hosted-executor.md): the design example for serving multiple project Workspaces from one application.
- [Documentation maintenance](documentation.md): preview, validate, and deploy this site.
- [Releasing](releasing.md): prepare and publish Python artifacts.

## Design boundaries

Native harnesses own their agent loops, tools, Turns, and native history. ohkit owns the common execution boundary and protocol adapters. Applications own policy, durable scheduling, persistence, deployment, and Workspace providers.

A Thread preserves conversation continuity. A Run represents one accepted unit of foreground work and may span native Turns. A Workspace supplies file and process operations; it is not an agent loop or a virtual operating system.

The [accepted specifications](https://github.com/Wh1isper/ohkit/tree/main/spec) own these contracts. They describe the target architecture rather than a claim of implemented backend compatibility.

## Project

Wh1isper maintains ohkit as an independent public project. Browse the [repository](https://github.com/Wh1isper/ohkit) or read the [contribution guide](https://github.com/Wh1isper/ohkit/blob/main/CONTRIBUTING.md).
