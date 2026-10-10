"""Codex app-server v2 control against the generated compatibility baseline."""

# pyright: reportPrivateUsage=false
# Adapters cooperate with private shared lifecycle hooks; these are not public API.
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import replace
from types import TracebackType
from typing import Literal
from uuid import uuid4

from ..._json import native, obj, string
from ...errors import (
    BusyError,
    CleanupError,
    InactiveRunError,
    NativeRejectedError,
    ProtocolError,
    UnavailableError,
    UnknownOutcomeError,
    UnsupportedError,
)
from ...execution import Run, Thread, _settle
from ...values import (
    ApprovalRequest,
    Capabilities,
    ContentEvent,
    Failure,
    Handlers,
    Image,
    Input,
    InteractionEvent,
    JSONValue,
    LifecycleEvent,
    LocalImage,
    NativeEvent,
    Outcome,
    QuestionRequest,
    Result,
    Text,
    ThreadRef,
    ToolEvent,
    Usage,
    UsageEvent,
)
from . import _generated as wire
from ._interactions import approval, approval_response, default_choice, question_response, questions
from ._rpc import RPC, RequestID
from ._transport import Stdio, WebSocket, local_scope
from ._version import CODEX_VERSION
from ._wire import decode, encode
from .options import CodexExecutor, CodexOptions, CodexThreadOptions

CAPABILITIES = Capabilities(steer=True, resume=True, fork=True, approvals=True, questions=True)
type Delta = (
    wire.AgentMessageDeltaNotification
    | wire.ReasoningSummaryTextDeltaNotification
    | wire.ReasoningTextDeltaNotification
    | wire.CommandExecutionOutputDeltaNotification
)
_DELTA_MODELS: dict[str, tuple[type[Delta], Literal["assistant", "reasoning", "tool"]]] = {
    "item/agentMessage/delta": (wire.AgentMessageDeltaNotification, "assistant"),
    "item/reasoning/summaryTextDelta": (wire.ReasoningSummaryTextDeltaNotification, "reasoning"),
    "item/reasoning/textDelta": (wire.ReasoningTextDeltaNotification, "reasoning"),
    "item/commandExecution/outputDelta": (wire.CommandExecutionOutputDeltaNotification, "tool"),
}


type NativeInput = wire.TextUserInput | wire.UrlUserInput | wire.LocalImageUserInput


def _input_item(value: object) -> NativeInput:
    if isinstance(value, Text):
        return wire.TextUserInput(type="text", text=value.text, text_elements=[])
    if isinstance(value, Image):
        return wire.UrlUserInput(type="image", url=value.url)
    if isinstance(value, LocalImage):
        return wire.LocalImageUserInput(type="localImage", path=value.path)
    raise TypeError("Run input requires Text, Image, or LocalImage values")


def _input(input: Input) -> list[NativeInput]:
    values = (Text(input),) if isinstance(input, str) else input
    if not values:
        raise ValueError("Run input cannot be empty")
    return [_input_item(value) for value in values]


class Codex:
    """Own a stdio app-server, or own a connection to a borrowed remote service.

    Native configuration stays on the app-server host. An optional executor
    endpoint selects application-hosted Workspace I/O independently of control.
    """

    capabilities = replace(CAPABILITIES, workspace=True)
    tested_native_version = CODEX_VERSION

    def __init__(self, *, options: CodexOptions | None = None) -> None:
        self.options = options or CodexOptions()
        self._rpc: RPC | None = None
        self._threads: dict[str, _Binding] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._entered = False
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._scope = local_scope(self.options)
        self._executors: dict[CodexExecutor, str] = {}
        self._executor_lock = asyncio.Lock()
        self._uses_executor = False

    async def __aenter__(self) -> Codex:
        if self._entered or self._closed:
            raise UnavailableError("Codex contexts cannot be reused")
        self._entered = True
        transport = await (
            WebSocket.open(self.options) if self.options.websocket_url is not None else Stdio.open(self.options)
        )
        self._rpc = RPC(transport, self.options.request_timeout, self._notification, self._request, self._lost)
        try:
            await self._rpc.initialize(
                wire.InitializeParams(
                    client_info=wire.ClientInfo(name="ohkit", version="0.0.0"),
                    capabilities=wire.InitializeCapabilities(experimental_api=True),
                )
            )
            await self._rpc.send({"method": "initialized"})
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.close()

    def _connection(self) -> RPC:
        if self._rpc is None or self._closed or self._rpc.failure is not None:
            raise UnavailableError("Enter an available Codex context before use")
        return self._rpc

    def _spawn(self, coroutine: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)

        def finished(task: asyncio.Task[None]) -> None:
            self._tasks.discard(task)
            if not task.cancelled():
                error = task.exception()
                if error is not None and self._rpc is not None:
                    self._rpc.fail(
                        error if isinstance(error, Exception) else ProtocolError("Native background task failed")
                    )

        task.add_done_callback(finished)

    def _attach(self, response: wire.Thread, *, external: bool = False) -> Thread:
        # An admitted history request may return after backend close began.
        self._connection()
        identity = response.id
        previous = self._threads.get(identity)
        if previous is not None and previous.thread._active is not None:
            raise ProtocolError("Native history is already owned by an active live Thread")
        if previous is not None:
            previous.thread._available = False
        binding = _Binding(self, identity)
        capabilities = replace(CAPABILITIES, workspace=True, resume=False, fork=False) if external else CAPABILITIES
        thread = Thread(ThreadRef("codex", identity, self._scope), capabilities, binding, self.options.event_capacity)
        binding.thread = thread
        self._threads[identity] = binding
        return thread

    async def _ready(self, identity: str, timeout: float) -> None:
        try:
            async with asyncio.timeout(timeout):
                while True:
                    response = await self._connection().environment_status(
                        wire.EnvironmentStatusParams(environment_id=identity)
                    )
                    if response.status == "ready":
                        return
                    if response.status != "pending":
                        raise UnavailableError(f"Executor is {response.status}")
                    # Poll native evidence; elapsed time is never a readiness signal.
                    await asyncio.sleep(0.05)
        except TimeoutError:
            raise UnavailableError("Executor readiness deadline expired") from None

    async def _executor(self, endpoint: CodexExecutor) -> str:
        # Native registration affects shared app-server defaults even if its reply is lost.
        self._uses_executor = True
        async with self._executor_lock:
            identity = self._executors.get(endpoint)
            if identity is None:
                identity = "ohkit_" + uuid4().hex
                await self._connection().environment_add(
                    wire.EnvironmentAddParams(
                        environment_id=identity,
                        exec_server_url=endpoint.url,
                        auth_bearer_token=endpoint.bearer_token,
                        connect_timeout_ms=max(1, int(endpoint.readiness_timeout * 1000)),
                    )
                )
                self._executors[endpoint] = identity
            await self._ready(identity, endpoint.readiness_timeout)
            return identity

    async def new_thread(
        self,
        *,
        cwd: str | None = None,
        options: CodexThreadOptions | None = None,
        executor: CodexExecutor | None = None,
    ) -> Thread:
        if executor is None and self._uses_executor:
            raise UnsupportedError("Choose an explicit executor after external environment registration")
        options = options or CodexThreadOptions()
        environment: str | None = None
        if executor is not None:
            if options.sandbox != "danger-full-access":
                raise UnsupportedError("The Workspace executor requires explicit danger-full-access mode")
            if cwd is None:
                raise ValueError("An external executor requires an explicit target cwd")
            environment = await self._executor(executor)
        response = await self._connection().thread_start(
            wire.ThreadStartParams(
                model=options.model,
                model_provider=options.model_provider,
                approval_policy=options.approval_policy,
                sandbox=options.sandbox,
                base_instructions=options.base_instructions,
                developer_instructions=options.developer_instructions,
                cwd=cwd,
                environments=[wire.TurnEnvironmentParams(environment_id=environment, cwd=cwd)]
                if environment is not None and cwd is not None
                else None,
                config={"features.deferred_executor": False, "features.shell_snapshot": False} if executor else None,
            )
        )
        if environment is not None:
            selected = response.thread.environments
            if (
                not selected
                or len(selected) != 1
                or selected[0].environment_id != environment
                or selected[0].cwd != cwd
            ):
                raise ProtocolError("Native Thread did not acknowledge the selected executor and cwd")
            assert executor is not None
            await self._ready(environment, executor.readiness_timeout)
        return self._attach(response.thread, external=executor is not None)

    def _reference(self, ref: ThreadRef) -> None:
        if ref.backend != "codex" or ref.scope != self._scope:
            raise ValueError("Thread reference belongs to another backend/history scope")
        previous = self._threads.get(ref.id)
        if previous is not None and previous.thread._active is not None:
            raise BusyError("Cannot reopen native history while this backend owns an active Run")

    async def resume(
        self,
        ref: ThreadRef,
        *,
        cwd: str | None = None,
        options: CodexThreadOptions | None = None,
        executor: CodexExecutor | None = None,
    ) -> Thread:
        if executor is not None or self._uses_executor:
            raise UnsupportedError("Codex cannot select an external executor during history resume/fork")
        self._reference(ref)
        options = options or CodexThreadOptions()
        response = await self._connection().thread_resume(
            wire.ThreadResumeParams(
                thread_id=ref.id,
                model=options.model,
                model_provider=options.model_provider,
                approval_policy=options.approval_policy,
                sandbox=options.sandbox,
                base_instructions=options.base_instructions,
                developer_instructions=options.developer_instructions,
                cwd=cwd,
            )
        )
        return self._attach(response.thread)

    async def fork(
        self,
        ref: ThreadRef,
        *,
        cwd: str | None = None,
        options: CodexThreadOptions | None = None,
        executor: CodexExecutor | None = None,
    ) -> Thread:
        if executor is not None or self._uses_executor:
            raise UnsupportedError("Codex cannot select an external executor during history resume/fork")
        self._reference(ref)
        options = options or CodexThreadOptions()
        response = await self._connection().thread_fork(
            wire.ThreadForkParams(
                thread_id=ref.id,
                model=options.model,
                model_provider=options.model_provider,
                approval_policy=options.approval_policy,
                sandbox=options.sandbox,
                base_instructions=options.base_instructions,
                developer_instructions=options.developer_instructions,
                cwd=cwd,
            )
        )
        return self._attach(response.thread)

    def _notification(self, method: str, params: dict[str, JSONValue]) -> None:
        identity = params.get("threadId")
        if not isinstance(identity, str):
            return  # Connection-scoped catalog/diagnostics are not Run observations.
        binding = self._threads.get(identity)
        if binding is not None and binding.active is not None:
            binding.active.notification(method, params)

    def _request(self, identity: RequestID, method: str, params: dict[str, JSONValue]) -> None:
        thread_id = params.get("threadId")
        binding = self._threads.get(thread_id) if isinstance(thread_id, str) else None
        if binding is not None and binding.active is not None:
            binding.active.request(identity, method, params)
        else:
            assert self._rpc is not None
            self._spawn(self._rpc.reject(identity, "No active ohkit Run owns this request"))

    def _lost(self, error: Exception) -> None:
        for binding in self._threads.values():
            binding.thread._available = False
            if binding.active is not None:
                binding.active.lost(error)

    async def close(self) -> None:
        if self._close_task is None:
            # Stop backend and Thread admission before the first wait, but keep
            # existing drivers' RPC alive until their interruption settles.
            self._closed = True
            for binding in self._threads.values():
                binding.thread._available = False
            self._close_task = asyncio.create_task(self._close())
        # Concurrent/cancelled callers share actual cleanup, not an early return.
        await _settle(self._close_task)

    async def _close(self) -> None:
        errors: list[Exception] = []
        for binding in tuple(self._threads.values()):
            try:
                await binding.thread.close()
            except Exception as exc:
                errors.append(exc)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._rpc is not None:
            try:
                await self._rpc.close()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("Codex cleanup failures", errors)


class _Binding:
    thread: Thread

    def __init__(self, backend: Codex, identity: str) -> None:
        self.backend = backend
        self.identity = identity
        self.active: _RunDriver | None = None

    def driver(self, run: Run, handlers: Handlers) -> _RunDriver:
        self.backend._connection()
        driver = _RunDriver(self, run, handlers)
        self.active = driver
        return driver

    async def close(self) -> None:
        # Native history/service is borrowed at the Thread level. No archive/delete.
        pass


class _RunDriver:
    def __init__(self, binding: _Binding, run: Run, handlers: Handlers) -> None:
        self.binding = binding
        self.run = run
        self.handlers = handlers
        self.rpc = binding.backend._connection()
        self.turn_id: str | None = None
        self.terminal: wire.Turn | None = None
        self.native_failure: Failure | None = None
        self.controls = 1  # Initial submission is owned before any notification.
        self.done = asyncio.Event()
        self.changed = asyncio.Event()
        self.failure: Failure | None = None
        self.unknown = False
        self.rejected = False
        self.output: dict[str, str] = {}
        self.usage: Usage | None = None
        self.steered: set[str] = set()
        self.recorded: set[str] = set()
        self.consumed: set[str] = set()
        self.model_items: set[str] = set()
        self.cancel_task: asyncio.Task[None] | None = None
        self.finalizer: asyncio.Task[None] | None = None
        self.interactions: dict[RequestID, asyncio.Task[None]] = {}
        self.retired: set[asyncio.Task[None]] = set()
        self.cleanup_error: CleanupError | None = None

    def _bind_turn(self, identity: str) -> None:
        if self.turn_id is not None and self.turn_id != identity:
            raise ProtocolError("Native admission changed the expected active Turn")
        self.turn_id = identity
        self.changed.set()

    async def start(self, input: Input) -> None:
        try:
            response = await self.rpc.turn_start(
                wire.TurnStartParams(
                    thread_id=self.binding.identity,
                    input=[item for item in _input(input)],
                    client_user_message_id="input_" + uuid4().hex,
                )
            )
            turn = response.turn
            self._bind_turn(turn.id)
            self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "started"))
            status = turn.status
            if status != "inProgress" and self.terminal is None:
                self._terminal(turn)
        except (NativeRejectedError, ValueError, TypeError):
            self.rejected = True
            raise
        except Exception:
            self.unknown = True
            self.binding.thread._available = False
            raise UnknownOutcomeError("Initial Codex submission has an unknown native outcome") from None
        finally:
            self.controls -= 1
            self.changed.set()
            self._maybe_finalize()

    def _active(self) -> str:
        if (
            self.done.is_set()
            or self.terminal is not None
            or self.unknown
            or self.rejected
            or self.cancel_task is not None
        ):
            raise InactiveRunError("Run no longer admits active input")
        if self.turn_id is None:
            raise InactiveRunError("Native Turn admission is not established")
        return self.turn_id

    async def steer(self, input: Input) -> None:
        content = _input(input)
        turn_id = self._active()
        identity = "input_" + uuid4().hex
        self.controls += 1
        try:
            response = await self.rpc.turn_steer(
                wire.TurnSteerParams(
                    thread_id=self.binding.identity,
                    expected_turn_id=turn_id,
                    input=[item for item in content],
                    client_user_message_id=identity,
                )
            )
            if response.turn_id != turn_id:
                raise ProtocolError("Steer accepted by an unexpected native Turn")
            self.steered.add(identity)
        except NativeRejectedError:
            raise  # Never replace a rejected steer with turn/start.
        except Exception:
            self.unknown = True
            self.binding.thread._available = False
            raise UnknownOutcomeError("Steering acknowledgement unavailable; accepted input outcome unknown") from None
        finally:
            self.controls -= 1
            self.changed.set()
            self._maybe_finalize()

    def overflow(self) -> None:
        self.failure = Failure("observation_overflow", "Run observations exceeded the bounded buffer")
        self._ensure_cancel()

    def _ensure_cancel(self) -> None:
        if self.cancel_task is None and not self.done.is_set() and self.terminal is None and not self.unknown:
            self.cancel_task = asyncio.create_task(self._interrupt())
            for identity in tuple(self.interactions):
                self._withdraw(identity)

    async def cancel(self) -> None:
        self._ensure_cancel()
        if self.cancel_task is not None:
            await asyncio.shield(self.cancel_task)

    async def _interrupt(self) -> None:
        self.controls += 1
        try:
            while self.turn_id is None and not self.unknown and not self.rejected:
                self.changed.clear()
                await self.changed.wait()
            if self.terminal is not None or self.unknown or self.rejected:
                return
            self.run._emit(LifecycleEvent(self.run.thread, self.run.id, "cancelling"))
            assert self.turn_id is not None
            await self.rpc.turn_interrupt(
                wire.TurnInterruptParams(thread_id=self.binding.identity, turn_id=self.turn_id)
            )
        except NativeRejectedError:
            # Completion can win. A rejection is not termination evidence.
            pass
        except Exception:
            self.unknown = True
            self.binding.thread._available = False
        finally:
            self.controls -= 1
            self.changed.set()
            self._maybe_finalize()

    def lost(self, error: Exception) -> None:
        if self.done.is_set():
            return
        self.unknown = True
        if self.failure is None:
            self.failure = Failure("connection_lost", "Native connection lost after possible execution")
        self.changed.set()
        self._maybe_finalize()

    def _terminal(self, turn: wire.Turn) -> None:
        status = turn.status
        if status not in ("completed", "failed", "interrupted"):
            raise ProtocolError("Unknown native terminal status")
        # Validate result fields on the reader path, where malformed evidence
        # fails the connection and settles Runs as unknown, never a stuck drain.
        failure = None if turn.error is None else Failure("native_execution_failed", turn.error.message)
        if self.terminal is None:
            self.native_failure = failure
            self.terminal = turn
        self._maybe_finalize()

    def notification(self, method: str, params: dict[str, JSONValue]) -> None:
        if self.done.is_set():
            return
        if method == "serverRequest/resolved":
            self._withdraw(decode(wire.ServerRequestResolvedNotification, params).request_id)
            return
        if method in ("turn/started", "turn/completed"):
            notification = decode(
                wire.TurnStartedNotification if method == "turn/started" else wire.TurnCompletedNotification, params
            )
            turn = notification.turn
            identity = turn.id
            if method == "turn/started" and self.turn_id is None:
                self._bind_turn(identity)
            if identity != self.turn_id:
                return
            if method == "turn/completed":
                self._terminal(turn)
            return
        # Only explicitly correlated foreground observations belong to this Run.
        if params.get("turnId") != self.turn_id or self.turn_id is None or self.terminal is not None:
            return
        delta_model = _DELTA_MODELS.get(method)
        if delta_model is not None:
            model, channel = delta_model
            delta = decode(model, params)
            self.run._emit(ContentEvent(self.run.thread, self.run.id, delta.item_id, delta.delta, channel))
        elif method == "item/started":
            self._observe_item(decode(wire.ItemStartedNotification, params), "started", obj(params["item"]))
        elif method == "item/completed":
            self._observe_item(decode(wire.ItemCompletedNotification, params), "completed", obj(params["item"]))
        elif method == "thread/tokenUsage/updated":
            # last = current native Turn, total = conversation lifetime.
            last = decode(wire.ThreadTokenUsageUpdatedNotification, params).token_usage.last
            self.usage = Usage(
                input_tokens=last.input_tokens,
                output_tokens=last.output_tokens,
                cached_input_tokens=last.cached_input_tokens,
                reasoning_output_tokens=last.reasoning_output_tokens,
                total_tokens=last.total_tokens,
            )
            self.run._emit(UsageEvent(self.run.thread, self.run.id, self.usage))
        else:
            self.run._emit(NativeEvent(self.run.thread, self.run.id, method, native(params)))

    def _observe_item(
        self,
        notification: wire.ItemStartedNotification | wire.ItemCompletedNotification,
        phase: Literal["started", "completed"],
        raw: dict[str, JSONValue],
    ) -> None:
        item = notification.item
        kind, identity = item.type, item.id
        if isinstance(item, wire.UserMessageThreadItem):
            if item.client_id is not None:
                self.recorded.add(item.client_id)
        elif isinstance(item, (wire.AgentMessageThreadItem, wire.ReasoningThreadItem)):
            if isinstance(item, wire.ReasoningThreadItem) or item.delivery is None:
                if phase == "started" and identity not in self.model_items:
                    # on_task_finished also records unsampled pending prompts.
                    # A new foreground model item after prompt recording is
                    # required; history/clientId alone is not consumption.
                    self.consumed.update(self.recorded)
                if isinstance(item, wire.AgentMessageThreadItem) and phase == "completed":
                    self.output[identity] = item.text
            self.model_items.add(identity)
        elif kind not in ("plan", "hookPrompt"):
            self.run._emit(ToolEvent(self.run.thread, self.run.id, identity, kind, phase, native(raw)))

    def request(self, identity: RequestID, method: str, params: dict[str, JSONValue]) -> None:
        if identity in self.interactions:
            raise ProtocolError("Duplicate live native interaction identity")
        if self.turn_id is None:
            self._bind_turn(string(params["turnId"]))
        if (
            params.get("turnId") != self.turn_id
            or self.terminal is not None
            or self.unknown
            or self.cancel_task is not None
        ):
            self.binding.backend._spawn(
                self.rpc.reject(
                    identity,
                    "Request is not owned by an active foreground Turn",
                    lambda: self.terminal is None and not self.unknown,
                )
            )
            return
        try:
            if method == "item/tool/requestUserInput":
                request = questions(self.run.thread, self.run.id, identity, params)
            else:
                request = approval(self.run.thread, self.run.id, identity, method, params)
        except Exception:
            self.failure = Failure("unsupported_interaction", "Native interaction semantics are unsupported")
            self.binding.backend._spawn(
                self.rpc.reject(
                    identity,
                    "Unsupported native interaction semantics",
                    lambda: self.terminal is None and not self.unknown,
                )
            )
            self._ensure_cancel()
            return
        self.run._emit(InteractionEvent(self.run.thread, self.run.id, str(identity), "requested", request))
        task = asyncio.create_task(self._handle(identity, request))
        self.interactions[identity] = task
        task.add_done_callback(self._handled)

    def _handled(self, task: asyncio.Task[None]) -> None:
        self.retired.discard(task)
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                self.rpc.fail(
                    error if isinstance(error, Exception) else ProtocolError("Native interaction task failed")
                )

    def _withdraw(self, identity: RequestID) -> None:
        task = self.interactions.pop(identity, None)
        if task is not None:
            task.cancel()
            self.retired.add(task)
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, str(identity), "withdrawn"))

    async def _handle(self, identity: RequestID, request: ApprovalRequest | QuestionRequest) -> None:
        owner = asyncio.current_task()

        def live() -> bool:
            return (
                self.interactions.get(identity) is owner
                and self.terminal is None
                and not self.unknown
                and self.cancel_task is None
            )

        try:
            if isinstance(request, ApprovalRequest):
                choice = (
                    default_choice(request) if self.handlers.approval is None else await self.handlers.approval(request)
                )
                response = approval_response(request, choice)
            else:
                if self.handlers.question is None:
                    raise UnsupportedError("No question handler configured")
                response = question_response(request, await self.handlers.question(request))
            # No await between the stale check and acquiring the write gate inside
            # reply_live; it checks again after lock acquisition before dispatch.
            sent = await self.rpc.reply_live(identity, response, live)
            if sent:
                self.run._emit(InteractionEvent(self.run.thread, self.run.id, str(identity), "answered"))
        except asyncio.CancelledError:
            raise
        except Exception:
            if not live():
                return
            self.failure = Failure(
                "interaction_handler_failed", "A live interaction handler failed or returned an invalid response"
            )
            self.run._emit(InteractionEvent(self.run.thread, self.run.id, str(identity), "failed"))
            if isinstance(request, ApprovalRequest):
                try:
                    response = approval_response(request, default_choice(request))
                    await self.rpc.reply_live(
                        identity,
                        response,
                        live,
                    )
                except Exception:
                    await self.rpc.reject(identity, "Interaction failed; permission was not granted", live)
            else:
                await self.rpc.reject(identity, "Question handler unavailable or failed", live)
            self._ensure_cancel()

    def _maybe_finalize(self) -> None:
        if (
            self.finalizer is None
            and self.controls == 0
            and (self.terminal is not None or self.unknown or self.rejected)
        ):
            self.finalizer = asyncio.create_task(self._finalize())

    async def _finalize(self) -> None:
        tasks = set(self.interactions.values()) | self.retired
        for identity in tuple(self.interactions):
            self._withdraw(identity)
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=self.binding.backend.options.cleanup_timeout)
            if pending:
                self.binding.thread._available = False
                self.cleanup_error = CleanupError("Interaction tasks did not settle before the cleanup deadline")
                self.unknown = True
        status = None if self.terminal is None else self.terminal.status
        outcome: Outcome = "unknown"
        if not self.unknown and status is not None:
            if status == "completed":
                outcome = "completed"
            elif status == "failed":
                outcome = "failed"
            else:
                outcome = "cancelled"
            if status != "interrupted" and self.steered - self.consumed:
                outcome = "unknown"
                self.binding.thread._available = False
                self.failure = Failure(
                    "unaccounted_steer", "Accepted steering input has no observed consumption evidence"
                )
            elif self.failure is not None:
                outcome = "failed"
        if self.failure is None:
            self.failure = self.native_failure
        result = Result(
            thread=self.run.thread,
            run_id=self.run.id,
            outcome=outcome,
            output="\n".join(self.output.values()),
            usage=self.usage,
            failure=self.failure,
            native_turn_id=self.turn_id,
            native_status=status,
            native=None if self.terminal is None else native(encode(self.terminal)),
        )
        if self.cleanup_error is not None:
            self.cleanup_error.result = result
        if not self.rejected:
            self.run._finish(result)
        self.done.set()
        self.binding.active = None

    async def close(self) -> None:
        if not self.done.is_set():
            self._ensure_cancel()
            try:
                async with asyncio.timeout(self.binding.backend.options.cleanup_timeout):
                    if self.cancel_task is not None:
                        await asyncio.shield(self.cancel_task)
                    await self.done.wait()
            except TimeoutError:
                self.binding.thread._available = False
                self.rpc.fail(UnknownOutcomeError("Run cleanup timed out; native termination not established"))
                self.unknown = True
                self._maybe_finalize()
                if self.finalizer is not None:
                    await asyncio.shield(self.finalizer)
                raise CleanupError("Native Run termination could not be established", self.run._terminal) from None
        if self.finalizer is not None:
            await asyncio.shield(self.finalizer)
        if self.cleanup_error is not None:
            raise self.cleanup_error
