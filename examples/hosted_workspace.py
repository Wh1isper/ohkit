"""Authenticated loopback hosting; TRUSTED, UNSANDBOXED host-account execution.

Run from the checkout: uv run python -m examples.hosted_workspace /trusted/project
The native Codex installation must already have model-provider configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
from collections.abc import AsyncIterator
from http import HTTPStatus
from pathlib import Path

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from examples.local_workspace import LocalWorkspace
from ohkit import ProtocolError
from ohkit.backends.codex import Codex, CodexExecBridge, CodexExecutor, CodexThreadOptions
from ohkit.workspace import Workspace


class ExecutorHost:
    """Application-owned exact routes and per-route bearer authorization."""

    def __init__(self, routes: dict[str, tuple[str, Workspace]]) -> None:
        if any(not token for token, _ in routes.values()):
            raise ValueError("Each executor route requires a nonempty bearer token")
        self.routes = {path: (token, CodexExecBridge(workspace)) for path, (token, workspace) in routes.items()}

    def authorize(self, connection: ServerConnection, request: Request) -> Response | None:
        route = self.routes.get(request.path)
        if route is None:
            return connection.respond(HTTPStatus.NOT_FOUND, "Unknown executor route\n")
        headers = request.headers.get_all("Authorization")
        if len(headers) != 1 or not secrets.compare_digest(headers[0].encode(), ("Bearer " + route[0]).encode()):
            return connection.respond(HTTPStatus.UNAUTHORIZED, "Executor authorization required\n")
        return None

    async def handle(self, connection: ServerConnection) -> None:
        assert connection.request is not None
        _, bridge = self.routes[connection.request.path]

        async def messages() -> AsyncIterator[str]:
            async for message in connection:
                if not isinstance(message, str):
                    raise ProtocolError("The executor requires text messages")
                yield message

        try:
            await bridge.serve(messages(), connection.send)
        except ConnectionClosed:
            # Native shutdown may omit the WebSocket close frame. Bridge cleanup
            # has already settled; CleanupError is deliberately not swallowed.
            pass
        finally:
            await connection.close()


async def main(cwd: Path, prompt: str) -> None:
    print("WARNING: trusted unsandboxed execution with full host-account authority.")
    workspace = LocalWorkspace(cwd)
    token = secrets.token_urlsafe(32)
    host = ExecutorHost({"/project/exec": (token, workspace)})
    async with serve(host.handle, "127.0.0.1", 0, process_request=host.authorize) as server:
        endpoint = CodexExecutor(
            f"ws://127.0.0.1:{next(iter(server.sockets)).getsockname()[1]}/project/exec", bearer_token=token
        )
        # Close native control first, then the application-owned listener.
        async with Codex() as backend:
            thread = await backend.new_thread(
                cwd=str(workspace.cwd),
                executor=endpoint,
                options=CodexThreadOptions(sandbox="danger-full-access", approval_policy="never"),
            )
            result = await thread.run(prompt)
            print(result.outcome, result.output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cwd", type=Path)
    parser.add_argument("--prompt", default="Read AGENTS.md if present, then summarize the project.")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.cwd, arguments.prompt))
