---
title: Claude
description: Ordinary Claude Agent SDK execution with explicit history and completion boundaries.
---

The `Claude` backend uses the official `claude-agent-sdk` Python package. The tested baseline is **0.2.165**, whose installed Linux distribution bundles **Claude Code 2.1.294**. Native model credentials, tool configuration, hooks, and native sandbox/permission policy remain application-owned.

## Execute and continue

```python
import asyncio

from claude_agent_sdk import ClaudeAgentOptions

from ohkit.backends.claude import Claude


async def main() -> None:
    options = ClaudeAgentOptions(allowed_tools=["Read", "Glob", "Grep"])
    async with Claude(options=options) as backend:
        thread = await backend.new_thread(cwd="/path/to/project")
        result = await thread.run("Explain this project without changing files.")
        print(result.outcome, result.output)
        print((await thread.run("Summarize that in one sentence.")).output)
        reference = thread.ref

    async with Claude(options=options) as backend:
        resumed = await backend.resume(reference, cwd="/path/to/project")
        print((await resumed.run("Continue the discussion.")).output)


asyncio.run(main())
```

A Thread has a stable native session UUID, but **each Run owns a fresh SDK client/process**. The first Run creates native history; later Runs resume it. Creating or reopening the Python Thread selects history locally; native validation occurs when the next Run starts. A missing history or refused resume is not replaced with an empty conversation. Keep the native history store, cwd, credentials, and configuration compatible.

This preserves history, not live processes, terminal handles, pending approvals, or the Python object graph. `history_scope` can explicitly identify your storage boundary. The default derives from native executable and home/config directory; it is not an authorization token or distributed ownership lease.

## Completion and control

The adapter sends exactly one initial input through an asynchronous iterable and drains `receive_messages()` to EOF. It does not use the first `ResultMessage` as a Run-completion shortcut. The SDK owns native background-task accounting, session-state handling, and input closure. Native follow-up Turns can therefore remain inside the same Run. The result is published after SDK cleanup.

Only text input and complete assistant message blocks are currently projected. Text from a child agent retains native attribution rather than being appended to the parent's final answer. Each native result is observable; final usage is the last native result's reported usage, not a sum of potentially overlapping statistics. Native terminal details remain in `result.native`.

`run.cancel()` requests an interrupt. The native result decides whether cancellation or normal completion won. `aborted_streaming` and `aborted_tools` establish cancellation; the bundled CLI can then exit with code 1 without invalidating that evidence. A matching SDK error result followed by exit code 1 likewise preserves the known failure. A crash, unfinished main-thread follow-up at EOF, or forced close without complete evidence is unknown and prevents another Run on that owner.

Steering is unavailable: writing another SDK input does not by itself establish the accepted-input accounting required by ohkit. Fork is not enabled. There is no silent queue or automatic submission retry.

## Permissions and configuration

Use `Handlers(approval=...)` with `thread.run()` or `thread.stream()`. The handler receives action-scoped accept/decline choices, tool input, and native permission suggestions. Return an offered choice unchanged. Suggestions are data, not automatically granted session permissions. Without a handler, requests reaching this callback are denied. Native policy can allow tools without reaching this callback; a handler is not an unconditional interceptor. Set `ClaudeAgentOptions(permission_mode="default")` when using native permission prompts rather than inheriting the CLI's permission-mode default.

Native callback cancellation withdraws the live request; it does not send a stale denial or bind the answer to another Run. Observation consumers do not own permission routing.

Pass a native `ClaudeAgentOptions` for SDK configuration; do not mutate it while the backend is in use. ohkit reserves history selection (`session_id`, resume/continue/fork options), its permission callback/routing, and input/output formats. Conflicting native options or `extra_args` fail explicitly. Partial-message mode is not enabled. Ordinary SDK tools and hooks are supported as native features, not translated into a replacement tool framework.

This backend **does not accept Workspace**. Native hooks and custom MCP tools do not establish transparent replacement of all filesystem/process I/O. Use [Codex](codex.md) or [ACP](acp.md) for the supported supplied-Workspace paths.

## Validation

Protocol tests use the actual SDK with its public Transport seam, covering multiple native results before EOF, exact permissions, callback withdrawal, interrupt races, history-selection options, and unknown outcomes. Native tests run the SDK-bundled CLI against a deterministic loopback Anthropic service with isolated home/config and a fake local-only API key. They verify actual history continuity across Runs and backend reopening, refused missing-history resume, interruption, and allow/deny decisions controlling real file-write effects. They make no paid model calls and do not validate production provider quality.

```bash
uv run --locked pytest tests/test_claude.py
make claude-native-test
```

The SDK retains ownership of its subprocess, control protocol, and native history. Compatibility claims apply to these covered paths, not arbitrary CLI overrides or every future SDK version.
