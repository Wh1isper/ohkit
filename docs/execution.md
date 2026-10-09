---
title: Execution
description: Typed async Thread and Run ownership, observations, active control, and live decisions.
---

## One live owner, one foreground Run

Create a Thread through a concrete backend. A Thread is a process-local execution owner of native conversation history; it admits at most one active Run. Concurrent `thread.run()` or stream entries raise `BusyError`. Inputs are not queued. Constructing `thread.stream(...)` does not dispatch; entering it does.

Both paths share one driver:

```python
result = await thread.run("Explain the code.")

async with thread.stream("Explain the code.") as run:
    async for event in run:
        observe(event)
    result = await run.result()
```

One task consumes the stream. Calling `result()` before drainage raises `UndrainedStreamError`, rather than waiting on a hidden consumer. Repeated `result()` after drainage returns the same immutable Result.

Input is a string or a tuple of `Text`, `Image`, and `LocalImage` values. Local image paths refer to the native backend host. Shared values are frozen, slotted dataclasses and do not depend on a vendor SDK.

## Active steering

`await run.steer(input)` adds input to that active Run. Codex targets its established native Turn using `expectedTurnId`; a rejection never starts a replacement Run. The caller must arrange steering while another task drains observations, or before beginning drainage.

A successful acknowledgement proves admission, not model consumption. The adapter waits for pending control acknowledgements before terminalizing. A normally completed Codex Run additionally requires observed consumption of each accepted steering input. Missing consumption evidence produces an unknown result and disables that live owner, rather than silently carrying input into a future Run. [Codex compatibility](codex.md#steering-evidence) describes the native evidence used.

Once native completion, cancellation, or uncertainty has closed admission, steering raises `InactiveRunError`. History resume is explicit continuation, not a fallback for rejected steering.

## Cancellation and cleanup

`await run.cancel()` requests native interruption. Its acknowledgement is not a terminal result. Continue drainage and inspect the actual outcome: normal completion may win; confirmed native interruption becomes `cancelled`; lost termination evidence becomes `unknown`. Repeated cancellation does not dispatch additional native tasks.

Leaving a stream early or cancelling its owning task settles initial submission and requests interruption before releasing ownership. Run cleanup uses a bounded deadline. `CleanupError` preserves any already observed Result in `.result`; it does not imply rollback. A lost connection, unaccounted steering, or unresolved cleanup makes that owner unavailable for new Runs. Explicitly re-establish native history after investigating uncertainty.

Backend context exit closes its live Threads and owned connections/processes while native routing remains available for interruption. Closing a Thread does not archive or delete native history. A caller-owned remote service is not stopped.

## Events and results

`Event` is a discriminated union of `ContentEvent`, `ToolEvent`, `InteractionEvent`, `UsageEvent`, `LifecycleEvent`, and namespaced `NativeEvent`. Events carry a `ThreadRef` and Run ID. Content channels distinguish assistant, reasoning, and tool output. An interaction observation has no response authority. Tool completion is not Run completion.

Events are process-local observations, not a durable replay log. Only reliably correlated foreground events enter the active stream; late events from another native Turn are not attributed to a new Run. Observation buffers are bounded and never block the sole native reader. Overflow triggers cancellation and `ObservationOverflowError`; native terminal evidence is retained out-of-band and remains available through `result()` after the stream failure.

A Result includes `outcome` (`completed`, `failed`, `cancelled`, or `unknown`), collected foreground output, optional current-Turn usage, optional Failure, native Turn/status, and native completion data. Partial output is not a successful final answer. Usage is unknown when not supplied by the native backend.

`NativeData` is a deliberate JSON-only escape hatch: immutable validated JSON text with a namespace, hidden from repr. `decode()` returns a detached JSON value. It rejects duplicate object keys, non-finite numbers, and non-JSON Python objects. Native payloads may contain private paths and tool inputs; do not automatically publish them as logs.

## Approvals and questions

Supply `Handlers(approval=..., question=...)` to a Run. Handlers are asynchronous and run separately from the native reader. Slow human decisions cannot block control acknowledgement routing.

```python
from ohkit import ApprovalChoice, ApprovalRequest, Handlers


async def deny(request: ApprovalRequest) -> ApprovalChoice:
    return next(choice for choice in request.choices if choice.kind in ("decline", "cancel"))


result = await thread.run("Inspect the project.", handlers=Handlers(approval=deny))
```

Return one of the offered `ApprovalChoice` values unchanged. Choices preserve native action, turn, session, or persistent scope and exact proposed permission/rule changes; a handler cannot manufacture broader authority. Command and file approvals differ from permission-profile requests. The default permission-profile response grants an empty profile, never the requested permissions.

Question handlers receive exact question IDs, offered options, free-text/other support, secret flags, and blocking semantics. Return `QuestionResponse` with one `Answer` for every question ID; unsupported IDs, duplicate answers, or unoffered labels are rejected. Answer contents are not placed in observation events or repr.

Missing approval handlers use an offered non-approval decision. Missing question handlers explicitly reject the request. Handler failure or an invalid response fails the Run and requests interruption; it never grants consent. Native withdrawal cancels the handler. A late response is checked again at the transport write gate and cannot answer a withdrawn request or a reused native request ID. Cancellation-suppressing handlers remain subject to the cleanup deadline; applications must write cooperative handlers.
