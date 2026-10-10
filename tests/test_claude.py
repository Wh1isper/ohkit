import asyncio
import json

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, Transport

from ohkit import ContentEvent, Handlers, NativeEvent
from ohkit.backends.claude import Claude
from ohkit.errors import BusyError, UnavailableError, UnknownOutcomeError, UnsupportedError


class Peer(Transport):
    """A deterministic transport beneath the REAL SDK control/router/drain stack."""

    def __init__(self, options):
        self.options = options
        self.incoming = asyncio.Queue()
        self.writes = []
        self.ended = False
        self.closed = False
        self.user = asyncio.Event()
        self.initial = None

    async def connect(self):
        pass

    def is_ready(self):
        return not self.closed

    async def write(self, data):
        value = json.loads(data)
        self.writes.append(value)
        if value["type"] == "control_request":
            await self.incoming.put(
                {
                    "type": "control_response",
                    "response": {"subtype": "success", "request_id": value["request_id"], "response": {}},
                }
            )
        elif value["type"] == "user":
            self.initial = value
            self.user.set()

    async def read_messages(self):
        while True:
            message = await self.incoming.get()
            if message is None:
                return
            if isinstance(message, Exception):
                raise message
            yield message

    async def close(self):
        self.closed = True
        await self.incoming.put(None)

    async def end_input(self):
        self.ended = True
        await self.incoming.put(None)

    async def state(self, state):
        await self.incoming.put(
            {"type": "system", "subtype": "session_state_changed", "state": state, "sdk_host_only": True}
        )

    async def text(self, text, parent=None):
        await self.incoming.put(
            {
                "type": "assistant",
                "message": {"role": "assistant", "model": "fixture", "content": [{"type": "text", "text": text}]},
                "parent_tool_use_id": parent,
            }
        )

    async def result(self, output="done", **kwargs):
        await self.incoming.put(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "duration_ms": 1,
                "duration_api_ms": 1,
                "num_turns": 1,
                "session_id": self.options.session_id or self.options.resume,
                "result": output,
                "terminal_reason": "completed",
                **kwargs,
            }
        )

    async def permission(self):
        await self.incoming.put(
            {
                "type": "control_request",
                "request_id": "permission-1",
                "request": {
                    "subtype": "can_use_tool",
                    "tool_name": "Bash",
                    "input": {"command": "pwd"},
                    "tool_use_id": "call-1",
                    "permission_suggestions": [],
                },
            }
        )


@pytest.fixture
def peers(monkeypatch):
    values = []

    def create(*, options):
        peer = Peer(options)
        values.append(peer)
        return ClaudeSDKClient(options=options, transport=peer)

    monkeypatch.setattr("ohkit.backends.claude.backend.ClaudeSDKClient", create)
    return values


def test_claude_waits_for_sdk_drain_beyond_first_result(peers):
    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread(cwd="/native")
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.state("running")
                await peer.text("first")
                await peer.result("first")
                saw_first = False
                async for event in run:
                    if isinstance(event, NativeEvent) and event.method == "result" and not saw_first:
                        saw_first = True
                        assert not peer.ended and run._terminal is None
                        await peer.text("child text", parent="child-tool")
                        await peer.text("follow-up")
                        await peer.result("final", usage={"input_tokens": 5, "output_tokens": 8})
                        await peer.state("idle")
                result = await run.result()
                assert saw_first and result.output == "final" and result.outcome == "completed"
                assert result.usage.input_tokens == 5
                assert peer.closed and peer.ended
                assert peer.options.session_id == thread.ref.id
            async with thread.stream("next") as run:
                peer = peers[-1]
                await peer.user.wait()
                assert peer.options.resume == thread.ref.id and peer.options.session_id is None
                await peer.result("continued")
                async for _ in run:
                    pass
                assert (await run.result()).output == "continued"

    asyncio.run(exercise())


@pytest.mark.parametrize("aborted", [True, False])
def test_claude_interrupt_ack_is_not_terminal(peers, aborted):
    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                with pytest.raises(BusyError):
                    await thread.run("other")
                with pytest.raises(UnsupportedError):
                    await run.steer("not queued")
                await run.cancel()
                assert run._terminal is None
                await peer.result(terminal_reason="aborted_tools" if aborted else "completed")
                async for _ in run:
                    pass
                assert (await run.result()).outcome == ("cancelled" if aborted else "completed")

    asyncio.run(exercise())


@pytest.mark.parametrize("choice", [None, 0, 1, "raises"])
def test_claude_permissions_go_through_real_sdk(peers, choice):
    async def handler(request):
        assert request.native.decode()["input"] == {"command": "pwd"}
        if choice == "raises":
            raise RuntimeError("handler failure")
        return request.choices[choice]

    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream(
                "start", handlers=Handlers(approval=handler if choice is not None else None)
            ) as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.permission()
                for _ in range(100):
                    replies = [v for v in peer.writes if v["type"] == "control_response"]
                    if replies:
                        break
                    await asyncio.sleep(0.001)
                assert replies[0]["response"]["response"]["behavior"] == ("allow" if choice == 0 else "deny")
                await peer.result()
                async for _ in run:
                    pass

    asyncio.run(exercise())


def test_claude_native_permission_withdrawal_has_no_stale_reply(peers):
    async def exercise():
        entered, withdrawn = asyncio.Event(), asyncio.Event()

        async def handler(request):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                withdrawn.set()

        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start", handlers=Handlers(approval=handler)) as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.permission()
                await entered.wait()
                await peer.incoming.put({"type": "control_cancel_request", "request_id": "permission-1"})
                await withdrawn.wait()
                await peer.result()
                async for _ in run:
                    pass
                assert not [v for v in peer.writes if v["type"] == "control_response"]

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", [None, RuntimeError("wire failed")])
def test_claude_eof_without_terminal_is_unknown(peers, failure):
    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.incoming.put(failure)
                async for _ in run:
                    pass
                assert (await run.result()).outcome == "unknown"
            with pytest.raises(UnavailableError):
                await thread.run("no automatic replay")

    asyncio.run(exercise())


def test_claude_error_success_subtype_still_fails(peers):
    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                await peers[-1].user.wait()
                await peers[-1].result(is_error=True, api_error_status=429, errors=["rate limited"])
                async for _ in run:
                    pass
                result = await run.result()
                assert result.outcome == "failed" and result.failure.message == "rate limited"

    asyncio.run(exercise())


def test_claude_early_exit_unknown_when_interrupt_has_no_result(peers):
    async def exercise():
        async with Claude(cleanup_timeout=0.05) as backend:
            thread = await backend.new_thread()
            with pytest.raises(UnknownOutcomeError):
                async with thread.stream("start") as run:
                    peer = peers[-1]
                    await peer.user.wait()
                    await peer.text("running")
                    async for event in run:
                        if isinstance(event, ContentEvent):
                            break
            assert peer.closed

    asyncio.run(exercise())


def test_claude_native_config_does_not_override_owned_controls():
    with pytest.raises(ValueError):
        Claude(options=ClaudeAgentOptions(resume="someone-else"))
    with pytest.raises(UnsupportedError):
        Claude(options=ClaudeAgentOptions(include_partial_messages=True))


@pytest.mark.parametrize("target", ["thread", "backend"])
def test_claude_close_waits_for_native_history_loading(monkeypatch, tmp_path, target):
    async def exercise():
        loading, release = asyncio.Event(), asyncio.Event()
        peers = []

        class Store:
            async def load(self, key):
                loading.set()
                await release.wait()
                return None

        def transport(*, prompt, options):
            peer = Peer(options)
            peers.append(peer)
            return peer

        monkeypatch.setattr("claude_agent_sdk._internal.transport.subprocess_cli.SubprocessCLITransport", transport)
        async with Claude(
            options=ClaudeAgentOptions(session_store=Store(), cwd=tmp_path), cleanup_timeout=1
        ) as backend:
            original = await backend.new_thread()
            thread = await backend.resume(original.ref)
            running = asyncio.create_task(thread.run("start"))
            await asyncio.wait_for(loading.wait(), 1)
            closing = asyncio.create_task(thread.close() if target == "thread" else backend.close())
            await asyncio.sleep(0.02)
            premature = closing.done()
            release.set()
            async with asyncio.timeout(2):
                while not peers:
                    await asyncio.sleep(0)
                peer = peers[-1]
                await peer.user.wait()
                await peer.result(terminal_reason="aborted_tools")
                await running
                await closing
            cleaned = peer.closed
            if not cleaned:
                await peer.close()
            assert not premature, "close returned before owned startup settled"
            assert cleaned, "native transport escaped cleanup"

    asyncio.run(exercise())


@pytest.mark.parametrize("kind", ["failed", "aborted", "success", "failed_then_activity", "failed_crash"])
def test_claude_exit_classification_preserves_only_complete_matching_results(peers, kind):
    from claude_agent_sdk import ProcessError

    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.state("running")
                if kind.startswith("failed"):
                    await peer.result(is_error=True, subtype="error_max_turns", errors=["maximum turns reached"])
                elif kind == "aborted":
                    await peer.result(terminal_reason="aborted_streaming")
                else:
                    await peer.result()
                if kind == "failed_then_activity":
                    await peer.text("unfinished follow-up")
                await peer.incoming.put(ProcessError("native exit", exit_code=2 if kind == "failed_crash" else 1))
                async for _ in run:
                    pass
                result = await run.result()
                expected = {"failed": "failed", "aborted": "cancelled"}.get(kind, "unknown")
                assert result.outcome == expected
                assert thread._available == (expected != "unknown")
                if expected == "failed":
                    assert result.failure.code == "error_max_turns"
                    assert result.failure.message == "maximum turns reached"
            if kind == "failed":
                async with thread.stream("continue after known failure") as run:
                    peer = peers[-1]
                    await peer.user.wait()
                    assert peer.options.resume == thread.ref.id
                    await peer.result("recovered")
                    async for _ in run:
                        pass
                    assert (await run.result()).outcome == "completed"

    asyncio.run(exercise())


def test_claude_eof_after_unfinished_followup_is_unknown(peers):
    async def exercise():
        async with Claude(cleanup_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                await peer.state("running")
                await peer.result("first turn completed")
                await peer.text("second turn in progress")
                await peer.incoming.put(None)
                async for _ in run:
                    pass
                assert (await run.result()).outcome == "unknown"
                assert not thread._available

    asyncio.run(exercise())


def test_claude_backend_close_stops_existing_thread_admission(peers):
    async def exercise():
        backend = await Claude(cleanup_timeout=0.1).__aenter__()
        thread = await backend.new_thread()
        closing = asyncio.create_task(backend.close())
        await asyncio.sleep(0)
        assert backend._closed
        try:
            with pytest.raises(UnavailableError):
                await thread.run("must not dispatch after close begins")
        finally:
            await closing
        assert not peers

    asyncio.run(exercise())


@pytest.mark.parametrize("terminal", ["completed", "aborted_tools", None])
def test_claude_eof_settles_interrupt_without_acknowledgement(peers, terminal):
    async def exercise():
        async with Claude(cleanup_timeout=0.2, control_timeout=1) as backend:
            thread = await backend.new_thread()
            async with thread.stream("start") as run:
                peer = peers[-1]
                await peer.user.wait()
                entered = asyncio.Event()
                original = peer.write

                async def write(data):
                    value = json.loads(data)
                    if value.get("request", {}).get("subtype") == "interrupt":
                        entered.set()
                        # Native completion races the control reply; do not ack.
                        return
                    await original(data)

                peer.write = write
                cancelling = asyncio.create_task(run.cancel())
                await entered.wait()
                if terminal is None:
                    await peer.incoming.put(None)
                else:
                    await peer.result(terminal_reason=terminal)
                async with asyncio.timeout(0.5):
                    await cancelling
                    async for _ in run:
                        pass
                expected = (
                    "unknown" if terminal is None else "cancelled" if terminal == "aborted_tools" else "completed"
                )
                assert (await run.result()).outcome == expected
                assert peer.closed

    asyncio.run(exercise())
