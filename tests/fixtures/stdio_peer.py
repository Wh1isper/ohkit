"""Controlled child process for ownership/failure tests, not a Codex emulator."""

import json
import os
import sys
from pathlib import Path

Path(os.environ["OHKIT_TEST_PID"]).write_text(str(os.getpid()))


def send(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    call = json.loads(line)
    method = call.get("method")
    with Path(os.environ["OHKIT_TEST_CALLS"]).open("a") as log:
        log.write(str(method) + "\n")
    if method == "initialize":
        send({"id": call["id"], "result": {"userAgent": "controlled-test-peer"}})
    elif method == "thread/start":
        send({"id": call["id"], "result": {"thread": {"id": "owned-thread"}}})
    elif method == "turn/start":
        input = call["params"]["input"][0]["text"]
        if input == "die":
            os._exit(3)
        send(
            {
                "method": "turn/started",
                "params": {"threadId": "owned-thread", "turn": {"id": "owned-turn", "status": "inProgress"}},
            }
        )
        send({"id": call["id"], "result": {"turn": {"id": "owned-turn", "status": "inProgress"}}})
    elif method == "turn/interrupt":
        send({"id": call["id"], "result": {}})
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "owned-thread",
                    "turn": {"id": "owned-turn", "status": "interrupted", "error": None},
                },
            }
        )
