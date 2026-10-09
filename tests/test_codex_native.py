"""Real pinned Codex + deterministic loopback Responses, never paid model calls.

Opt in with OHKIT_TEST_NATIVE=1. An explicit OHKIT_CODEX_BINARY may replace the
verified official Linux fixture download; its version is checked before use.
"""

import asyncio
import json
import os
import platform
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from ohkit import Answer, ContentEvent, Handlers, QuestionResponse, ToolEvent
from ohkit.backends.codex import Codex, CodexOptions, CodexThreadOptions
from ohkit.backends.codex._version import CODEX_VERSION
from scripts.codex_protocol import SOURCE, download_binary

pytestmark = pytest.mark.skipif(os.environ.get("OHKIT_TEST_NATIVE") != "1", reason="Opt-in native executable tests")


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    supplied = os.environ.get("OHKIT_CODEX_BINARY")
    if supplied:
        return supplied
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        pytest.skip("Provide OHKIT_CODEX_BINARY for this platform")
    root = tmp_path_factory.mktemp("codex-native")
    metadata = json.loads((SOURCE / "manifest.json").read_text())
    assert metadata["version"] == CODEX_VERSION
    return str(download_binary(metadata, root))


class Model:
    def __init__(self):
        self.calls = []
        self.entered = asyncio.Queue()
        self.hold = False
        self.release = asyncio.Event()
        self.tool = None
        self.tool_name = "exec_command"
        self.tasks = set()
        self.errors = []

    async def connection(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            body = json.loads(await reader.readexactly(length))
            self.calls.append(body)
            number = len(self.calls)
            await self.entered.put(number)
            if self.hold:
                await self.release.wait()
            if self.tool is not None and number == 1:
                item = {
                    "type": "function_call",
                    "id": "tool-1",
                    "call_id": "call-1",
                    "name": self.tool_name,
                    "arguments": json.dumps(self.tool),
                }
            else:
                item = {
                    "type": "message",
                    "id": f"message-{number}",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": f"controlled answer {number}"}],
                }
            events = [
                {"type": "response.created", "response": {"id": f"response-{number}"}},
                {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {**item, "content": []} if item["type"] == "message" else item,
                },
            ]
            if item["type"] == "message":
                events.append(
                    {
                        "type": "response.output_text.delta",
                        "item_id": item["id"],
                        "output_index": 0,
                        "content_index": 0,
                        "delta": f"controlled answer {number}",
                    }
                )
            events.extend(
                [
                    {"type": "response.output_item.done", "output_index": 0, "item": item},
                    {
                        "type": "response.completed",
                        "response": {
                            "id": f"response-{number}",
                            "status": "completed",
                            "output": [item],
                            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                        },
                    },
                ]
            )
            payload = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()
            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
                + payload
            )
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass  # Native interrupt closes an in-flight model connection.
        except Exception as error:
            self.errors.append(error)
        finally:
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)


@asynccontextmanager
async def fixture(binary, root: Path):
    version = await asyncio.create_subprocess_exec(binary, "--version", stdout=asyncio.subprocess.PIPE)
    output, _ = await version.communicate()
    assert output.decode().strip() == f"codex-cli {CODEX_VERSION}"
    model = Model()
    server = await asyncio.start_server(model.connection, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    home = root / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(f"""model = "gpt-5.1-codex"
model_provider = "fixture"
approval_policy = "never"
sandbox_mode = "read-only"
[features]
shell_snapshot = false
[model_providers.fixture]
name = "fixture"
base_url = "http://127.0.0.1:{port}"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
""")
    # No ambient model credentials, shared home, or user config is inherited.
    env = (("PATH", os.environ.get("PATH", "/usr/bin:/bin")), ("HOME", str(root)), ("CODEX_HOME", str(home)))
    options = CodexOptions(executable=binary, env=env, request_timeout=10, cleanup_timeout=10)
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


def test_native_stream_result_usage_fork_and_reopen_history(binary, tmp_path):
    async def scenario():
        async with fixture(binary, tmp_path) as (_, options):
            async with Codex(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                async with thread.stream("Reply with a short text only; do not use tools.") as run:
                    events = [event async for event in run]
                    result = await run.result()
                assert result.outcome == "completed", result
                assert result.output == "controlled answer 1"
                assert result.usage is not None and result.usage.total_tokens == 15
                assert any(isinstance(e, ContentEvent) and e.channel == "assistant" for e in events)
                forked = await backend.fork(thread.ref)
                assert forked.ref.id != thread.ref.id
                reference = thread.ref
            async with Codex(options=options) as reopened:
                resumed = await reopened.resume(reference, cwd=str(tmp_path))
                result = await resumed.run("Another short reply only.")
                assert result.outcome == "completed" and result.output == "controlled answer 2"

    asyncio.run(scenario())


def test_native_steer_consumed_before_normal_completion_then_interrupt(binary, tmp_path):
    async def scenario():
        async with fixture(binary, tmp_path) as (model, options):
            model.hold = True
            async with Codex(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                async with thread.stream("Reply only with text.") as run:
                    assert await model.entered.get() == 1
                    await run.steer("Include a concise follow-up answer.")
                    model.hold = False
                    model.release.set()
                    events = [event async for event in run]
                    result = await run.result()
                assert result.outcome == "completed", result
                assert len(model.calls) == 2
                second_input = model.calls[1]["input"]
                assert any(
                    item.get("role") == "user"
                    and any(
                        part.get("text") == "Include a concise follow-up answer." for part in item.get("content", [])
                    )
                    for item in second_input
                ), second_input
                assert "controlled answer 2" in result.output
                assert any(e.kind == "lifecycle" and e.phase == "terminal" for e in events)
                # No silently deferred steering becomes a future foreground task.
                third = await thread.run("A new short reply only.")
                assert third.outcome == "completed" and third.output == "controlled answer 3"
                assert len(model.calls) == 3
                model.release.clear()
                model.hold = True
                async with thread.stream("Another reply.") as run:
                    while await model.entered.get() != 4:
                        pass
                    await run.cancel()
                    async for _ in run:
                        pass
                    assert (await run.result()).outcome == "cancelled"

    asyncio.run(scenario())


@pytest.mark.parametrize("decision", ["cancel", "accept"])
def test_native_approval_handler_controls_real_command(binary, tmp_path, decision):
    async def scenario():
        target = tmp_path / "effect.txt"
        requests = []

        async def handle(request):
            requests.append(request)
            return next(choice for choice in request.choices if choice.kind == decision)

        async with fixture(binary, tmp_path) as (model, options):
            model.tool = {"cmd": f"printf controlled > {target}", "yield_time_ms": 1000}
            async with Codex(options=options) as backend:
                thread = await backend.new_thread(
                    cwd=str(tmp_path), options=CodexThreadOptions(approval_policy="untrusted", sandbox="read-only")
                )
                async with thread.stream("Run the controlled command.", handlers=Handlers(approval=handle)) as run:
                    events = [event async for event in run]
                    result = await run.result()
                assert requests, (result, events, model.calls)
                assert result.outcome == ("cancelled" if decision == "cancel" else "completed"), (result, requests)
                assert any(isinstance(event, ToolEvent) for event in events)
                assert target.exists() == (decision == "accept")

    asyncio.run(scenario())


@asynccontextmanager
async def borrowed_service(binary, options):
    process = await asyncio.create_subprocess_exec(
        binary,
        "app-server",
        "--listen",
        "ws://127.0.0.1:0",
        env=dict(options.env),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    drains = []
    try:
        async with asyncio.timeout(10):
            while True:
                line = await process.stderr.readline()
                assert line, "Native WebSocket service exited before readiness"
                if b"listening on:" in line:
                    url = line.decode().strip().split("listening on:", 1)[1].strip()
                    break
        # Native startup banner follows bind; no polling or readiness sleep.
        drains = [asyncio.create_task(process.stdout.read()), asyncio.create_task(process.stderr.read())]
        yield (
            process,
            CodexOptions(
                websocket_url=url, history_scope="isolated-native-websocket", request_timeout=10, cleanup_timeout=10
            ),
        )
    finally:
        if process.returncode is None:
            process.terminate()
        async with asyncio.timeout(10):
            await process.wait()
        await asyncio.gather(*drains)


def test_native_websocket_closes_connection_not_borrowed_service(binary, tmp_path):
    async def scenario():
        async with fixture(binary, tmp_path) as (model, local):
            async with borrowed_service(binary, local) as (service, remote):
                async with Codex(options=remote) as backend:
                    thread = await backend.new_thread(cwd=str(tmp_path))
                    result = await thread.run("A short reply only.")
                    assert result.outcome == "completed" and result.output == "controlled answer 1"
                    reference = thread.ref
                assert service.returncode is None
                async with Codex(options=remote) as backend:
                    resumed = await backend.resume(reference, cwd=str(tmp_path))
                    result = await resumed.run("Another reply only.")
                    assert result.outcome == "completed" and result.output == "controlled answer 2"
                assert service.returncode is None and len(model.calls) == 2

    asyncio.run(scenario())


def test_native_question_handler_response_reaches_next_model_request(binary, tmp_path):
    async def scenario():
        requests = []

        async def handle(request):
            requests.append(request)
            assert request.questions[0].id == "direction"
            assert tuple(option.label for option in request.questions[0].options) == ("A", "B")
            return QuestionResponse((Answer("direction", ("A",)),))

        async with fixture(binary, tmp_path) as (model, options):
            model.tool_name = "request_user_input"
            model.tool = {
                "questions": [
                    {
                        "id": "direction",
                        "header": "Direction",
                        "question": "Choose the controlled direction.",
                        "options": [
                            {"label": "A", "description": "First"},
                            {"label": "B", "description": "Second"},
                        ],
                    }
                ]
            }
            options = replace(options, config=("features.default_mode_request_user_input=true",))
            async with Codex(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                result = await thread.run("Ask the controlled question.", handlers=Handlers(question=handle))
                assert requests, (result, model.calls)
                assert result.outcome == "completed", result
                assert any(
                    item.get("type") == "function_call_output" and '"A"' in item.get("output", "")
                    for item in model.calls[1]["input"]
                ), model.calls[1]["input"]

    asyncio.run(scenario())
