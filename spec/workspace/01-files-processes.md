# Files and Processes

## Design Position

Workspace abstracts I/O operations, not model-facing tools. Patch parsing remains native-harness behavior; a filesystem does not need to understand `apply_patch`. Process creation receives argv; it does not need to understand a tool called `Bash` or `exec_command`.

The contract is semantic rather than a copy of the richest backend's wire schema. Backend admission checks the concrete requirements of the selected mode. An ACP text-only integration need not claim Codex filesystem parity.

## Files

| Operation family                   | Required meaning when supported                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------- |
| Read and replace                   | Read file bytes; replace contents with the supplied bytes                          |
| Open read handle                   | Retain one opened resource for bounded reads until close                           |
| Metadata and directory entries     | Report actual type, size, and supported metadata                                   |
| Create directory, remove, and copy | Apply explicit recursive and overwrite semantics within the target's authority     |
| Canonicalize                       | Resolve on the actual target, returning a path reusable in the Workspace namespace |
| Symlink behavior                   | Preserve a requested follow/no-follow distinction or reject it                     |

An open read handle is not repeated reopening of a path: replacement of that path must not silently switch the resource behind the handle. This is not a promise of an immutable content snapshot. Whole-file buffering is not an unbounded substitute for streaming.

Text encoding, line slicing, and wire base64 belong to the native adapter. The file boundary does not silently repair invalid text bytes. Metadata unavailable from the target remains unavailable; adapters do not invent timestamps or file kinds merely to satisfy a wire shape.

Reads, writes, and copies retain the provider's documented atomicity. A disconnected write or partially completed copy can have effects despite an error; the bridge cannot promise rollback or automatically replay mutations.

## Processes

Process requests preserve explicit argv, cwd, environment construction, stdin and terminal requirements, and any supplied target hint. The bridge does not join argv into shell text or parse it again. When a native harness chooses a shell, that shell is already an explicit executable in argv.

Environment construction is relative to the target's base environment, never the Python host's `os.environ`. An overlay and a replacement/filtering policy are different requirements. The adapter and Workspace must agree on supported inheritance, exclusions, and assignments before launch; unsupported policy does not degrade to a plain dictionary.

A process handle provides:

- bounded byte output with stream identity, explicit completion, and detectable gaps;
- exit observation independently of output drainage;
- stdin writes and EOF when enabled at creation;
- supported signals and termination requests, separate from observed exit;
- closure of its owned resources, terminating an owned command if still running and reporting unresolved cleanup.

Output retention is bounded and loss is explicit. Native sequence numbers, replay buffers, and cumulative text snapshots are adapter-local projections. The bridge cannot claim complete output after a provider reports a gap. If the native protocol cannot represent that loss, it fails explicitly instead of fabricating completeness. Cross-stream ordering is observed ordering unless the provider offers a stronger guarantee.

Exit does not discard unread final bytes. A native adapter whose consumer treats exit as final output must drain retained output before publishing that terminal signal, or document and reject a mode where faithful projection is impossible. Cleanup of an exited process still releases its handle.

## Requirements and Enforcement

Capabilities describe supported operations and semantics, not permission to use them. Each operation remains subject to provider authority and caller policy. Unsupported requirements known at admission fail before work starts; requirements discovered in a later native request fail before that operation's side effects.

Sandbox intent, managed networking, TTY mode, and symlink policy are not optional decorations. A bridge either enforces the requested semantics through supported target facilities or rejects the request. It must not silently drop them, run locally after a remote failure, or switch targets to bypass denial. An explicitly selected unsandboxed native mode is distinct from ignoring a sandbox request and still carries the caller's risk.

Workspace is not itself proof of isolation. Coverage depends on the [backend](../backends/00-overview.md): native history storage, configuration, networking, plugins, or other paths may remain outside the bridge. Applications requiring complete confinement must enforce it at the actual native runtime and provider boundaries.

## Failure Boundaries

| Observation                           | Meaning                                                                   |
| ------------------------------------- | ------------------------------------------------------------------------- |
| Unsupported or denied before dispatch | The requested operation did not execute through this boundary             |
| Provider reports an operation error   | Preserve known effects and the provider's outcome; do not infer rollback  |
| Connection lost after dispatch        | Effects may be unknown; do not blindly retry a mutation or process launch |
| Termination accepted                  | Stop was requested, not proof of exit or drainage                         |
| Handle closed successfully            | Owned live resources were settled; retained native history is unrelated   |

Failures remain typed at the Python boundary. Adapters translate them into native error categories without conflating missing files, unsupported behavior, denial, and transport loss.
