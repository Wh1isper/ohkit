---
title: Getting started
description: Run a configured Codex app-server through typed asynchronous execution.
---

## Requirements and availability

Use Python 3.13 or newer. This source checkout implements Thread/Run execution and Codex control. Earlier published bootstrap releases expose version metadata only; install the implementation from this checkout until a release containing it is available.

Codex must be installed separately and configured with access to its native model provider. The adapter is tested against Codex `0.161.0`; see [Codex compatibility](codex.md#compatibility-and-validation). Core execution and stdio control have no runtime Python dependencies. Documentation tools are separate developer dependencies.

## Install from source

```bash
python -m pip install .
# Only when connecting to a caller-owned WebSocket app-server:
python -m pip install '.[codex-websocket]'
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
- [Codex](codex.md): options, native policy, transport lifetime, and compatibility evidence.
- [Runnable example](https://github.com/Wh1isper/ohkit/blob/main/examples/codex.py): streaming with an explicit non-approval handler and history continuation.
- [Application-hosted executor](examples/application-hosted-executor.md): conceptual future Workspace integration, not an implemented executor bridge.
