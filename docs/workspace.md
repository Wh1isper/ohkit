---
title: Workspace
description: Typed file and process providers, Codex executor binding, and explicit authority boundaries.
---

## One borrowed provider

`ohkit.workspace` exports async `Workspace`, `FileSystem`, `ReadFile`, and `Process` protocols plus immutable typed request/result values. Providers implement ordinary Python methods; they do not parse Codex JSON, patches, base64, or native handle IDs. The module has no native-backend dependency.

A Workspace has `files`, `describe() -> WorkspaceInfo`, and `start_process(ProcessRequest) -> Process`. Its metadata describes the actual target cwd, shell, platform, path style, and optional home. Paths and an optional opaque `target` hint belong to the provider's namespace, never the controller's filesystem. The Codex bridge has a fixed Workspace binding; it does not invent per-call target hints or route by path prefixes.

## File semantics

The filesystem exposes byte reads/writes, metadata, directory entries, directory creation, removal, copy, canonicalization, and opened read handles. `ReadFile.read(offset, max_bytes)` reads that opened resource even if the original path is replaced; it does not promise an immutable snapshot. `FileBlock.eof` reports the end of the file. Close the handle when finished.

Symlink following, recursive operations, overwrite, and missing-file behavior are explicit arguments. Unsupported semantics raise `UnsupportedError` before effects. Ordinary filesystem errors use typed `OSError` subclasses such as `FileNotFoundError` and `PermissionError`. Unknown timestamps remain `None` in `FileInfo`; the Codex projection uses its native zero sentinel, not fabricated creation metadata. `is_symlink` is independent of the followed file kind.

Writes and copies have the provider's documented atomicity. A failure or disconnect does not imply rollback, and the bridge never retries an uncertain mutation.

## Process semantics

`ProcessRequest` preserves argv without shell re-parsing, target cwd, environment construction, stdin/TTY requirements, and optional argv0. Environment filtering is relative to the **target's** base environment: choose inheritance, apply case-insensitive exclusion globs, assignments, optional include-only globs, then the explicit `env` overlay. Providers must reject policies they cannot implement faithfully.

`Process.read(max_bytes)` consumes a bounded byte stream and returns `ProcessOutput` with stdout/stderr/pty identity, output EOF, and any lost-byte count. There is one consuming reader. `wait()` observes process exit independently of output drainage. `write()`, `close_stdin()`, and `signal()` act on the original process, not a newly resolved target. `close()` is idempotent: settle the owned command, unblock pending I/O, and release resources, or report cleanup failure.

Providers must settle admitted operations rather than abandon handles after cancellation. On disconnect, the bridge closes existing processes first to unblock pending stdin writes, then waits for in-flight launches and opens and closes their returned handles. A provider that never settles can hold connection cleanup open; the application must choose provider deadlines and operational recovery appropriate to its infrastructure.

## Codex binding

The controller supplies an endpoint, not a Python Workspace:

```python
from ohkit.backends.codex import Codex, CodexExecutor, CodexThreadOptions

# Inside an async function; obtain project_token from application secret storage.
async with Codex() as backend:
    thread = await backend.new_thread(
        cwd="/target/project",
        executor=CodexExecutor(
            "wss://executor.example.com/projects/a/exec",
            bearer_token=project_token,
        ),
        options=CodexThreadOptions(sandbox="danger-full-access"),
    )
    result = await thread.run("Explain the project.")
```

The endpoint must be reachable by app-server. Authentication, authorization, TLS, routing, and listener lifetime belong to your application. `new_thread` requires explicit target cwd and `danger-full-access`; it registers the endpoint once per backend/endpoint value, waits for native readiness, prepares the selected Thread without deferred executor startup or shell snapshots, verifies the selected environment/cwd, and checks readiness again. No arbitrary preparation sleep or local-execution fallback is used.

**External history resume/fork is unsupported.** The pinned native requests lack environment selection before startup I/O. Passing `executor=` to `resume` or `fork` raises `UnsupportedError` before dispatch. Once a backend attempts external registration, it also rejects history operations and new Threads without an explicit executor. An external Thread advertises `workspace=True`, `resume=False`, and `fork=False`; ordinary native Threads retain their history capabilities. Multiple Runs on the same live external Thread are supported.

Use a dedicated app-server for this external mode: registration changes shared native defaults and outlives the controller connection on a borrowed service. Do not mix it with unrelated default-environment consumers. `ThreadRef` contains history identity only, not an executor binding; do not reopen external history through a fresh backend's ordinary host-history API. Dedicated startup-configured native deployments are a different integration, not a per-thread rebinding feature of this API.

## Bridge lifetime and limits

`CodexExecBridge(workspace).serve(incoming, send)` borrows one Workspace for one authenticated connection. You may reuse the bridge configuration for multiple connections; every invocation has separate handles, request IDs, output retention, and cleanup. Keep the provider usable until `serve` finishes. The bridge never closes the provider itself or another connection's resources. Closing a Thread or Run does not close an app-server-wide executor connection; the host owns that lifetime.

- `output_capacity` defaults to 1 MiB per process replay buffer and bounds file-block reads. Native reads return complete chunks, so the first chunk can exceed the native request's `maxBytes`, but never the bridge capacity. Whole-file operations retain their whole-file semantics; configure transport/provider limits separately.
- `handle_limit` defaults to 256 for each connection's open files and live processes. Completed processes release their provider handles after output drainage and exit observation; they no longer consume live-process capacity. `request_limit` independently bounds in-flight requests (default 256).
- `replay_limit` retains the most recent completed processes in completion order (default 256), independently of live handles. Their bounded output, terminal status, and write acknowledgements remain readable without a provider handle. Older records are evicted; reads/signals for an evicted process fail explicitly, writes return `unknownProcess`, and termination reports not running. Retained completed processes reject new stdin with `stdinClosed` but acknowledge already-accepted write IDs.
- Process IDs are single-use for the connection, including a launch whose provider call failed after possible effects. Small identity tombstones survive replay eviction so an old ID can never relaunch a command. Accepted stdin write IDs are retained with their live process or completed replay record, without a cumulative write quota. Output and resource limits do not bound this identity metadata: it grows with admitted process IDs and retained write IDs. Hosts may end a connection to release it, but must treat that as binding shutdown, not transparent recovery.
- Provider output loss fails the connection; an evicted replay cursor returns an explicit error. Neither becomes complete output or a successful exit. The bridge drains output and settles the provider handle before publishing native terminal notifications. Natural release and connection cleanup share the same close operation; a failed release never becomes a successful `process/closed` notification.
- Disconnect, cancellation, and iterator completion stop admission and settle handles. Cleanup failures reach the application as `CleanupError`. Unknown side effects are not replayed. Native executor-session recovery is rejected; reconnecting starts a new resource scope.

The initial bridge supports file/process requests, not optional discovery, filesystem walks, HTTP forwarding, environment configuration, shell snapshots, writable file streams, or managed networking. It advertises no optional executor capabilities. Sandbox policies other than explicitly disabled native permissions are rejected. TTY, argv0, and environment policy support depend on the provider and must fail before launch when unsupported. Native stdin writes are supported; the pinned wire has no separate stdin-EOF operation even though the public Process contract does.

## Reference provider, not a sandbox

[`examples/local_workspace.py`](https://github.com/Wh1isper/ohkit/blob/main/examples/local_workspace.py) is a real POSIX provider for trusted integration testing and application examples. It uses actual files, opened read handles, subprocess groups, bounded output, environment policy, and stdin/termination. It rejects TTY, argv0 overrides, target selectors, core-only environment inheritance, and no-follow traversal through symlinks rather than weakening them. Relative file paths and process cwd share the Workspace cwd as their base; absolute paths remain absolute. Copies preserve source symlinks; existing symlink destinations, including nested entries in directory merges, fail without modifying their referents. Regular files can overwrite, and recursive directory copies can merge. No atomic multi-file transaction or protection against concurrent path replacement is promised.

**Its cwd is not confinement. Files and commands have the host account's full authority.** Authentication identifies a trusted peer; it does not sandbox commands or provide tenant isolation. Production applications must supply an appropriate provider and secure both native control and executor access. Native history, credentials, configuration, and other unbridged I/O remain on the app-server host.

See the [runnable authenticated host](examples/application-hosted-executor.md) and [Codex validation evidence](codex.md#compatibility-and-validation). ACP and Claude are not implemented Workspace adapters.
