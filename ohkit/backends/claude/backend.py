"""Ordinary Claude execution; native SDK owns its drain and history semantics."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from types import TracebackType
from uuid import uuid4

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ProcessError,
    ResultError,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from ..._json import obj
from ...errors import BusyError, InactiveRunError, UnavailableError, UnknownOutcomeError, UnsupportedError
from ...execution import Run, Thread, _settle
from ...values import (
    ApprovalChoice,
    ApprovalRequest,
    Capabilities,
    ContentEvent,
    Failure,
    Handlers,
    Input,
    InteractionEvent,
    JSONValue,
    LifecycleEvent,
    NativeData,
    NativeEvent,
    Outcome,
    Result,
    Text,
    ThreadRef,
    ToolEvent,
    Usage,
    UsageEvent,
)

CAPABILITIES = Capabilities(resume=True, approvals=True)


def _native(value: object) -> NativeData:
    import json

    # Upstream dataclasses contain JSON-shaped native fields. Validate once at our boundary.
    return NativeData("claude", json.dumps(value, ensure_ascii=False, allow_nan=False))


def _count(data: dict[str, JSONValue], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class Claude:
    """History-continuous Threads using one SDK-owned process per Run.

    Native SDK options configure tools, models, hooks and credentials. ohkit owns
    session selection, permission callback, input admission and complete messages.
    Do not mutate the supplied native configuration while the backend is in use.
    """

    capabilities = CAPABILITIES

    def __init__(
        self,
        *,
        options: ClaudeAgentOptions | None = None,
        event_capacity: int = 1024,
        control_timeout: float = 60,
        cleanup_timeout: float = 10,
        history_scope: str | None = None,
    ) -> None:
        self.options = options or ClaudeAgentOptions()
        if (
            self.options.resume
            or self.options.session_id
            or self.options.fork_session
            or self.options.continue_conversation
            or self.options.resume_session_at
            or self.options.resume_drops_turn
        ):
            raise ValueError("Use ohkit new_thread/resume to select conversation history")
        owned_flags = {
            "resume",
            "session-id",
            "continue",
            "fork-session",
            "resume-session-at",
            "resume-drops-turn",
            "no-session-persistence",
            "input-format",
            "output-format",
            "include-partial-messages",
            "permission-prompt-tool",
        }
        if owned_flags.intersection(self.options.extra_args):
            raise ValueError("Native extra_args cannot override ohkit-owned execution controls")
        if self.options.permission_prompt_tool_name is not None:
            raise ValueError("ohkit owns native permission routing")
        if self.options.can_use_tool is not None:
            raise ValueError("Use Run Handlers.approval; ohkit owns the SDK permission callback")
        if self.options.include_partial_messages:
            raise UnsupportedError("Claude currently projects complete message blocks, not partial deltas")
        if event_capacity < 1 or control_timeout <= 0 or cleanup_timeout <= 0:
            raise ValueError("Capacities and timeouts must be positive")
        self.event_capacity = event_capacity
        self.control_timeout = control_timeout
        self.cleanup_timeout = cleanup_timeout
        scope = (
            self.options.cli_path,
            self.options.env.get("CLAUDE_CONFIG_DIR", os.environ.get("CLAUDE_CONFIG_DIR")),
            self.options.env.get("HOME", os.path.expanduser("~")),
        )
        self._scope = history_scope or hashlib.sha256(repr(scope).encode()).hexdigest()
        self._threads: dict[str, _Binding] = {}
        self._entered = False
        self._closed = False
        self._closing: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Claude:
        if self._entered or self._closed:
            raise UnavailableError("Claude contexts cannot be reused")
        self._entered = True
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.close()

    async def new_thread(self, *, cwd: str | None = None) -> Thread:
        return self._attach(str(uuid4()), cwd, False)

    async def resume(self, ref: ThreadRef, *, cwd: str | None = None) -> Thread:
        if ref.backend != "claude" or ref.scope != self._scope:
            raise ValueError("Thread reference belongs to another backend/history scope")
        previous = self._threads.get(ref.id)
        if previous is not None:
            if previous.thread._active is not None:
                raise BusyError("Cannot reopen active native history")
            previous.thread._available = False
            if cwd is None:
                cwd = previous.cwd
        return self._attach(ref.id, cwd, True)

    async def fork(self, ref: ThreadRef, *, cwd: str | None = None) -> Thread:
        raise UnsupportedError("Claude history fork is not enabled by this adapter")

    def _attach(self, identity: str, cwd: str | None, resume: bool) -> Thread:
        if not self._entered or self._closed:
            raise UnavailableError("Enter an available Claude context before use")
        binding = _Binding(self, cwd, resume)
        thread = Thread(ThreadRef("claude", identity, self._scope), CAPABILITIES, binding, self.event_capacity)
        binding.thread = thread
        self._threads[identity] = binding
        return thread

    async def close(self) -> None:
        if self._closing is None:
            self._closed = True
            self._closing = asyncio.create_task(self._close())
        await _settle(self._closing)

    async def _close(self) -> None:
        results = await asyncio.gather(
            *(binding.thread.close() for binding in self._threads.values()), return_exceptions=True
        )
        errors = [value for value in results if isinstance(value, Exception)]
        if errors:
            raise ExceptionGroup("Claude cleanup failed", errors)


class _Binding:
    def __init__(self, backend: Claude, cwd: str | None, resume: bool) -> None:
        self.backend = backend
        self.cwd = cwd
        self.resume = resume
        self.thread: Thread

    def driver(self, run: Run, handlers: Handlers) -> _Driver:
        return _Driver(self, run, handlers)

    async def close(self) -> None:
        # Native process resources belong to each Run, not to an idle history reference.
        pass


class _Driver:
    def __init__(self, binding: _Binding, run: Run, handlers: Handlers) -> None:
        self.binding = binding
        self.run = run
        self.handlers = handlers
        self.client: ClaudeSDKClient | None = None
        self.task: asyncio.Task[None] | None = None
        self.starting: asyncio.Task[None] | None = None
        self.cancellation: asyncio.Task[None] | None = None
        self.closing: asyncio.Task[None] | None = None
        self.disconnecting: asyncio.Task[None] | None = None
        self.decisions: set[asyncio.Task[ApprovalChoice]] = set()
        self.finished = False
        self.output = ""
        self.submitted = False
        self.forced_close = False
        self.activity_after_result = False
        self.last: ResultMessage | None = None
        self.outcome: Outcome = "completed"
        self.failure: Failure | None = None
        self.usage: Usage | None = None

    async def start(self, input: Input) -> None:
        if self.closing is not None:
            raise UnavailableError("Claude Run was closed before startup")
        self.starting = asyncio.create_task(self._start(input))
        await asyncio.shield(self.starting)

    async def _start(self, input: Input) -> None:
        values = (Text(input),) if isinstance(input, str) else input
        if not values:
            raise ValueError("Run input cannot be empty")
        if not all(isinstance(value, Text) for value in values):
            raise UnsupportedError("Claude currently accepts text input; no implicit local image reads")
        blocks = [{"type": "text", "text": value.text} for value in values if isinstance(value, Text)]
        native_options = replace(
            self.binding.backend.options,
            cwd=self.binding.cwd if self.binding.cwd is not None else self.binding.backend.options.cwd,
            session_id=None if self.binding.resume else self.run.thread.id,
            resume=self.run.thread.id if self.binding.resume else None,
            can_use_tool=self._permission,
        )
        self.client = ClaudeSDKClient(options=native_options)

        async def prompt() -> AsyncIterator[dict[str, object]]:
            self.submitted = True
            yield {
                "type": "user",
                "message": {"role": "user", "content": blocks},
                "session_id": self.run.thread.id,
                "parent_tool_use_id": None,
            }

        try:
            async with asyncio.timeout(self.binding.backend.control_timeout):
                await self.client.connect(prompt=prompt())
        except BaseException:
            self.binding.thread._available = False
            await self._disconnect()
            raise
        self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "started"))
        self.task = asyncio.create_task(self._execute())

    async def _execute(self) -> None:
        assert self.client is not None
        try:
            # The single-input iterable delegates native background/idle draining to
            # the SDK. The first ResultMessage is deliberately NOT the Run boundary.
            async for message in self.client.receive_messages():
                self._message(message)
            if self.last is None or self.activity_after_result or self.forced_close:
                raise UnknownOutcomeError("Claude ended without complete result evidence")
            self.binding.resume = True
        except Exception as exc:
            # Native failed/aborted results deliberately exit 1. Preserve only
            # matching terminal evidence, not a later transport crash.
            if (
                isinstance(exc, ProcessError)
                and exc.exit_code == 1
                and self.last is not None
                and (
                    self.last.terminal_reason in ("aborted_streaming", "aborted_tools")
                    or (
                        isinstance(exc, ResultError)
                        and self.last.is_error
                        and exc.session_id == self.last.session_id
                        and exc.subtype == self.last.subtype
                        and exc.terminal_reason == self.last.terminal_reason
                        and exc.result == self.last.result
                        and exc.api_error_status == self.last.api_error_status
                    )
                )
                and not self.activity_after_result
                and not self.forced_close
            ):
                self.binding.resume = True
            else:
                self.outcome = "unknown"
                self.failure = Failure("connection_lost", str(exc))
                self.binding.thread._available = False
        finally:
            self.finished = True
            for decision in self.decisions:
                decision.cancel()
            await asyncio.gather(*self.decisions, return_exceptions=True)
            if self.cancellation is not None:
                await asyncio.gather(self.cancellation, return_exceptions=True)
            try:
                await self._disconnect()
            except Exception as exc:
                self.binding.thread._available = False
                self.outcome = "unknown"
                self.failure = Failure("cleanup_failed", str(exc))
            last = self.last
            self.run._finish(
                Result(
                    self.run.thread,
                    self.run.id,
                    self.outcome,
                    self.output,
                    usage=self.usage,
                    failure=self.failure,
                    native_status=(last.terminal_reason or last.subtype) if last else None,
                    native=_native(asdict(last)) if last else None,
                )
            )

    def _message(self, message: object) -> None:
        if isinstance(message, AssistantMessage):
            if message.parent_tool_use_id is not None:
                self.run._emit(
                    NativeEvent(self.run.thread, self.run.id, "subagent/assistant", _native(asdict(message)))
                )
                return
            self.activity_after_result = True
            for block in message.content:
                if isinstance(block, TextBlock):
                    self.output += block.text
                    self.run._emit(ContentEvent(self.run.thread, self.run.id, "assistant", block.text, "assistant"))
                elif isinstance(block, ThinkingBlock):
                    self.run._emit(ContentEvent(self.run.thread, self.run.id, "reasoning", block.thinking, "reasoning"))
                elif isinstance(block, ToolUseBlock):
                    self.run._emit(
                        ToolEvent(self.run.thread, self.run.id, block.id, block.name, "started", _native(asdict(block)))
                    )
        elif isinstance(message, UserMessage):
            if isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        self.run._emit(
                            ToolEvent(
                                self.run.thread,
                                self.run.id,
                                block.tool_use_id,
                                block.tool_use_id,
                                "completed",
                                _native(asdict(block)),
                            )
                        )
        elif isinstance(message, ResultMessage):
            if message.session_id != self.run.thread.id:
                raise UnknownOutcomeError("Claude returned a different native history identity")
            self.last = message
            self.activity_after_result = False
            if message.result is not None:
                self.output = message.result
            if message.terminal_reason in ("aborted_streaming", "aborted_tools"):
                if self.outcome != "failed":
                    self.outcome = "cancelled"
            elif message.is_error:
                self.outcome = "failed"
                self.failure = Failure(
                    message.subtype, "; ".join(message.errors or [message.result or "Claude execution failed"])
                )
            if message.usage is not None:
                data = obj(_native(message.usage).decode())
                self.usage = Usage(
                    input_tokens=_count(data, "input_tokens"),
                    output_tokens=_count(data, "output_tokens"),
                    cached_input_tokens=_count(data, "cache_read_input_tokens"),
                )
                self.run._emit(UsageEvent(self.run.thread, self.run.id, self.usage))
            self.run._emit(NativeEvent(self.run.thread, self.run.id, "result", _native(asdict(message))))
        elif isinstance(message, SystemMessage):
            self.run._emit(
                NativeEvent(self.run.thread, self.run.id, "system/" + message.subtype, _native(message.data))
            )

    async def _permission(
        self, tool_name: str, input: dict[str, object], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        denied = PermissionResultDeny(message="Not approved by the caller")
        if self.finished or self.cancellation is not None:
            return denied
        choices = (ApprovalChoice("accept", "action"), ApprovalChoice("decline", "action"))
        request = ApprovalRequest(
            self.run.thread,
            self.run.id,
            "permission_" + uuid4().hex,
            "tool",
            context.tool_use_id or "tool",
            context.decision_reason,
            choices,
            native=_native(
                {
                    "tool_name": tool_name,
                    "input": input,
                    "permission_suggestions": [asdict(value) for value in context.suggestions],
                }
            ),
        )
        self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "requested", request))
        handler = self.handlers.approval
        if handler is None:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "answered"))
            return denied

        async def decide() -> ApprovalChoice:
            return await handler(request)

        task = asyncio.create_task(decide())
        self.decisions.add(task)
        try:
            choice = await task
            if self.finished or self.cancellation is not None:
                raise asyncio.CancelledError
            if choice not in choices:
                raise ValueError("Approval handler must return an offered choice unchanged")
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "answered"))
            return PermissionResultAllow() if choice.kind == "accept" else denied
        except asyncio.CancelledError:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "withdrawn"))
            # SDK cancellation withdraws the native request; never send a stale denial.
            raise
        except Exception:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "failed"))
            return denied
        finally:
            self.decisions.discard(task)

    async def steer(self, input: Input) -> None:
        raise UnsupportedError("Claude streaming writes do not establish ohkit steering admission")

    async def cancel(self) -> None:
        if self.finished:
            raise InactiveRunError("Run is terminal")
        if self.cancellation is None:
            self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "cancelling"))
            self.cancellation = asyncio.create_task(self._cancel())
        await asyncio.shield(self.cancellation)

    async def _cancel(self) -> None:
        assert self.client is not None
        async with asyncio.timeout(self.binding.backend.control_timeout):
            await self.client.interrupt()

    def overflow(self) -> None:
        if self.cancellation is None and not self.finished:
            self.cancellation = asyncio.create_task(self._cancel())

    async def _disconnect(self) -> None:
        if self.disconnecting is None:

            async def disconnect() -> None:
                if self.client is not None:
                    await self.client.disconnect()

            self.disconnecting = asyncio.create_task(disconnect())
        await _settle(self.disconnecting)

    async def close(self) -> None:
        if self.closing is None:
            self.closing = asyncio.create_task(self._close())
        await _settle(self.closing)

    async def _close(self) -> None:
        # connect() can load caller-owned history before creating a transport.
        # Settle that bounded startup before caching any disconnect operation.
        if self.starting is not None:
            await asyncio.gather(self.starting, return_exceptions=True)
        if self.task is None:
            await self._disconnect()
            return
        try:
            async with asyncio.timeout(self.binding.backend.cleanup_timeout):
                if not self.finished:
                    await self.cancel()
                await asyncio.shield(self.task)
        except Exception as exc:
            self.binding.thread._available = False
            self.forced_close = True
            await self._disconnect()
            await self.task
            raise UnknownOutcomeError("Claude foreground cleanup could not establish completion") from exc
