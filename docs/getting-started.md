---
title: Getting started
description: Install ohkit and run Codex, an ACP agent, or Claude through typed asynchronous execution.
---

## Requirements and availability

Use Python 3.13 or newer. ohkit provides one typed Thread/Run interface with Codex, ACP, and Claude backends. Earlier published bootstrap releases expose version metadata only; install the implementation from this checkout or a validated runtime-bearing wheel until the first runtime release is published.

All three backend dependencies are included in the default installation; no extras are required. Your application supplies native credentials and configuration. Node.js is not required to build ohkit; a chosen ACP agent may require it at runtime.

| Backend             | Native setup                                             | Supplied Workspace                                             |
| ------------------- | -------------------------------------------------------- | -------------------------------------------------------------- |
| [Codex](codex.md)   | Install and configure the tested Codex executable        | Application-hosted external executor                           |
| [ACP](acp.md)       | Install and configure a selected ACP agent               | Optional file/terminal callbacks; actual use is agent-specific |
| [Claude](claude.md) | Configure credentials for the SDK-bundled Claude runtime | Not supported                                                  |

See each backend guide for its tested baseline and capability limits. The example below starts with Codex; runnable [ACP](https://github.com/Wh1isper/ohkit/blob/main/examples/acp.py) and [Claude](https://github.com/Wh1isper/ohkit/blob/main/examples/claude.py) examples use the same streaming and result model.

## Install from source

```bash
python -m pip install .
# Or install a validated build without a source checkout:
python -m pip install /path/to/ohkit-<version>-py3-none-any.whl
```

## Result-only execution

```python
import asyncio

from ohkit.backends.codex import Codex


async def main() -> None:
    async with Codex() as backend:
        thread = await backend.new_thread(cwd="/path/to/project")
        result = await thread.run("Explain the project without changing files.")
        print(result.outcome)
        print(result.output)


asyncio.run(main())
```

`Codex()` starts and owns an app-server over stdio. `cwd` refers to the native app-server host, not a caller-supplied Workspace. The native harness owns tool execution and sandbox policy. Missing approval handlers select a native non-approval choice; they do not grant permission.

A completed result means native execution ended normally, not that the task achieved its goal. Check `result.outcome` before treating `result.output` as a successful answer. Usage is `None` when unavailable, not zero.

## Streaming and continuation

```python
from ohkit import ContentEvent

# Inside an async function with an entered backend:
thread = await backend.new_thread(cwd="/path/to/project")
async with thread.stream("Explain the main entry point.") as run:
    async for event in run:
        if isinstance(event, ContentEvent) and event.channel == "assistant":
            print(event.text, end="", flush=True)
    result = await run.result()

reference = thread.ref
resumed = await backend.resume(reference)
follow_up = await resumed.run("Summarize your explanation.")
```

Consume a Run's stream once before calling `result()`. For result-only work, `thread.run()` owns the same driver's drainage. Leaving a stream early requests interruption and settles cleanup; it does not detach the foreground work.

`ThreadRef` identifies native history and its storage scope. It contains no credentials and does not restore live processes, pending approvals, or an interrupted Python Run. Reopening the same history in this backend replaces its idle live owner; the old object becomes unavailable.

## Next steps

- [Execution](execution.md): ownership, steering, cancellation, events, and handlers.
- [Codex](codex.md), [ACP](acp.md), and [Claude](claude.md): native setup, policy, capability differences, and compatibility evidence.
- [Runnable example](https://github.com/Wh1isper/ohkit/blob/main/examples/codex.py): streaming with an explicit non-approval handler and history continuation.
- [Workspace](workspace.md) and [application-hosted executor](examples/application-hosted-executor.md): typed provider I/O and a runnable authenticated bridge for new Codex Threads.
