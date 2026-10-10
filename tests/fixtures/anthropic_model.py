"""Credential-isolated loopback Anthropic model for native harness tests."""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from claude_agent_sdk import ClaudeAgentOptions


class Model:
    def __init__(self):
        self.calls = []
        self.entered = asyncio.Queue()
        self.release = asyncio.Event()
        self.hold = False
        self.tasks = set()
        self.errors = []
        self.tools = []

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
                if number <= len(self.tools):
                    tool_name, tool_input = self.tools[number - 1]
                    events[1] = {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "tool_use", "id": f"tool_{number}", "name": tool_name, "input": {}},
                    }
                    events[2] = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps(tool_input),
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
