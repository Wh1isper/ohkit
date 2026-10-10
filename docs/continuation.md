---
title: History and workspace continuation
description: Resume native history or reconstruct selected context when changing execution targets.
---

Changing an execution target does not require mutating an existing native Thread. A host can keep its own logical conversation ID while either reopening native history or mapping that ID to a new native Thread seeded with selected context. Files, execution authority, and conversation history are separate migration decisions.

This guide records integration strategies and bounded evidence as of **2026-10-10**. It distinguishes implemented ohkit calls from upstream SDK/protocol operations and designs that still need agent-specific validation. It does not introduce a common `MessageHistory`, snapshot, `copy()`, or `inject()` API.

## Choose the operation

| Operation                          | Native identity | What carries forward                                          | What it does not establish                                             |
| ---------------------------------- | --------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Resume                             | Same            | History available to the selected native runtime/store        | Live processes, pending decisions, or a clean context                  |
| Native fork, then resume           | New             | Native transcript branch, subject to the backend's copy rules | Portable execution state or removal of old instructions                |
| Copy selected content, then inject | New             | Only the messages explicitly selected by the host             | An exact clone of the previous model request                           |
| New Thread plus handoff prompt     | New             | A summary or quoted transcript supplied as new user input     | Original message roles, native tool history, or zero-execution seeding |

Prefer resume when retaining the existing history is the goal. Prefer reconstruction when changing trust domains, intentionally omitting old instructions, or continuing without the native history store. A new working directory alone is not proof that old instructions disappeared from history.

| Backend | Existing ohkit resume                                                                      | Structured copy/inject route                                                             | Conservative cross-target strategy                                                                        |
| ------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Codex   | Ordinary native history; external-executor history rebinding is unavailable                | Native `thread/read` projection plus `thread/inject_items`; not public ohkit methods     | Create a new external Thread on B and inject selected user/assistant items                                |
| ACP     | Negotiated `session/resume`, otherwise `session/load`; can supply a new callback Workspace | No portable arbitrary-history import/injection operation in the inspected stable surface | Recreate the provider behind a compatible session namespace, or start a new session with a handoff prompt |
| Claude  | Reopens native history in a fresh SDK process; accepts a native `cwd`                      | Public SDK transcript fork/import/store operations, not a Codex-style live item injector | Resume or fork/resume for native continuity; new Thread plus selected handoff for a cleaner context       |

## Host-owned handoff boundary

1. Stop admitting new work to A. Drain or explicitly cancel its foreground Run and establish the outcome. A lost outcome is not permission to replay potentially executed tool calls.
2. Choose resume, fork, or selected reconstruction. Save the source native reference and intended destination mapping before abandoning the old owner.
3. Prepare B's files, tool configuration, credentials, and permissions independently. Copying history does not copy the working tree, install dependencies, migrate terminals, or authorize access to another target.
4. Create or reopen the destination through the appropriate backend. Confirm history selection and target routing before publishing the host's new active mapping; do not silently turn a refused resume into empty history.
5. Retire the old execution owner. It may remain as an archival history branch, but must not keep writing to a conversation that the host now treats as exclusively active elsewhere.

A handoff can preserve goals, decisions, completed observations, relevant edits, and remaining work. Preserve original roles when a verified native importer supports them. Historical tool output remains data, not current authority. Old approvals, credentials, executor IDs, terminal handles, and workspace-specific instructions should not be blindly imported. Tool-call/result pairs require consistent IDs and ordering; the text-only Codex evidence below does not validate arbitrary tool-history import.

When only a prompt is available, use an explicitly delimited handoff document, such as goals, verified facts, changed files, outstanding work, and quoted observations. Explain that it is historical data, then provide the current task separately. This is intentionally lossy. Sending past user turns one at a time is **not** history injection: each submission can start new agent work and repeat side effects.

## Codex: new external Thread plus selected injection

### Resume boundary

Ordinary `Codex.resume(ref)` continues native history in its compatible scope. The current external executor integration does not support selecting a replacement executor early enough in native resume/fork startup. Passing another cwd or copying a native reference is not a supported external rebinding mechanism. See the [Codex supported-mode matrix](codex.md).

### Reconstruction plan

The following is a **native-protocol integration plan**, not an executable public ohkit recipe:

1. Read the source's available conversation projection with `thread/read` and `includeTurns=true`, or use a host-maintained transcript.
2. Select transferable content. The verified path maps textual `userMessage` and `agentMessage` records to native Responses user/assistant message items; it does not copy every returned record.
3. Create Thread B with B's executor endpoint and cwd using the existing external Thread creation path. Let its native startup obtain the destination's instructions and environment.
4. Call native `thread/inject_items` on B with those selected items. The wire name contains an underscore. This appends history without starting a user Turn.
5. Submit the next ordinary Run. The host maps its logical conversation to B's new native ID.

There is no public ohkit read/inject wrapper yet. Do not build application integrations on the private RPC methods used in the investigation. Any future wrappers should remain backend-specific and separately expose reading a projection and injecting native items, leaving selection and migration policy to the host.

`thread/read` is **not an exact model-context getter**. In the isolated probe, both an injected assistant marker and a developer-instruction marker reached the actual next model request but were absent from the read projection. Flattening that projection into a large user prompt therefore cannot reconstruct every prior model input. The native `thread/resume.history` field is explicitly marked unstable for Codex Cloud in the inspected source; it is not this plan's import boundary.

### Verified evidence

Real Codex **0.162.0**, isolated HOME/CODEX_HOME, and a deterministic loopback model service were used with two authenticated executor endpoints and two temporary POSIX Workspace providers. No paid model calls or production credentials were used.

The destination had a different native ID; its actual model request contained A's selected goal and answer, B's `AGENTS.md` marker, and not A's workspace-instruction marker. Injection caused no additional model request. The subsequent command ran through B's executor and created its effect file only in B. This establishes selected text-history reconstruction, not arbitrary tool-history import, active-run injection, file replication, or an exact snapshot.

## ACP: resume a compatible namespace or hand off explicitly

### Native resume/load

For an agent with persistent history, ohkit already supports this call shape with an entered backend and an authorized reference:

```python
continued = await backend.resume(
    reference,
    cwd="/project",
    workspace=recreated_workspace,
)
```

The adapter starts a new agent process and binds callbacks to the supplied Workspace. It chooses advertised `session/resume`, which restores context without replay, or falls back to advertised `session/load`, which replays conversation updates before returning. ohkit deliberately suppresses load replay as new Run output. Neither operation recreates old terminal handles or pending permission handlers.

For a short-lived physical Workspace, the conservative design is to preserve the agent-visible namespace, for example `/project`, while the host recreates the provider behind it. The chosen agent must retain its native session store and must actually use the supplied callbacks for the operations that need relocation. Callback rebinding does not relocate the agent's own local I/O or history storage.

Do **not** infer that arbitrary A→B cwd changes are portable just because load/resume carry a `cwd` field. The pinned stable session-setup contract describes changing additional roots on load/resume while the request cwd matches the stored session cwd. Keep a compatible cwd by default; validate any changed-cwd behavior against the selected agent. The deterministic ohkit protocol peer is not evidence that every third-party agent accepts a different root.

### Copy/inject alternative

The inspected stable ACP surface has no general operation to append an arbitrary user/assistant/tool transcript to a new session without prompting. `session/update` replay is agent-to-client observation, not a client-to-agent history import API. The current ohkit adapter also exposes neither replay export nor unstable `session/fork`.

For a genuinely different namespace or unavailable native store:

1. Keep a host-owned transcript or handoff record while running A. A separate native client can observe `session/load` replay when supported, but current ohkit resume does not return that replay as history.
2. Create a new ACP Thread with B's cwd and Workspace.
3. Submit a selected handoff summary together with the next task as one normal text input. Treat this as a new Run, not silent history seeding.
4. Record the new native session ID under the host's logical conversation.

An individual agent may offer a native fork/import extension. That can improve fidelity only after its capabilities, history storage, target selection, and tool/permission behavior are verified; it is not a generic ACP guarantee. A replayed visible transcript is also not proof of the exact next model request.

## Claude: native resume, fork/resume, or selected handoff

Here a target means the Claude process's native working directory and filesystem. The ordinary Claude backend still does **not** accept an ohkit Workspace provider.

### Resume on a new working directory

With an entered backend and a compatible native history scope, the implemented call is:

```python
continued = await backend.resume(reference, cwd="/target/project-b")
result = await continued.run("Continue the task in project B.")
```

Each Run starts a new SDK process, so there is no need to mutate a running process's cwd. The native runtime must be able to find the saved session; the directory argument does not transfer history to another machine or storage configuration. Do not change `history_scope` merely to bypass a reference mismatch. Applications must establish actual store access and ownership.

A bounded probe with SDK **0.2.165** and bundled Claude Code **2.1.294** completed this flow using one isolated local history store and separate A/B directories. The next model request retained A's goal and answer, reported B as the primary working directory, and the controlled Write tool affected only B.

**It was not a clean instruction reset.** With project settings enabled and distinct `CLAUDE.md` markers, both A's old marker and B's new marker appeared in B's model request. Native resume is suitable for continuing compatible history, not for guaranteeing removal of old project instructions or crossing a trust boundary safely.

### Copy using the SDK's native fork

When the source should remain a separate branch, the public SDK supplies `fork_session(source_id, directory=source_cwd)` and `fork_session_via_store(...)`. These rewrite native session/message identities and parent chains rather than byte-copying a transcript under an unrelated ID. The filesystem helper's `directory` locates the **source** project; it is not a destination-directory parameter. Its branch is written under the source history project.

The application-level plan is:

1. Settle A and make its transcript durable in the selected native history store.
2. Invoke the SDK's fork operation and retain the returned new session ID. Run synchronous filesystem helpers off the application's async I/O loop.
3. Construct an explicit Claude `ThreadRef` for that new ID in the same authorized history scope, then use the existing `Claude.resume(..., cwd=B)` path.
4. Validate target execution and publish the new logical-to-native mapping.

This composition was also native-probed: the ID changed, old dialogue remained available, B was the working directory, and the file effect occurred only in B. Both project-instruction markers remained visible, just as with direct resume. `Claude.fork()` itself remains unavailable; this is an explicit upstream-SDK integration, not a newly advertised ohkit capability.

Fork is not a runtime snapshot. The inspected SDK omits file-undo history and filters sidechain/progress entries when constructing the main transcript branch. Do not promise copied live subagents, their execution handles, or a complete process tree. SDK filesystem helpers use their own history-directory resolution in the calling process; supplying `options.env` only to the Claude backend does not automatically configure those helpers' lookup environment.

### History on another machine or in a host-owned store

The public SDK provides `SessionStore`, `import_session_to_store`, and store-backed reading/fork helpers. This is **native transcript storage**, not a general role-message injection interface:

- Configure `ClaudeAgentOptions(session_store=store)` to mirror native transcript entries, or import an existing local transcript with `import_session_to_store`. Observe mirror failures and ensure the required history is durable before moving execution; model success alone does not prove successful remote replication.
- Store-backed resume loads entries before subprocess startup and materializes a temporary native history tree. The subprocess still writes local files; the store does not replace Claude's filesystem or tool executor.
- The SDK derives the lookup `project_key` from the requested cwd. Import retains the source on-disk project key; fork-via-store also reads and writes within its selected project key. Moving to a different cwd or storage namespace therefore needs an explicit host mapping or authorized copy of the history keys, including required subpaths. `cwd=B` alone does not migrate A's store entry.
- Preserve opaque entries rather than synthesizing native transcript JSONL from displayed messages. Use the SDK fork transform if a new native identity is required. A storage-level byte copy with an arbitrary new ID is not an equivalent fork.

The store relocation/key-mapping plan is supported by source inspection but was **not** part of the cross-directory native probe. Validate it against the chosen store before depending on it, including failed mirrors, missing entries, subagent subpaths, and destination history ownership.

### Selected-content reconstruction

For a cleaner boundary, read visible dialogue through the SDK's `get_session_messages`/store-backed equivalent or use the host's own records, select a handoff summary, create a fresh Claude Thread in B, and submit the summary plus current task as normal input. These readers return a conversation projection, not the complete model context or an importable native transcript.

No Codex-style public live item-injection operation was established in the inspected Claude SDK surface. Do not simulate it by streaming historic user prompts through `query()` or constructing undocumented session-file records. Native fork/resume is the higher-fidelity history path; a fresh Thread with a selected handoff is the deliberately lossy path that avoids automatically carrying the full old transcript.

## Evidence and limits

| Path                                      | Evidence                                                                         | Remaining limit                                                          |
| ----------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Codex new external B + selected injection | Actual 0.162.0 executable, actual model input and Workspace effects              | Text messages only; private native RPC probe, no public ohkit injector   |
| ACP resume/load + recreated callbacks     | Stable contract, SDK 0.12.1, deterministic stdio peer and real Workspace effects | Changed-cwd and third-party-agent behavior must be validated separately  |
| Claude direct resume in B                 | Actual SDK 0.2.165 / CLI 2.1.294, model input and file effect                    | Same local history store; old instruction content persisted              |
| Claude SDK fork + resume in B             | Same native probe, distinct session identity                                     | Not `Claude.fork()`; not a full runtime/subagent snapshot                |
| Claude store migration                    | SDK source and public storage interfaces                                         | Destination key mapping and remote-store behavior not native-probed here |

The repository's regular backend tests remain the maintained compatibility gate. These additional migration probes establish the bounded observations above, not a guarantee for every provider, SDK update, or history format.

### Primary sources

- Codex 0.162.0: [native method declaration](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server-protocol/src/protocol/common.rs), [read/resume/inject parameters](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server-protocol/src/protocol/v2/thread.rs), and [injection tests](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/app-server/tests/suite/v2/thread_inject_items.rs).
- ACP pinned stable contract: [session creation, load, resume, and working directories](https://github.com/agentclientprotocol/agent-client-protocol/blob/1c2b84c785c923ed283a4e7ea3badb2422596418/docs/protocol/v1/session-setup.mdx) and [prompt lifecycle](https://github.com/agentclientprotocol/agent-client-protocol/blob/1c2b84c785c923ed283a4e7ea3badb2422596418/docs/protocol/v1/prompt-turn.mdx).
- Claude SDK 0.2.165: [public exports](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/__init__.py), [fork transforms](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/_internal/session_mutations.py), [session readers](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/_internal/sessions.py), [store types](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/types.py), [local transcript import](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/_internal/session_import.py), and [resume materialization](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.165/src/claude_agent_sdk/_internal/session_resume.py).
