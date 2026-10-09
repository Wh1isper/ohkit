"""Public API against an explicitly controlled local protocol peer, not Codex."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from websockets.asyncio.server import serve

from ohkit import (
    Answer,
    ApprovalChoice,
    BusyError,
    CleanupError,
    ContentEvent,
    Handlers,
    InactiveRunError,
    NativeData,
    NativeRejectedError,
    ObservationOverflowError,
    ProtocolError,
    QuestionResponse,
    UnavailableError,
    UndrainedStreamError,
    UnknownOutcomeError,
)
from ohkit.backends.codex import Codex, CodexOptions

FIXTURES = Path(__file__).parent / "fixtures"


def thread_response(identity):
    response = json.loads((FIXTURES / "thread.json").read_text())
    response["thread"]["id"] = identity
    return response


class Peer:
    def __init__(self):
        self.connection = None
        self.calls = asyncio.Queue()
        self.responses = asyncio.Queue()
        self.all_calls = []
        self.number = 0
        self.thread_count = 0
        self.turn = None
        self.hold_start = False
        self.hold_thread = False
        self.drop_start = False
        self.hold_interrupt = False
        self.closed = asyncio.Event()

    async def send(self, value):
        await self.connection.send(json.dumps(value))

    async def response(self, call, result):
        await self.send({"id": call["id"], "result": result})

    async def notify(self, method, **params):
        if method == "item/started":
            params.setdefault("startedAtMs", 1)
        elif method == "item/completed":
            params.setdefault("completedAtMs", 2)
        await self.send({"method": method, "params": {"threadId": "thread-1", **params}})

    async def next(self, method):
        async with asyncio.timeout(5):
            while True:
                call = await self.calls.get()
                if call.get("method") == method:
                    return call

    async def finish(self, status="completed", text="answer", turn=None):
        identity = turn or self.turn
        await self.notify("item/started", turnId=identity, item={"type": "agentMessage", "id": "answer-1", "text": ""})
        await self.notify(
            "item/completed", turnId=identity, item={"type": "agentMessage", "id": "answer-1", "text": text}
        )
        await self.notify("turn/completed", turn={"id": identity, "status": status, "items": [], "error": None})

    async def user(self, call):
        await self.notify(
            "item/started",
            turnId=self.turn,
            item={
                "type": "userMessage",
                "id": "user-1",
                "content": [],
                "clientId": call["params"].get("clientUserMessageId"),
            },
        )

    async def request(self, method, identity=700, **params):
        if method.endswith("/requestApproval"):
            params.setdefault("startedAtMs", 1)
        await self.send(
            {
                "id": identity,
                "method": method,
                "params": {"threadId": "thread-1", "turnId": self.turn, "itemId": "tool-1", **params},
            }
        )

    async def handler(self, connection):
        self.connection = connection
        try:
            async for text in connection:
                frame = json.loads(text)
                if "method" not in frame:
                    await self.responses.put(frame)
                    continue
                self.all_calls.append(frame)
                method = frame["method"]
                if method == "initialize":
                    await self.response(frame, json.loads((FIXTURES / "initialize.json").read_text()))
                elif method in ("thread/start", "thread/resume", "thread/fork"):
                    if method == "thread/start":
                        self.thread_count += 1
                        identity = f"thread-{self.thread_count}"
                    else:
                        identity = "thread-fork" if method == "thread/fork" else frame["params"]["threadId"]
                    if not self.hold_thread:
                        await self.response(frame, thread_response(identity))
                elif method == "turn/start":
                    self.number += 1
                    self.turn = f"turn-{self.number}"
                    if self.drop_start:
                        await connection.close()
                        return
                    # Native notification deliberately precedes the acceptance response.
                    await self.notify(
                        "turn/started", turn={"id": self.turn, "status": "inProgress", "items": [], "error": None}
                    )
                    if not self.hold_start:
                        await self.response(
                            frame, {"turn": {"id": self.turn, "status": "inProgress", "items": [], "error": None}}
                        )
                elif method == "turn/interrupt" and not self.hold_interrupt:
                    await self.response(frame, {})
                    await self.finish("interrupted")
                await self.calls.put(frame)
        finally:
            self.closed.set()


@asynccontextmanager
async def connected(**options):
    peer = Peer()
    options = {"request_timeout": 2, "cleanup_timeout": 2, **options}
    async with serve(peer.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with Codex(
            options=CodexOptions(
                websocket_url=f"ws://127.0.0.1:{port}",
                history_scope="test-service",
                **options,
            )
        ) as backend:
            yield peer, backend
        await peer.closed.wait()
        # The listener/service is still caller-owned after closing ohkit.
        assert server.is_serving()


async def drain(run):
    events = [event async for event in run]
    return events, await run.result()


def test_stream_run_history_and_native_scope():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread(cwd="/native/project")
            assert thread.capabilities.steer and not thread.capabilities.workspace
            async with thread.stream("first") as run:
                with pytest.raises(UndrainedStreamError):
                    await run.result()
                await peer.notify("item/agentMessage/delta", turnId=peer.turn, itemId="answer-1", delta="answer")
                await peer.finish()
                events, result = await drain(run)
                assert result.outcome == "completed" and result.output == "answer"
                assert result.usage is None
                assert any(isinstance(event, ContentEvent) for event in events)
                assert await run.result() is result
            ref = thread.ref
            resumed = await backend.resume(ref)
            with pytest.raises(UnavailableError):
                await thread.run("old owner")
            fork = await backend.fork(ref)
            assert fork.ref.id != ref.id
            result_task = asyncio.create_task(resumed.run("second"))
            await peer.next("turn/start")  # first queued start
            await peer.next("turn/start")
            await peer.finish(text="follow-up")
            assert (await result_task).output == "follow-up"

    asyncio.run(scenario())


def test_no_implicit_queue_and_context_exit_interrupts():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            context = thread.stream("not dispatched")
            assert not any(call["method"] == "turn/start" for call in peer.all_calls)
            async with context as run:
                with pytest.raises(BusyError):
                    await thread.run("never queued")
                with pytest.raises(BusyError):
                    await backend.resume(thread.ref)
                assert len([c for c in peer.all_calls if c["method"] == "turn/start"]) == 1
            assert (await drain(run))[1].outcome == "cancelled"
            assert len([c for c in peer.all_calls if c["method"] == "turn/interrupt"]) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("consume", [True, False])
@pytest.mark.parametrize("status", ["completed", "failed"])
def test_steer_ack_after_completion_settles_before_result(consume, status):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                steering = asyncio.create_task(run.steer("add input"))
                call = await peer.next("turn/steer")
                if consume:
                    await peer.user(call)
                await peer.finish(status)
                collection = asyncio.create_task(drain(run))
                # A round trip (not a sleep) establishes processing of completion.
                await backend.new_thread()
                assert not collection.done()
                await peer.response(call, {"turnId": peer.turn})
                await steering
                result = (await collection)[1]
                assert result.outcome == (status if consume else "unknown")
                if not consume:
                    with pytest.raises(UnavailableError):
                        await thread.run("not safe")
                with pytest.raises(InactiveRunError):
                    await run.steer("no future Run")

    asyncio.run(scenario())


def test_rejected_steer_never_starts_replacement():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                task = asyncio.create_task(run.steer("late"))
                call = await peer.next("turn/steer")
                await peer.send({"id": call["id"], "error": {"code": -32600, "message": "no active turn"}})
                with pytest.raises(NativeRejectedError):
                    await task
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"
            assert len([c for c in peer.all_calls if c["method"] == "turn/start"]) == 1

    asyncio.run(scenario())


def test_completion_can_win_cancellation_and_cancel_is_idempotent():
    async def scenario():
        async with connected() as (peer, backend):
            peer.hold_interrupt = True
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                cancel = asyncio.create_task(run.cancel())
                call = await peer.next("turn/interrupt")
                again = asyncio.create_task(run.cancel())
                await peer.finish("completed")
                await peer.response(call, {})
                await asyncio.gather(cancel, again)
                assert (await drain(run))[1].outcome == "completed"
            assert len([c for c in peer.all_calls if c["method"] == "turn/interrupt"]) == 1

    asyncio.run(scenario())


def test_lost_start_ack_is_unknown_not_replayed():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            peer.drop_start = True
            with pytest.raises(UnknownOutcomeError):
                await thread.run("may execute")
            with pytest.raises(UnavailableError):
                await thread.run("cannot retry")
            assert peer.number == 1

    asyncio.run(scenario())


def test_connection_loss_after_admission_is_unknown():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.connection.close()
                assert (await drain(run))[1].outcome == "unknown"
            with pytest.raises(UnavailableError):
                await thread.run("cannot retry")

    asyncio.run(scenario())


def test_slow_consumer_overflow_does_not_block_interrupt_reader():
    async def scenario():
        async with connected(event_capacity=2) as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                for _ in range(10):
                    await peer.notify("item/agentMessage/delta", turnId=peer.turn, itemId="answer-1", delta="x")
                await peer.next("turn/interrupt")
                with pytest.raises(ObservationOverflowError):
                    await drain(run)
                result = await run.result()
                assert result.outcome == "failed"
                assert result.failure.code == "observation_overflow"
                assert result.native_status == "interrupted"

    asyncio.run(scenario())


def test_caller_cancellation_during_initial_admission_settles_native_work():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            peer.hold_start = True
            task = asyncio.create_task(thread.run("work"))
            call = await peer.next("turn/start")
            task.cancel()
            await peer.response(call, {"turn": {"id": peer.turn, "status": "inProgress", "items": [], "error": None}})
            await peer.next("turn/interrupt")
            with pytest.raises(asyncio.CancelledError):
                await task
            assert peer.number == 1
            peer.hold_start = False
            async with thread.stream("new work") as run:
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"

    asyncio.run(scenario())


@pytest.mark.parametrize("handler_mode", ["missing", "failed", "invalid", "accept"])
def test_approval_choices_missing_and_failed_handlers_never_approve(handler_mode):
    async def scenario():
        async def handle(request):
            assert request.command == "printf hi"
            assert tuple(c.kind for c in request.choices) == ("accept", "decline")
            if handler_mode == "failed":
                raise RuntimeError("no")
            if handler_mode == "invalid":
                return ApprovalChoice("acceptForSession", "session")
            return request.choices[0]

        handlers = Handlers() if handler_mode == "missing" else Handlers(approval=handle)
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=handlers) as run:
                await peer.request(
                    "item/commandExecution/requestApproval",
                    command="printf hi",
                    cwd="/project",
                    availableDecisions=["accept", "decline"],
                )
                response = await asyncio.wait_for(peer.responses.get(), 5)
                assert response["result"]["decision"] == ("accept" if handler_mode == "accept" else "decline")
                await peer.notify("serverRequest/resolved", requestId=700)
                await peer.finish()
                result = (await drain(run))[1]
                assert result.outcome == ("failed" if handler_mode in ("failed", "invalid") else "completed")

    asyncio.run(scenario())


@pytest.mark.parametrize("extra", [{}, {"glob_scan_max_depth": 2}, {"globScanMaxDepth": 3, "glob_scan_max_depth": 2}])
def test_permissions_preserve_exact_scope_and_native_profile(extra):
    async def scenario():
        permissions = {
            "network": {"enabled": True},
            "fileSystem": {
                **extra,
                "write": ["/project"],
                "entries": [{"path": {"type": "glob_pattern", "pattern": "/project/*.py"}, "access": "write"}],
            },
        }

        async def handle(request):
            assert request.native.decode()["permissions"] == permissions
            return next(choice for choice in request.choices if choice.kind == "permissions" and choice.scope == "turn")

        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                await peer.request(
                    "item/permissions/requestApproval", cwd="/project", permissions=permissions, startedAtMs=1
                )
                response = await peer.responses.get()
                assert response["result"] == {"permissions": permissions, "scope": "turn"}
                await peer.notify("serverRequest/resolved", requestId=700)
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"

    asyncio.run(scenario())


def test_question_shape_and_secret_answers_are_not_observations():
    async def scenario():
        async def handle(request):
            assert request.blocking and request.questions[0].secret
            return QuestionResponse((Answer("q1", ("A",)),))

        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(question=handle)) as run:
                await peer.request(
                    "item/tool/requestUserInput",
                    isBlocking=True,
                    questions=[
                        {
                            "id": "q1",
                            "header": "Pick",
                            "question": "Choose",
                            "isSecret": True,
                            "options": [{"label": "A", "description": "one"}],
                        }
                    ],
                )
                response = await peer.responses.get()
                assert response["result"] == {"answers": {"q1": {"answers": ["A"]}}}
                await peer.notify("serverRequest/resolved", requestId=700)
                await peer.finish()
                events, result = await drain(run)
                assert result.outcome == "completed"
                assert all("QuestionResponse" not in repr(event) for event in events)

    asyncio.run(scenario())


def test_withdrawal_cancels_handler_and_late_answer_is_never_sent():
    async def scenario():
        entered, withdrawn, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def handle(request):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                withdrawn.set()
                await release.wait()
            return request.choices[0]

        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                await peer.request("item/fileChange/requestApproval")
                await entered.wait()
                await peer.notify("serverRequest/resolved", requestId=700)
                await withdrawn.wait()
                release.set()
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"
                assert peer.responses.empty()

    asyncio.run(scenario())


def test_unknown_reverse_request_is_explicitly_unsupported():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.request("item/newPower/requestApproval")
                response = await peer.responses.get()
                assert "error" in response
                result = (await drain(run))[1]
                assert result.outcome == "failed"

    asyncio.run(scenario())


def test_native_json_is_immutable_detached_strict_and_private():
    data = NativeData("codex", '{"scope":{"paths":["/project"]}}')
    decoded = data.decode()
    decoded["scope"]["paths"].append("/outside")
    assert data.decode()["scope"]["paths"] == ["/project"]
    assert "/project" not in repr(data)
    for invalid in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(ProtocolError):
            NativeData("codex", invalid)
    secret = "not-a-real-token"
    options = CodexOptions(
        websocket_url=f"ws://localhost/test?token={secret}",
        headers=(("Authorization", secret),),
        history_scope="service",
    )
    assert secret not in repr(options)


def test_native_terminal_before_start_ack_is_retained():
    async def scenario():
        async with connected() as (peer, backend):
            peer.hold_start = True
            thread = await backend.new_thread()
            task = asyncio.create_task(thread.run("work"))
            call = await peer.next("turn/start")
            await peer.finish()
            await backend.new_thread()  # Reader round trip processes completion.
            assert not task.done()
            await peer.response(call, {"turn": {"id": peer.turn, "status": "inProgress", "items": []}})
            assert (await task).outcome == "completed"

    asyncio.run(scenario())


def test_withdrawn_handler_cannot_answer_reused_request_identity():
    async def scenario():
        entered, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        count = 0

        async def handle(request):
            nonlocal count
            count += 1
            if count == 1:
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    await release.wait()
                return request.choices[0]
            return next(choice for choice in request.choices if choice.kind == "decline")

        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                await peer.request("item/fileChange/requestApproval")
                await entered.wait()
                await peer.notify("serverRequest/resolved", requestId=700)
                await cancelled.wait()
                await peer.request("item/fileChange/requestApproval")
                response = await peer.responses.get()
                assert response["result"]["decision"] == "decline"
                release.set()
                await peer.notify("serverRequest/resolved", requestId=700)
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"
                assert peer.responses.empty()

    asyncio.run(scenario())


def test_resolved_unsupported_request_cannot_send_stale_error_from_write_queue():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                # Hold the actual write gate to reproduce a queued rejection. The
                # native reader must still process withdrawal while writes wait.
                async with backend._rpc.write_lock:
                    await peer.request("item/newPower/requestApproval")
                    await peer.notify("serverRequest/resolved", requestId=700)
                    await peer.finish()
                    result = (await drain(run))[1]
                    assert result.outcome == "failed"
                await backend.new_thread()
                assert peer.responses.empty()

    asyncio.run(scenario())


def test_connection_failure_while_waiting_for_write_lock_never_dispatches(monkeypatch):
    async def scenario():
        async with connected() as (peer, backend):
            rpc = backend._rpc
            entered = asyncio.Event()
            send = rpc.send

            async def queued_send(message):
                entered.set()
                await send(message)

            monkeypatch.setattr(rpc, "send", queued_send)
            async with rpc.write_lock:
                submission = asyncio.create_task(rpc._call("turn/start", {"threadId": "thread-1", "input": []}))
                await entered.wait()
                rpc.fail(ProtocolError("Connection failed while the write was queued"))
            with pytest.raises(UnknownOutcomeError):
                await submission
        assert not any(call["method"] == "turn/start" for call in peer.all_calls)

    asyncio.run(scenario())


def test_cleanup_deadline_keeps_native_evidence_and_disables_owner():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def handle(request):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return request.choices[0]

        async with connected(cleanup_timeout=0.02) as (peer, backend):
            thread = await backend.new_thread()
            try:
                with pytest.raises(CleanupError) as caught:
                    async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                        await peer.request("item/fileChange/requestApproval")
                        await entered.wait()
                        await peer.finish()
                        result = (await drain(run))[1]
                        assert result.outcome == "unknown" and result.native_status == "completed"
                assert caught.value.result is result
                with pytest.raises(UnavailableError):
                    await thread.run("unsafe")
            finally:
                release.set()
            await backend.new_thread()
            assert peer.responses.empty()

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["futureStatus", None])
def test_malformed_terminal_fails_connection_and_never_claims_success(status):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.finish(status)
                assert (await drain(run))[1].outcome == "unknown"
            with pytest.raises(UnavailableError):
                await thread.run("unsafe")

    asyncio.run(scenario())


@pytest.mark.parametrize("error", [{"message": 42}, {}, "not an object"])
@pytest.mark.parametrize("status", ["completed", "failed"])
def test_malformed_terminal_error_settles_as_unknown_without_hanging(error, status):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.notify("turn/completed", turn={"id": peer.turn, "status": status, "error": error})
                result = (await asyncio.wait_for(drain(run), 0.5))[1]
                assert result.outcome == "unknown"
                assert result.native_status is None
                assert result.failure.code == "connection_lost"
            with pytest.raises(UnavailableError):
                await thread.run("unsafe")
            with pytest.raises(UnavailableError):
                await backend.new_thread()

    asyncio.run(scenario())


def test_valid_failed_terminal_preserves_native_failure_evidence():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                terminal = {"id": peer.turn, "status": "failed", "error": {"message": "model failed"}, "items": []}
                await peer.notify("turn/completed", turn=terminal)
                result = (await asyncio.wait_for(drain(run), 0.5))[1]
                assert result.outcome == "failed"
                assert result.native_status == "failed"
                assert result.failure.code == "native_execution_failed"
                assert result.failure.message == "model failed"
                assert result.native.decode() == terminal
            async with thread.stream("retry explicitly") as run:
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["new", "resume", "fork"])
@pytest.mark.parametrize("cancel_caller", [False, True])
def test_backend_close_stops_thread_admission_and_concurrent_close_waits(operation, cancel_caller):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            history = await backend.new_thread()
            peer.hold_interrupt = True
            async with thread.stream("work") as run:
                closing = asyncio.create_task(backend.close())
                interrupt = await peer.next("turn/interrupt")
                before = len(peer.all_calls)
                with pytest.raises(UnavailableError):
                    if operation == "new":
                        await backend.new_thread()
                    elif operation == "resume":
                        await backend.resume(history.ref)
                    else:
                        await backend.fork(history.ref)
                assert len(peer.all_calls) == before
                with pytest.raises(UnavailableError):
                    await history.run("no new Run during close")
                concurrent = asyncio.create_task(backend.close())
                await asyncio.sleep(0)  # Let the second close reach its cleanup wait.
                assert not closing.done() and not concurrent.done()
                if cancel_caller:
                    closing.cancel()
                    await asyncio.sleep(0)
                    assert not closing.done() and not concurrent.done()
                await peer.response(interrupt, {})
                await peer.finish("interrupted")
                results = await asyncio.wait_for(asyncio.gather(closing, concurrent, return_exceptions=True), 1)
                assert results[1] is None
                assert isinstance(results[0], asyncio.CancelledError) if cancel_caller else results[0] is None
                assert (await drain(run))[1].outcome == "cancelled"
                assert sum(c["method"] == "turn/interrupt" for c in peer.all_calls) == 1
            await backend.close()
            await peer.closed.wait()

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["new", "resume", "fork"])
def test_backend_close_rejects_late_thread_attachment(operation):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            history = await backend.new_thread()
            peer.hold_thread = True
            peer.hold_interrupt = True
            async with thread.stream("work") as run:
                if operation == "new":
                    attaching = asyncio.create_task(backend.new_thread())
                    call = await peer.next("thread/start")  # Earlier setup calls.
                    call = await peer.next("thread/start")
                    call = await peer.next("thread/start")
                elif operation == "resume":
                    attaching = asyncio.create_task(backend.resume(history.ref))
                    call = await peer.next("thread/resume")
                else:
                    attaching = asyncio.create_task(backend.fork(history.ref))
                    call = await peer.next("thread/fork")
                closing = asyncio.create_task(backend.close())
                interrupt = await peer.next("turn/interrupt")
                identity = history.ref.id if operation == "resume" else "thread-late"
                await peer.response(call, thread_response(identity))
                with pytest.raises(UnavailableError):
                    await asyncio.wait_for(attaching, 1)
                assert not closing.done()
                await peer.response(interrupt, {})
                await peer.finish("interrupted")
                await asyncio.wait_for(closing, 1)
                assert (await drain(run))[1].outcome == "cancelled"
                assert sum(c["method"] == "turn/start" for c in peer.all_calls) == 1
                assert sum(c["method"] == "turn/interrupt" for c in peer.all_calls) == 1

    asyncio.run(scenario())


def test_missing_question_handler_explicitly_rejects_without_answers():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.request(
                    "item/tool/requestUserInput",
                    isBlocking=True,
                    questions=[{"id": "q", "header": "Q", "question": "Required"}],
                )
                response = await peer.responses.get()
                assert "error" in response and "result" not in response
                assert (await drain(run))[1].outcome == "failed"

    asyncio.run(scenario())


def test_single_consumer_and_late_background_not_attributed_to_new_run():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("first") as first:
                await peer.finish()
                assert (await drain(first))[1].outcome == "completed"
                old_turn = peer.turn
            async with thread.stream("second") as second:
                await anext(second)  # Claim the single consumer in this task.
                with pytest.raises(RuntimeError, match="one event consumer"):
                    await asyncio.create_task(anext(second))
                await peer.notify("item/agentMessage/delta", turnId=old_turn, itemId="late", delta="old")
                await peer.notify(
                    "item/completed", turnId=old_turn, item={"id": "late", "type": "agentMessage", "text": "old"}
                )
                await peer.finish(text="new")
                events, result = await drain(second)
                assert result.output == "new"
                assert not any(isinstance(event, ContentEvent) and event.text == "old" for event in events)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "response",
    [
        {"result": []},
        {},
        {"result": {}, "error": {"code": -1, "message": "ambiguous"}},
        {"error": {"code": "invalid", "message": "malformed"}},
    ],
)
def test_malformed_start_response_settles_pending_call_without_waiting_for_ack_timeout(response):
    async def scenario():
        async with connected(request_timeout=30) as (peer, backend):
            peer.hold_start = True
            thread = await backend.new_thread()
            task = asyncio.create_task(thread.run("uncertain"))
            call = await peer.next("turn/start")
            await peer.send({"id": call["id"], **response})
            # Protocol failure settles the original pending call, not merely all
            # other calls. This bound is below its configured native ack timeout.
            with pytest.raises(UnknownOutcomeError):
                await asyncio.wait_for(task, 1)
            with pytest.raises(UnavailableError):
                await thread.run("cannot retry")
            assert peer.number == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("params", "kinds"),
    [
        ({}, ("accept", "cancel")),
        ({"proposedExecpolicyAmendment": ["printf"]}, ("accept", "execpolicy", "cancel")),
        (
            {"additionalPermissions": {"network": {"enabled": True}}, "proposedExecpolicyAmendment": ["printf"]},
            ("accept", "cancel"),
        ),
        (
            {
                "networkApprovalContext": {"host": "example.test", "protocol": "https"},
                "proposedNetworkPolicyAmendments": [
                    {"host": "example.test", "action": "deny"},
                    {"host": "example.test", "action": "allow"},
                ],
            },
            ("accept", "acceptForSession", "network", "cancel"),
        ),
    ],
)
def test_absent_available_decisions_uses_exact_pinned_native_prompt_defaults(params, kinds):
    async def scenario():
        async def handle(request):
            assert tuple(choice.kind for choice in request.choices) == kinds
            if "network" in kinds:
                choice = next(choice for choice in request.choices if choice.kind == "network")
                assert choice.scope == "persistent"
                assert choice.native.decode() == {
                    "applyNetworkPolicyAmendment": {
                        "network_policy_amendment": {"host": "example.test", "action": "allow"}
                    }
                }
            return next(choice for choice in request.choices if choice.kind == "cancel")

        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                await peer.request("item/commandExecution/requestApproval", **params)
                assert (await peer.responses.get())["result"] == {"decision": "cancel"}
                await peer.notify("serverRequest/resolved", requestId=700)
                await peer.finish()
                assert (await drain(run))[1].outcome == "completed"

    asyncio.run(scenario())


def test_run_cancellation_withdraws_handler_before_native_interrupt_ack():
    async def scenario():
        entered, cancelled, release, returned = (asyncio.Event() for _ in range(4))

        async def handle(request):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
            returned.set()
            return request.choices[0]

        async with connected() as (peer, backend):
            peer.hold_interrupt = True
            thread = await backend.new_thread()
            async with thread.stream("work", handlers=Handlers(approval=handle)) as run:
                await peer.request("item/fileChange/requestApproval")
                await entered.wait()
                task = asyncio.create_task(run.cancel())
                interrupt = await peer.next("turn/interrupt")
                await cancelled.wait()
                release.set()
                await returned.wait()
                await backend.new_thread()
                assert peer.responses.empty()  # Native terminal is still held.
                await peer.response(interrupt, {})
                await peer.finish("interrupted")
                await task
                assert (await drain(run))[1].outcome == "cancelled"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "later", ["none", "old_delta", "old_completed", "old_started_again", "async_started", "unknown_delivery"]
)
def test_terminal_history_drain_is_not_steering_consumption(later):
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            async with thread.stream("work") as run:
                await peer.notify(
                    "item/started", turnId=peer.turn, item={"type": "agentMessage", "id": "old", "text": ""}
                )
                steering = asyncio.create_task(run.steer("must be sampled"))
                call = await peer.next("turn/steer")
                await peer.response(call, {"turnId": peer.turn})
                await steering
                # Native on_task_finished can emit this without another model step.
                await peer.user(call)
                if later == "old_delta":
                    await peer.notify("item/agentMessage/delta", turnId=peer.turn, itemId="old", delta="old")
                elif later in ("old_completed", "old_started_again"):
                    await peer.notify(
                        "item/completed" if later == "old_completed" else "item/started",
                        turnId=peer.turn,
                        item={"type": "agentMessage", "id": "old", "text": "old"},
                    )
                elif later in ("async_started", "unknown_delivery"):
                    await peer.notify(
                        "item/started",
                        turnId=peer.turn,
                        item={
                            "type": "agentMessage",
                            "id": "async",
                            "delivery": "async" if later == "async_started" else "future",
                            "text": "",
                        },
                    )
                await peer.notify(
                    "turn/completed", turn={"id": peer.turn, "status": "completed", "items": [], "error": None}
                )
                result = (await drain(run))[1]
                assert result.outcome == "unknown"
                if later == "unknown_delivery":
                    assert result.failure.code == "connection_lost"  # Unknown enum is not additive data.
                else:
                    assert result.failure.code == "unaccounted_steer"
                    assert result.native_status == "completed"
            with pytest.raises(UnavailableError):
                await thread.run("unsafe continuation")

    asyncio.run(scenario())


def test_thread_options_omit_inherited_values_on_all_history_calls():
    async def scenario():
        async with connected() as (peer, backend):
            thread = await backend.new_thread()
            assert (await peer.next("thread/start"))["params"] == {}
            await backend.resume(thread.ref)
            assert (await peer.next("thread/resume"))["params"] == {"threadId": thread.ref.id}
            await backend.fork(thread.ref)
            assert (await peer.next("thread/fork"))["params"] == {"threadId": thread.ref.id}

    asyncio.run(scenario())


def test_malformed_typed_start_response_settles_unknown_and_disables_connection():
    async def scenario():
        async with connected() as (peer, backend):
            peer.hold_start = True
            thread = await backend.new_thread()
            task = asyncio.create_task(thread.run("work"))
            call = await peer.next("turn/start")
            await peer.response(call, {"turn": {"id": peer.turn, "status": "inProgress"}})  # Missing required items.
            with pytest.raises(UnknownOutcomeError):
                await asyncio.wait_for(task, 2)
            with pytest.raises(UnavailableError):
                await backend.new_thread()

    asyncio.run(scenario())
