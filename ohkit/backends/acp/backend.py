"""Stable ACP execution using the upstream Python SDK and its wire models."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import hashlib
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from types import TracebackType
from uuid import uuid4

from acp import Client, RequestError, spawn_agent_process
from acp import schema as wire
from acp.client.connection import ClientSideConnection
from acp.interfaces import Agent
from pydantic import BaseModel

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
    LifecycleEvent,
    NativeData,
    NativeEvent,
    Outcome,
    Result,
    Text,
    ThreadRef,
    ToolEvent,
)
from ...workspace import ProcessRequest, Workspace
from ._workspace import WorkspaceCallbacks


def _native(value: BaseModel) -> NativeData:
    return NativeData("acp", value.model_dump_json(by_alias=True, exclude_none=True))


@dataclass(frozen=True, slots=True)
class ACPOptions:
    command: tuple[str, ...]
    process_cwd: str | None = None
    env: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    history_scope: str | None = None
    event_capacity: int = 1024
    control_timeout: float = 30
    cleanup_timeout: float = 10
    terminal_output_limit: int = 1_048_576
    terminal_limit: int = 256

    def __post_init__(self) -> None:
        if not self.command or self.event_capacity < 1 or self.terminal_limit < 1:
            raise ValueError("Command and positive capacities are required")
        if self.control_timeout <= 0 or self.cleanup_timeout <= 0 or self.terminal_output_limit < 0:
            raise ValueError("Invalid timeout or terminal output limit")


class ACP:
    """Own one agent process per live Thread, with optional borrowed Workspace I/O.

    Agent installation, authentication and history storage are application-owned.
    env overlays the SDK's trimmed subprocess environment, not the entire host env.
    """

    def __init__(self, *, options: ACPOptions) -> None:
        self.options = options
        scope = (options.command, options.process_cwd or os.getcwd(), options.env)
        self._scope = options.history_scope or hashlib.sha256(repr(scope).encode()).hexdigest()
        self._threads: dict[str, _Binding] = {}
        self._lock = asyncio.Lock()
        self._entered = False
        self._closed = False
        self._closing: asyncio.Task[None] | None = None

    async def __aenter__(self) -> ACP:
        if self._entered or self._closed:
            raise UnavailableError("ACP contexts cannot be reused")
        self._entered = True
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.close()

    async def new_thread(self, *, cwd: str, workspace: Workspace | None = None) -> Thread:
        return await self._open(cwd, workspace, None)

    async def resume(self, ref: ThreadRef, *, cwd: str, workspace: Workspace | None = None) -> Thread:
        return await self._open(cwd, workspace, ref)

    async def fork(self, ref: ThreadRef, *, cwd: str, workspace: Workspace | None = None) -> Thread:
        raise UnsupportedError("ACP session/fork is unstable and is not enabled")

    async def _open(self, cwd: str, workspace: Workspace | None, ref: ThreadRef | None) -> Thread:
        async with self._lock:
            if not self._entered or self._closed:
                raise UnavailableError("Enter an available ACP context before use")
            if ref is not None:
                if ref.backend != "acp" or ref.scope != self._scope:
                    raise ValueError("Thread reference belongs to another backend/history scope")
                previous = self._threads.get(ref.id)
                if previous is not None:
                    if previous.thread._active is not None:
                        raise BusyError("Cannot reopen active native history")
                    await previous.thread.close()
            binding = _Binding(self.options, cwd, workspace)
            try:
                identity, capabilities = await binding.open(ref.id if ref else None)
                if self._closed:
                    raise UnavailableError("ACP closed during Thread creation")
                if identity in self._threads and ref is None:
                    raise UnavailableError("Agent returned a history identity already owned here")
                thread = Thread(
                    ThreadRef("acp", identity, self._scope), capabilities, binding, self.options.event_capacity
                )
                binding.thread = thread
                self._threads[identity] = binding
                return thread
            except BaseException:
                await binding.close()
                raise

    async def close(self) -> None:
        if self._closing is None:
            self._closed = True
            for binding in self._threads.values():
                binding.thread._available = False
            self._closing = asyncio.create_task(self._close())
        await _settle(self._closing)

    async def _close(self) -> None:
        async with self._lock:
            results = await asyncio.gather(
                *(binding.thread.close() for binding in self._threads.values()), return_exceptions=True
            )
            errors = [value for value in results if isinstance(value, Exception)]
            if errors:
                raise ExceptionGroup("ACP cleanup failed", errors)


class _Binding(Client):
    def __init__(self, options: ACPOptions, cwd: str, workspace: Workspace | None) -> None:
        self.options = options
        self.cwd = cwd
        self.workspace = (
            WorkspaceCallbacks(workspace, cwd, options.terminal_output_limit, options.terminal_limit)
            if workspace
            else None
        )
        self.stack = AsyncExitStack()
        self.connection: ClientSideConnection
        self.thread: Thread
        self.identity: str | None = None
        self.active: _Driver | None = None
        self.closing: asyncio.Task[None] | None = None
        self.agent_capabilities = wire.AgentCapabilities()

    async def open(self, identity: str | None) -> tuple[str, Capabilities]:
        options = self.options
        self.connection, _ = await self.stack.enter_async_context(
            spawn_agent_process(
                self,
                *options.command,
                cwd=options.process_cwd,
                env=dict(options.env),
                transport_kwargs={
                    "stderr": asyncio.subprocess.DEVNULL,
                    "limit": 4 * 1024 * 1024,
                    "shutdown_timeout": options.cleanup_timeout,
                },
            )
        )
        async with asyncio.timeout(options.control_timeout):
            response = await self.connection.initialize(
                protocol_version=1,
                client_info=wire.Implementation(name="ohkit", version="0.0.0"),
                client_capabilities=wire.ClientCapabilities(
                    fs=wire.FileSystemCapabilities(
                        read_text_file=self.workspace is not None, write_text_file=self.workspace is not None
                    ),
                    terminal=self.workspace is not None,
                ),
            )
            if response.protocol_version != 1:
                raise UnsupportedError("Agent did not negotiate stable ACP v1")
            self.agent_capabilities = response.agent_capabilities or wire.AgentCapabilities()
            sessions = self.agent_capabilities.session_capabilities or wire.SessionCapabilities()
            capabilities = Capabilities(
                resume=bool(self.agent_capabilities.load_session) or sessions.resume is not None,
                fork=False,
                approvals=True,
                workspace=self.workspace is not None,
            )
            if identity is None:
                self.identity = (await self.connection.new_session(cwd=self.cwd)).session_id
            else:
                self.identity = identity
                if sessions.resume is not None:
                    await self.connection.resume_session(session_id=identity, cwd=self.cwd)
                elif self.agent_capabilities.load_session:
                    await self.connection.load_session(session_id=identity, cwd=self.cwd)
                else:
                    raise UnsupportedError("Agent does not advertise history resume/load")
        assert self.identity is not None
        return self.identity, capabilities

    def driver(self, run: Run, handlers: Handlers) -> _Driver:
        self.active = _Driver(self, run, handlers)
        return self.active

    def _session(self, session_id: str) -> None:
        if self.identity != session_id or self.closing is not None:
            raise RequestError.invalid_params({"details": "Unknown or closed session"})

    def _workspace(self, session_id: str) -> WorkspaceCallbacks:
        self._session(session_id)
        if self.workspace is None:
            raise RequestError.method_not_found("Workspace callbacks were not advertised")
        return self.workspace

    async def session_update(self, session_id: str, update: object, **kwargs: object) -> None:
        # Load replay and idle updates are not output of a new Run.
        if session_id == self.identity and self.active is not None and not self.active.finished:
            self.active.update(update)

    async def request_permission(
        self, session_id: str, tool_call: wire.ToolCallUpdate, options: list[wire.PermissionOption], **kwargs: object
    ) -> wire.RequestPermissionResponse:
        self._session(session_id)
        if self.active is None or self.active.finished:
            return wire.RequestPermissionResponse(outcome=wire.DeniedOutcome(outcome="cancelled"))
        return await self.active.permission(tool_call, options)

    async def read_text_file(
        self, session_id: str, path: str, line: int | None = None, limit: int | None = None, **kwargs: object
    ) -> wire.ReadTextFileResponse:
        return await self._workspace(session_id).read(path, line, limit)

    async def write_text_file(
        self, session_id: str, path: str, content: str, **kwargs: object
    ) -> wire.WriteTextFileResponse:
        return await self._workspace(session_id).write(path, content)

    async def create_terminal(
        self,
        session_id: str,
        command: str,
        args: list[str] | None = None,
        env: list[wire.EnvVariable] | None = None,
        cwd: str | None = None,
        output_byte_limit: int | None = None,
        **kwargs: object,
    ) -> wire.CreateTerminalResponse:
        workspace = self._workspace(session_id)
        request = ProcessRequest(
            argv=(command, *(args or [])),
            cwd=cwd if cwd is not None else self.cwd,
            env=tuple((entry.name, entry.value) for entry in env or []),
        )
        return await workspace.create(request, output_byte_limit)

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs: object) -> wire.TerminalOutputResponse:
        return self._workspace(session_id).get(terminal_id).snapshot()

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> wire.WaitForTerminalExitResponse:
        return await self._workspace(session_id).get(terminal_id).wait()

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs: object) -> wire.KillTerminalResponse:
        await self._workspace(session_id).get(terminal_id).process.signal("kill")
        return wire.KillTerminalResponse()

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: object
    ) -> wire.ReleaseTerminalResponse:
        await self._workspace(session_id).release(terminal_id)
        return wire.ReleaseTerminalResponse()

    def on_connect(self, conn: Agent) -> None:
        pass

    async def complete_elicitation(self, elicitation_id: str, **kwargs: object) -> None:
        pass

    async def ext_method(self, method: str, params: dict[str, object]) -> dict[str, object]:
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method: str, params: dict[str, object]) -> None:
        pass

    async def create_elicitation(
        self, message: str, mode: wire.ElicitationMode, **kwargs: object
    ) -> wire.CreateElicitationResponse:
        raise RequestError.method_not_found("Elicitation is not advertised")

    async def close(self) -> None:
        if self.closing is None:
            self.closing = asyncio.create_task(self._close())
        await _settle(self.closing)

    async def _close(self) -> None:
        try:
            if self.workspace is not None:
                await self.workspace.close()
        finally:
            await self.stack.aclose()


class _Driver:
    def __init__(self, binding: _Binding, run: Run, handlers: Handlers) -> None:
        self.binding = binding
        self.run = run
        self.handlers = handlers
        self.output = ""
        self.finished = False
        self.task: asyncio.Task[None] | None = None
        self.cancellation: asyncio.Task[None] | None = None
        self.decisions: set[asyncio.Task[ApprovalChoice]] = set()
        self.closing: asyncio.Task[None] | None = None

    async def start(self, input: Input) -> None:
        values = (Text(input),) if isinstance(input, str) else input
        if not values:
            raise ValueError("Run input cannot be empty")
        if not all(isinstance(value, Text) for value in values):
            raise UnsupportedError("ACP currently accepts text input; local files are never read on the controller")
        prompt = [wire.TextContentBlock(type="text", text=value.text) for value in values if isinstance(value, Text)]
        self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "started"))
        self.task = asyncio.create_task(self._execute(prompt))

    async def _execute(self, prompt: list[wire.TextContentBlock]) -> None:
        outcome: Outcome = "unknown"
        status: str | None = None
        failure = None
        native = None
        try:
            response = await self.binding.connection.prompt(session_id=self.run.thread.id, prompt=list(prompt))
            status = response.stop_reason
            native = _native(response)
            outcome = "cancelled" if status == "cancelled" else "completed"
        except RequestError as exc:
            outcome = "failed"
            failure = Failure(str(exc.code), str(exc))
        except Exception as exc:
            failure = Failure("connection_lost", str(exc))
            self.binding.thread._available = False
        finally:
            self.finished = True
            for decision in self.decisions:
                decision.cancel()
            await asyncio.gather(*self.decisions, return_exceptions=True)
            if self.cancellation is not None:
                results = await asyncio.gather(self.cancellation, return_exceptions=True)
                if isinstance(results[0], Exception) and outcome == "unknown":
                    failure = Failure("cancel_unknown", str(results[0]))
            self.run._finish(
                Result(
                    self.run.thread,
                    self.run.id,
                    outcome,
                    self.output,
                    failure=failure,
                    native_status=status,
                    native=native,
                )
            )

    def update(self, update: object) -> None:
        if isinstance(update, (wire.AgentMessageChunk, wire.AgentThoughtChunk)) and isinstance(
            update.content, wire.TextContentBlock
        ):
            channel = "assistant" if isinstance(update, wire.AgentMessageChunk) else "reasoning"
            if channel == "assistant":
                self.output += update.content.text
            self.run._emit(ContentEvent(self.run.thread, self.run.id, channel, update.content.text, channel))
        elif isinstance(update, (wire.ToolCallStart, wire.ToolCallProgress)):
            phase = "completed" if update.status in ("completed", "failed") else "started"
            self.run._emit(
                ToolEvent(
                    self.run.thread,
                    self.run.id,
                    update.tool_call_id,
                    update.title or update.tool_call_id,
                    phase,
                    _native(update),
                )
            )
        elif isinstance(update, BaseModel):
            self.run._emit(NativeEvent(self.run.thread, self.run.id, "session/update", _native(update)))

    async def permission(
        self, tool: wire.ToolCallUpdate, options: list[wire.PermissionOption]
    ) -> wire.RequestPermissionResponse:
        denied = wire.RequestPermissionResponse(outcome=wire.DeniedOutcome(outcome="cancelled"))
        if self.finished or self.cancellation is not None:
            return denied
        choices = tuple(ApprovalChoice("native", "native", _native(option)) for option in options)
        request = ApprovalRequest(
            self.run.thread,
            self.run.id,
            "permission_" + uuid4().hex,
            "tool",
            tool.tool_call_id,
            tool.title,
            choices,
            native=_native(tool),
        )
        self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "requested", request))
        if self.cancellation is not None:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "withdrawn"))
            return denied
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
                raise ValueError("Approval handler must return an offered native choice unchanged")
            selected = options[choices.index(choice)].option_id
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "answered"))
            return wire.RequestPermissionResponse(outcome=wire.AllowedOutcome(outcome="selected", option_id=selected))
        except asyncio.CancelledError:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "withdrawn"))
            if self.binding.closing is not None:
                # SDK shutdown has stopped its sender. Propagate cancellation
                # instead of queuing a denial that can never be delivered.
                raise
            return denied
        except Exception:
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, request.id, "failed"))
            if self.binding.closing is not None:
                raise asyncio.CancelledError from None
            return denied
        finally:
            self.decisions.discard(task)

    async def steer(self, input: Input) -> None:
        raise UnsupportedError("Stable ACP has no active steering contract")

    async def cancel(self) -> None:
        if self.finished:
            raise InactiveRunError("Run is terminal")
        await asyncio.shield(self._begin_cancel())

    def _begin_cancel(self) -> asyncio.Task[None]:
        for decision in self.decisions:
            decision.cancel()
        if self.cancellation is None:
            self.cancellation = asyncio.create_task(self._cancel())
            self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "cancelling"))
        return self.cancellation

    async def _cancel(self) -> None:
        async with asyncio.timeout(self.binding.options.control_timeout):
            await self.binding.connection.cancel(session_id=self.run.thread.id)

    def overflow(self) -> None:
        if not self.finished:
            self._begin_cancel()

    async def close(self) -> None:
        if self.closing is None:
            self.closing = asyncio.create_task(self._close())
        await _settle(self.closing)

    async def _close(self) -> None:
        if self.task is None:
            self.binding.active = None
            return
        try:
            async with asyncio.timeout(self.binding.options.cleanup_timeout):
                if not self.finished:
                    await self.cancel()
                await asyncio.shield(self.task)
        except Exception as exc:
            self.binding.thread._available = False
            await self.binding.close()
            await self.task
            raise UnknownOutcomeError("ACP foreground cleanup could not establish completion") from exc
        finally:
            self.binding.active = None
