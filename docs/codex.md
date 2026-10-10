---
title: Codex
description: Native Codex app-server control, transport ownership, options, and validation evidence.
---

## Implemented boundary

`ohkit.backends.codex.Codex` is a concrete asynchronous app-server v2 control adapter. It creates native Threads, starts foreground Runs, steers the expected active Turn, interrupts work, resumes/forks native history, streams observations, and answers typed command/file/permission approvals and user questions.

Codex owns the agent loop, tool semantics, provider configuration, credentials, and native history. By default it also owns file/process execution. For explicitly selected external execution, `CodexExecBridge` delegates file/process operations to an application-supplied Workspace without emulating Codex tools or patches. The backend advertises Workspace support; ordinary native Threads have `workspace=False`, while external Threads have `workspace=True` and no resume/fork capability. Capability flags describe implemented features, not a guarantee that every native configuration supports them. See [Workspace](workspace.md) for the supported mode and authority boundary.

## Owned stdio process

```python
from ohkit.backends.codex import Codex, CodexOptions, CodexThreadOptions

async with Codex(options=CodexOptions(executable="codex")) as backend:
    thread = await backend.new_thread(
        cwd="/native/project",
        options=CodexThreadOptions(approval_policy="untrusted", sandbox="read-only"),
    )
    result = await thread.run("Explain the code without modifying it.")
```

The default launches `codex app-server --listen stdio://`. `CodexOptions.config` contains actual native TOML `-c key=value` overrides. `env`, when provided as name/value pairs, replaces rather than merges the child environment; callers must supply needed `PATH`, `HOME`, `CODEX_HOME`, and native authentication themselves. Leave it `None` to inherit the process environment. Config and environment values are hidden from repr.

`CodexThreadOptions` forwards actual model, model-provider, approval policy, sandbox, base-instruction, and developer-instruction parameters. Omitted values retain native defaults. Approval policy and sandbox are native security controls, not policies enforced by ohkit. The library neither logs credentials nor authenticates a model provider for the caller.

Closing the backend first settles live Runs, then closes stdin and waits for the owned app-server, escalating to terminate/kill under the cleanup deadline if necessary. Private stderr is drained to prevent deadlock, not promoted into ordinary events.

## Borrowed WebSocket service

WebSocket control is included in the default installation. Start and secure the native service yourself; pass its URL and optional authentication headers:

```python
options = CodexOptions(
    websocket_url="ws://127.0.0.1:4500",
    history_scope="my-codex-service-and-storage",
)
async with Codex(options=options) as backend:
    thread = await backend.new_thread(cwd="/path/on/service-host")
    result = await thread.run("Explain the project.")
```

The adapter owns only its WebSocket connection, not the server/listener or any external provider. Backend exit closes that connection after Run settlement; it does not terminate the borrowed service. `headers` and the URL are hidden from repr, and connection errors do not echo credential-bearing addresses or headers. Transport/protocol errors after possible execution are uncertainty, not a reason to reconnect and replay input automatically.

`history_scope` is required for remote control. Use a stable non-secret identity for the native service and history storage, not a token or credentialed URL. Local references use the absolute effective `CODEX_HOME` by default. A reference's scope must match the backend; references contain no credentials and grant no access.

## Application-hosted execution

Pass `executor=CodexExecutor(...)` to `new_thread`, with explicit target cwd and `CodexThreadOptions(sandbox="danger-full-access")`. Control may still use stdio or a borrowed WebSocket service. The application hosts and authorizes `CodexExecBridge.serve`; the backend neither creates a hidden listener nor owns the provider. Native readiness and exact selection are checked before returning the Thread.

The current native resume/fork requests cannot bind an external executor before startup I/O. Those external operations are rejected, not downgraded to local execution. Registration also affects shared native defaults: use a dedicated app-server and do not reopen external history through the ordinary host-history API. [Workspace](workspace.md#codex-binding) owns these limits; the [hosting example](examples/application-hosted-executor.md) is runnable checkout code.

A separate [copy/inject integration plan](continuation.md#codex-new-external-thread-plus-selected-injection) records native evidence for reconstructing selected dialogue in a new external Thread on another Workspace. It does not add public history-read or injection methods, and is not native executor rebinding.

## Operational limits

`event_capacity` bounds retained Run observations (default 256). `request_timeout` bounds native request acknowledgement waits; losing an acknowledgement after possible dispatch makes the connection unavailable and raises `UnknownOutcomeError`. `cleanup_timeout` bounds Run interaction/termination settlement and process/connection close operations. A timeout is not proof that native side effects did not occur.

Native app-server control is a trusted interface, not a remote authorization boundary supplied by ohkit. Secure remote access and native provider configuration separately. Multiple application owners of the same native history must coordinate outside this process; ohkit provides no distributed lease.

## Compatibility and validation

The tested native version is **Codex 0.162.0**, upstream tag `rust-v0.162.0`. This is a pinned compatibility baseline, not a claim about the latest release. The adapter opts into experimental app-server fields required for exact approval and input-correlation semantics. It does not enforce a global executable version at startup; use the tested version or verify compatibility for your chosen release. Unknown terminal enums, malformed native JSON, uncorrelated responses, or unrepresentable decisions fail explicitly rather than inventing semantics.

Validation has distinct layers:

- Controlled localhost WebSocket protocol tests exercise notification-before-response admission, pending steering/interrupt acknowledgements, lost transport, stale/reused interaction IDs, cleanup deadlines, event pressure, malformed terminal data, and foreground attribution. These peers are not native Codex.
- Controlled real stdio child tests verify owned process reaping, early-exit interruption, and death during uncertain submission without replay.
- Opt-in public-API tests run the actual verified Codex 0.162.0 executable with isolated `HOME`/`CODEX_HOME` and a deterministic loopback Responses SSE model endpoint. They cover streaming/usage, history fork/reopen, steer followed by normal completion and a separate subsequent Run, interruption, real command approval non-approval/accept with a temporary-file effect, typed questions, and borrowed native WebSocket service survival across client closure. They also cover real Workspace instruction discovery, file read/patch/write, command effects and final output through both control transports, endpoint reuse, event-gated preparation, and process cancellation followed by another Run on the same binding. They make no paid external model calls and inherit no ambient model credentials.

Run native tests explicitly:

```bash
OHKIT_TEST_NATIVE=1 uv run --locked pytest tests/test_codex_native.py -q
# For another supported platform, provide an installed exact-version binary:
OHKIT_TEST_NATIVE=1 OHKIT_CODEX_BINARY=/path/to/codex uv run --locked pytest tests/test_codex_native.py -q
```

The Linux x86_64 fixture downloads the official pinned release into a test temporary directory and checks its SHA-256 before extraction. Normal `make check-all` skips these executable/network-download tests. No authenticated live-provider smoke test is implied by deterministic validation.

Wire shapes are generated from the pinned official schema into private Pydantic v2 models. Structural decoding is strict and errors do not echo native validation payloads. Unknown fields survive round trips; unknown known-field enum values fail explicitly. [Protocol maintenance](codex-protocol.md) owns regeneration, the daily native upstream regression Action, and the reviewed upgrade procedure.

## Steering evidence

The adapter sends a unique `clientUserMessageId` on each steering request and first records the same `clientId` on the current Turn's native user-message item. Recording alone is insufficient: only a new foreground `agentMessage` or `reasoning` **item start**, after that prompt item, establishes subsequent model work. Deltas, late completion of an older item, repeated starts of an already observed item, async-delivery messages, and another Turn's events are not consumption evidence. The pinned [delivery enum](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/protocol/src/items.rs#L130-L135) has only `async`; only absent/null delivery is treated as foreground, not an unknown future delivery value. The adapter also waits for steering acknowledgement and native terminal evidence. Non-interrupted completion without this evidence is unknown and disables the owner.

The pinned upstream source establishes the following chain:

1. [App-server steering](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server/src/request_processors/turn_processor.rs#L1075-L1085) forwards `clientUserMessageId` and the expected Turn.
2. [Active-Turn admission](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn_input.rs#L758-L847) checks that Turn under its active-owner lock and appends the ID-bearing user input to its pending queue.
3. [Queue drainage](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/input_queue.rs#L400-L429) removes pending inputs; the [Turn loop](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L425-L448) records them before the next model step. [Post-sampling pending input](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L560-L573) forces follow-up work.
4. [Prompt recording](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/hook_runtime.rs#L716-L740) forwards the ID to [history recording and item emission](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/mod.rs#L4914-L4974). The [app-server item conversion](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server-protocol/src/protocol/v2/item.rs#L873-L880) preserves that `clientId`. However, [task finalization](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/tasks/mod.rs#L672-L709) also drains and records unsampled pending input before terminalization. This branch must not be mistaken for model consumption.
5. The normal loop awaits [its sampling request](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L497-L543) before another pending-input drain. Within sampling, [model `OutputItemAdded`](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L2811-L2887) emits the new foreground item start. [Response completion flushes deferred assistant text](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L2946-L2995), and [final flushing and in-flight tool drainage](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/turn.rs#L3143-L3191) finish before sampling returns. An earlier response's deferred foreground starts therefore precede the next prompt drain, not follow it.
6. [Core emission](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/session/mod.rs#L2555-L2581) awaits enqueueing the attributed item; the [single thread listener](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server/src/request_processors/thread_lifecycle.rs#L313-L364) awaits translation of each event before receiving the next. The adapter observes that native order. Item identity deduplication and explicit async-delivery exclusion prevent old or unrelated output from satisfying the receipt.
7. [Native interruption](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/core/src/tasks/mod.rs#L616-L628) clears pending input. Confirmed `interrupted` terminal evidence can therefore account for accepted input as cancelled without claiming it was sampled.

The native test additionally asserts that the second loopback model request actually contains the steering text, then runs a distinct third request to rule out a silently deferred foreground task. Targeted controlled tests cover terminal-only history drain, old deltas/completion/repeated starts, and async starts: all remain unknown, while a genuinely new foreground start can establish the consumption boundary. Correlated recording followed by that new model item, admission settlement, and native completion account for accepted input; neither acknowledgement nor history insertion alone is consumption. The fixture proves delivery to the model boundary, not that a real model will follow the requested instruction.

## Native interaction closure and defaults

The pinned [request-resolution notification](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server-protocol/src/protocol/v2/notification.rs#L70-L77) uses `threadId` and `requestId`. The reader retires that exact response owner before routing the observation. Both successful replies and error replies recheck ownership at the write gate, including when a native request ID is reused.

Command prompts use the exact `availableDecisions` list when present. When absent, the adapter follows the pinned [native prompt defaults](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/tui/src/approval_events.rs#L56-L111): ordinary or additional-permission prompts do not implicitly offer session-wide approval; network prompts preserve their distinct session/persistent choices and exact proposed allow amendment. File-change choices follow their native response schema. A response enum accepting a value is not evidence that every prompt offered that authority.
