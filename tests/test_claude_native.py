"""Bundled Claude CLI + loopback Anthropic fixture, isolated credentials/config."""

import asyncio
import json
import os
from contextlib import asynccontextmanager

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from ohkit import Handlers
from ohkit.backends.claude import Claude
from ohkit.errors import UnavailableError

pytestmark = pytest.mark.skipif(os.environ.get("OHKIT_TEST_NATIVE") != "1", reason="Opt-in native executable tests")


class Model:
    def __init__(self):
        self.calls = []
        self.entered = asyncio.Queue()
        self.release = asyncio.Event()
        self.hold = False
        self.tasks = set()
        self.errors = []
        self.write_path = None

    async def connection(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                (
                    int(line.split(b":", 1)[1])
                    for line in headers.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                ),
                0,
            )
            body = json.loads(await reader.readexactly(length)) if length else {}
            path = headers.split(b" ")[1]
            if b"/messages" not in path or b"count_tokens" in path:
                payload = json.dumps({"input_tokens": 10}).encode()
                content_type = "application/json"
            else:
                self.calls.append(body)
                number = len(self.calls)
                await self.entered.put(number)
                if self.hold:
                    await self.release.wait()
                events = [
                    {
                        "type": "message_start",
                        "message": {
                            "id": f"msg_fixture_{number}",
                            "type": "message",
                            "role": "assistant",
                            "model": body["model"],
                            "content": [],
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": {"input_tokens": 10, "output_tokens": 0},
                        },
                    },
                    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": f"controlled answer {number}"},
                    },
                    {"type": "content_block_stop", "index": 0},
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 5},
                    },
                    {"type": "message_stop"},
                ]
                if self.write_path is not None and number == 1:
                    events[1] = {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "tool_use", "id": "tool_write_1", "name": "Write", "input": {}},
                    }
                    events[2] = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps({"file_path": self.write_path, "content": "approved write\n"}),
                        },
                    }
                    events[4]["delta"]["stop_reason"] = "tool_use"
                payload = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()
                content_type = "text/event-stream"
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
                + payload
            )
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception as exc:
            self.errors.append(exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
            self.tasks.discard(task)


@asynccontextmanager
async def fixture(root, monkeypatch):
    model = Model()
    server = await asyncio.start_server(model.connection, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(root),
        "CLAUDE_CONFIG_DIR": str(root / "claude-config"),
        "ANTHROPIC_API_KEY": "fixture-not-a-real-key",
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
    }
    # The SDK merges os.environ, so replace its inherited mapping, not just env overrides.
    monkeypatch.setattr(os, "environ", env)
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6", tools=[], system_prompt="Reply with text only.", setting_sources=[], env=env
    )
    try:
        yield model, options
    finally:
        model.release.set()
        server.close()
        await server.wait_closed()
        for task in tuple(model.tasks):
            task.cancel()
        await asyncio.gather(*model.tasks, return_exceptions=True)
        assert not model.errors, model.errors


def test_native_claude_history_across_runs_and_reopened_backend(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            async with Claude(options=options, control_timeout=20) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                first = await thread.run("Remember the first goal")
                assert first.outcome == "completed", first
                assert first.output == "controlled answer 1"
                second = await thread.run("Continue the goal")
                assert second.outcome == "completed", second
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])
                ref = thread.ref
            async with Claude(options=options) as reopened:
                thread = await reopened.resume(ref, cwd=str(tmp_path))
                third = await thread.run("Finish")
                assert third.outcome == "completed", third
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])

    asyncio.run(exercise())


def test_native_claude_interrupt_waits_for_terminal_evidence(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            model.hold = True
            async with Claude(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                async with thread.stream("A slow answer") as run:
                    await asyncio.wait_for(model.entered.get(), 20)
                    await run.cancel()
                    async for _ in run:
                        pass
                    result = await run.result()
                    assert result.outcome == "cancelled", result

    asyncio.run(exercise())


@pytest.mark.parametrize("allow", [True, False])
def test_native_claude_permissions_control_real_tool_effects(tmp_path, monkeypatch, allow):
    async def exercise():
        approved = []

        async def handler(request):
            approved.append(request)
            assert request.native.decode()["tool_name"] == "Write"
            return request.choices[0 if allow else 1]

        async with fixture(tmp_path, monkeypatch) as (model, options):
            target = tmp_path / "controlled.txt"
            model.write_path = str(target)
            options.tools = ["Write"]
            options.permission_mode = "default"
            async with Claude(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                result = await thread.run("Write the requested file", handlers=Handlers(approval=handler))
                assert result.outcome == "completed", result
                assert len(approved) == 1, json.dumps(model.calls)
                assert target.exists() == allow
                if allow:
                    assert target.read_text() == "approved write\n"
                assert len(model.calls) == 2
                assert "tool_result" in json.dumps(model.calls[-1]["messages"])

    asyncio.run(exercise())


def test_native_claude_refused_resume_does_not_start_empty_history(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            async with Claude(options=options) as backend:
                original = await backend.new_thread(cwd=str(tmp_path))
                thread = await backend.resume(original.ref, cwd=str(tmp_path))
                # No Run has persisted this UUID. The real CLI must refuse it,
                # either during initialization or as a failed native result.
                try:
                    result = await thread.run("Do not silently start over")
                except Exception as exc:
                    from claude_agent_sdk import ResultError

                    assert isinstance(exc, ResultError), exc
                    with pytest.raises(UnavailableError):
                        await thread.run("No implicit retry")
                else:
                    assert result.outcome == "failed", result
                assert not model.calls

    asyncio.run(exercise())
