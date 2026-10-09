"""Control connection ownership, independent from service ownership."""

from __future__ import annotations

import asyncio
import os
from typing import Protocol

from websockets.asyncio.client import ClientConnection, connect

from ...errors import CleanupError, ProtocolError, UnavailableError
from .options import CodexOptions

MAX_MESSAGE_BYTES = 8 * 1024 * 1024


class Transport(Protocol):
    async def receive(self) -> str: ...
    async def send(self, text: str) -> None: ...
    async def close(self) -> None: ...


class Stdio:
    def __init__(self, process: asyncio.subprocess.Process, timeout: float) -> None:
        self.process = process
        self.timeout = timeout
        self.closed = False
        self.stderr_task = asyncio.create_task(self._discard_diagnostics())

    @classmethod
    async def open(cls, options: CodexOptions) -> Stdio:
        argv = [options.executable, "app-server", "--listen", "stdio://"]
        for override in options.config:
            argv.extend(("-c", override))
        process = await asyncio.create_subprocess_exec(
            *argv,
            env=dict(options.env) if options.env is not None else None,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=MAX_MESSAGE_BYTES,
        )
        return cls(process, options.cleanup_timeout)

    async def _discard_diagnostics(self) -> None:
        # Drain, but never automatically publish private diagnostics or secrets.
        assert self.process.stderr is not None
        while await self.process.stderr.read(65536):
            pass

    async def receive(self) -> str:
        assert self.process.stdout is not None
        line = await self.process.stdout.readline()
        if not line:
            raise UnavailableError("Codex stdio connection closed")
        if len(line) > MAX_MESSAGE_BYTES:
            raise ProtocolError("Native message exceeds configured size bound")
        return line.decode("utf-8", errors="strict")

    async def send(self, text: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(text.encode("utf-8") + b"\n")
        await self.process.stdin.drain()

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            async with asyncio.timeout(self.timeout):
                await self.process.wait()
        except TimeoutError:
            if self.process.returncode is None:
                self.process.terminate()
            try:
                async with asyncio.timeout(self.timeout):
                    await self.process.wait()
            except TimeoutError:
                if self.process.returncode is None:
                    self.process.kill()
                await self.process.wait()
        finally:
            await self.stderr_task


class WebSocket:
    def __init__(self, connection: ClientConnection) -> None:
        self.connection = connection

    @classmethod
    async def open(cls, options: CodexOptions) -> WebSocket:
        assert options.websocket_url is not None
        try:
            connection = await connect(
                options.websocket_url,
                additional_headers=options.headers,
                max_size=MAX_MESSAGE_BYTES,
                max_queue=16,
                open_timeout=options.request_timeout,
                close_timeout=options.cleanup_timeout,
                proxy=None,
            )
        except Exception:
            # Upstream connection errors may include credentialed headers or URLs.
            raise UnavailableError("Could not connect to the remote Codex service") from None
        return cls(connection)

    async def receive(self) -> str:
        try:
            message = await self.connection.recv()
        except Exception:
            raise UnavailableError("Remote Codex connection closed") from None
        if not isinstance(message, str):
            raise ProtocolError("Codex requires text WebSocket messages")
        return message

    async def send(self, text: str) -> None:
        try:
            await self.connection.send(text)
        except Exception:
            raise UnavailableError("Remote Codex write failed") from None

    async def close(self) -> None:
        try:
            await self.connection.close()
        except Exception:
            raise CleanupError("Remote Codex connection cleanup failed") from None


def local_scope(options: CodexOptions) -> str:
    if options.history_scope is not None:
        return options.history_scope
    env = dict(options.env) if options.env is not None else os.environ
    return os.path.abspath(env.get("CODEX_HOME", os.path.join(env.get("HOME", os.path.expanduser("~")), ".codex")))
