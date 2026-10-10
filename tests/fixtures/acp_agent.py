"""Deterministic independent ACP wire peer, not an LLM or provider simulation."""

import asyncio
import json
import os
import sys
from uuid import uuid4

from acp import stdio_streams


async def main():
    reader, writer = await stdio_streams()
    pending = {}
    tasks = set()
    cancelled = asyncio.Event()
    session = None
    cwd = None
    capabilities = None
    counter = 0

    async def send(value):
        writer.write((json.dumps({"jsonrpc": "2.0", **value}) + "\n").encode())
        await writer.drain()

    async def call(method, **params):
        nonlocal counter
        counter += 1
        identity = f"agent-{counter}"
        future = asyncio.get_running_loop().create_future()
        pending[identity] = future
        await send({"id": identity, "method": method, "params": {"sessionId": session, **params}})
        return await future

    async def update(text):
        await send(
            {
                "method": "session/update",
                "params": {
                    "sessionId": session,
                    "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": text}},
                },
            }
        )

    async def prompt(message):
        cancelled.clear()
        text = message["params"]["prompt"][0]["text"]
        stop = "end_turn"
        if text == "disconnect":
            os._exit(0)
        if text == "reject":
            await send({"id": message["id"], "error": {"code": -32602, "message": "Rejected input"}})
            return
        if text == "permission":
            result = await call(
                "session/request_permission",
                toolCall={"toolCallId": "tool-1", "title": "Run command", "kind": "execute", "status": "pending"},
                options=[
                    {"optionId": "once", "name": "Allow once", "kind": "allow_once"},
                    {"optionId": "always", "name": "Always deny", "kind": "reject_always"},
                ],
            )
            await update(json.dumps(result["outcome"], sort_keys=True))
        elif text == "workspace":
            assert capabilities["fs"]["readTextFile"] and capabilities["terminal"]
            await call("fs/write_text_file", path=cwd + "/nested/test.txt", content="one\r\ntwo\r\nthree\n")
            result = await call("fs/read_text_file", path=cwd + "/nested/test.txt", line=2, limit=1)
            assert result["content"] == "two\r\n"
            terminal = await call(
                "terminal/create",
                command=sys.executable,
                args=["-c", "import os; print(os.environ['ACP_MARKER'] + ':' + os.getcwd())"],
                env=[{"name": "ACP_MARKER", "value": "target"}],
            )
            identity = terminal["terminalId"]
            exit = await call("terminal/wait_for_exit", terminalId=identity)
            assert exit["exitCode"] == 0
            for _ in range(100):
                result = await call("terminal/output", terminalId=identity)
                if result["output"]:
                    break
                await asyncio.sleep(0.01)
            again = await call("terminal/output", terminalId=identity)
            assert result == again
            await call("terminal/release", terminalId=identity)
            await update(result["output"])
        elif text == "wait" or text == "ignore_cancel":
            await update("working")
            if text == "wait":
                await cancelled.wait()
                stop = "cancelled"
            else:
                await asyncio.Event().wait()
        elif text == "burst":
            for i in range(100):
                await update(str(i) + ",")
        else:
            await update("answer:" + text)
        await send({"id": message["id"], "result": {"stopReason": stop}})

    while line := await reader.readline():
        message = json.loads(line)
        if "method" not in message:
            future = pending.pop(message["id"])
            if "error" in message:
                future.set_exception(RuntimeError(message["error"]))
            else:
                future.set_result(message["result"])
            continue
        method = message["method"]
        params = message.get("params", {})
        if method == "initialize":
            capabilities = params.get("clientCapabilities", {})
            result = {
                "protocolVersion": 1,
                "agentCapabilities": {"loadSession": True, "sessionCapabilities": {"resume": {}, "fork": {}}},
            }
        elif method == "session/new":
            session, cwd = str(uuid4()), params["cwd"]
            result = {"sessionId": session}
        elif method in ("session/load", "session/resume"):
            session, cwd = params["sessionId"], params["cwd"]
            await update("replayed history must not become run output")
            result = {}
        elif method == "session/prompt":
            task = asyncio.create_task(prompt(message))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            continue
        elif method == "session/cancel":
            cancelled.set()
            continue
        else:
            raise AssertionError(method)
        await send({"id": message["id"], "result": result})
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(main())
