---
title: ACP
description: Stable Agent Client Protocol execution with optional Workspace callbacks.
---

The `ACP` backend uses the official `agent-client-protocol` Python SDK. The tested SDK baseline is **0.12.1**, negotiating stable wire protocol **1**. Install and authenticate your chosen ACP agent separately; ohkit does not choose an agent or launch a login flow.

## Execute and continue

Pass the actual command and arguments for your configured agent. `process_cwd` is the controller-side launch directory; `new_thread(cwd=...)` is the native session's target directory. Paths are not resolved against the controller to make a remote target look local.

```python
import asyncio
import sys

from ohkit.backends.acp import ACP, ACPOptions


async def main() -> None:
    # Usage: python example.py /target/project agent-executable [agent-args...]
    cwd, *command = sys.argv[1:]
    async with ACP(options=ACPOptions(command=tuple(command))) as backend:
        thread = await backend.new_thread(cwd=cwd)
        result = await thread.run("Explain this project without changing files.")
        print(result.outcome, result.output)
        if thread.capabilities.resume:
            continued = await backend.resume(thread.ref, cwd=cwd)
            print((await continued.run("Summarize that in one sentence.")).output)


asyncio.run(main())
```

Each live Thread owns one subprocess and SDK connection. Later Runs on that Thread reuse the connection. Resume opens a new owner and process, choosing `session/resume` when advertised, otherwise `session/load`; replayed history is not emitted as new Run output. An old idle owner is closed before replacement. The application coordinates owners in other processes.

`ACPOptions.env` overlays the SDK's trimmed base environment. Supply credentials through your application's environment/configuration policy, never hard-code them. Native stderr is discarded rather than accumulated as an unbounded private log. `history_scope` can identify application-owned history storage; the default hashes launch command, directory, and explicit environment configuration. A reference carries no credentials.

## Capability boundaries

| Behavior                                            | Availability                                                          |
| --------------------------------------------------- | --------------------------------------------------------------------- |
| Text input, streaming events, result-only execution | Implemented                                                           |
| Cancellation                                        | Requests `session/cancel`; final prompt response is terminal evidence |
| Resume/load                                         | Negotiated per agent                                                  |
| Steering                                            | Unavailable; no prompt-queue fallback                                 |
| Fork                                                | Unavailable; the SDK marks `session/fork` unstable                    |
| Permissions                                         | Offered native choices through `Handlers.approval`                    |
| Images and elicitation/questions                    | Not advertised by this adapter                                        |
| Workspace                                           | Optional text-file and terminal callbacks                             |

A prompt has no independent acceptance response: Run admission is local, while its final response supplies `stopReason`. `end_turn`, `max_tokens`, `max_turn_requests`, and `refusal` mean native work ended normally, not that the goal succeeded. Inspect `result.native_status`. `cancelled` is distinct; connection loss is unknown and makes the owner unavailable. Inputs are never automatically replayed.

Approval choices have `kind="native"` and `scope="native"`. Their `native.decode()` retains the offered `optionId`, `name`, and native choice kind. Return one offered choice unchanged. In particular, `allow_always` and `reject_always` are not normalized to a guessed persistence scope. Missing handlers or handler failures return the native cancelled outcome, never approval.

## Supply a Workspace

```python
from ohkit.backends.acp import ACP, ACPOptions
from ohkit.workspace import Workspace


async def inspect(command: tuple[str, ...], workspace: Workspace) -> str:
    info = await workspace.describe()
    async with ACP(options=ACPOptions(command=command)) as backend:
        thread = await backend.new_thread(cwd=info.cwd, workspace=workspace)
        return (await thread.run("Read the project instructions.")).output
```

The adapter advertises callbacks only when given a Workspace. It borrows that provider; closing the backend releases adapter-owned terminal handles, not the Workspace. A selected agent may still perform other native I/O independently. Callback support is not complete interception or a sandbox.

Text files decode strict UTF-8; line slicing preserves line endings. Writes encode UTF-8 and create parent directories through the provider. Command and args become argv without shell re-parsing. Omitted terminal cwd uses the session cwd; environment entries overlay the target base environment.

Terminals retain a cumulative text snapshot, with per-stream incremental UTF-8 decoding and replacement of invalid bytes. Output limits are bytes, capped by `terminal_output_limit`; truncation never splits a character and provider loss is visible. `wait_for_exit` does not wait for output EOF. Kill retains the handle; release closes it and invalidates its ID. Handles survive prompt completion until release or Thread close. `terminal_limit` limits unreleased handles, not total commands over a connection's life.

## Validation

The tests exercise the real Python SDK against an independent deterministic stdio protocol peer, including exact permission choices, history replay exclusion, cancellation, transport loss, output overflow, and real Workspace file/process callbacks. Additional provider tests cover UTF-8 boundaries, output loss, exit versus EOF, concurrent close, and cancelled late launches. These establish the supported protocol paths, not compatibility with every ACP agent or actual model provider.

```bash
uv run --locked pytest tests/test_acp.py tests/test_acp_workspace.py
```

See [execution](execution.md) for shared lifecycle and [Workspace](workspace.md) for provider semantics.
