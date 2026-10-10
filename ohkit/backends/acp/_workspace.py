"""ACP text and terminal projections over borrowed Workspace operations."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
import codecs
from pathlib import PurePosixPath, PureWindowsPath
from uuid import uuid4

from acp import RequestError
from acp import schema as wire

from ...execution import _settle
from ...workspace import Process, ProcessRequest, Workspace


class _Terminal:
    def __init__(self, process: Process, limit: int) -> None:
        self.process = process
        self.limit = limit
        self.output = b""
        self.truncated = False
        self.reader = asyncio.create_task(self._read())
        self.exit = asyncio.create_task(process.wait())
        self.closing: asyncio.Task[None] | None = None
        # Retain failures for the next callback/close, without unobserved-task warnings.
        self.reader.add_done_callback(self._observed)
        self.exit.add_done_callback(self._observed)

    @staticmethod
    def _observed(task: asyncio.Task[object]) -> None:
        if not task.cancelled():
            task.exception()

    def _append(self, text: str) -> None:
        self.output += text.encode("utf-8")
        if len(self.output) > self.limit:
            self.truncated = True
            self.output = (
                self.output[-self.limit :].decode("utf-8", errors="ignore").encode("utf-8") if self.limit else b""
            )

    async def _read(self) -> None:
        decoders = {stream: codecs.getincrementaldecoder("utf-8")("replace") for stream in ("stdout", "stderr", "pty")}
        while True:
            block = await self.process.read(65536)
            decoder = decoders[block.stream]
            if block.lost_bytes:
                self.truncated = True
                # A gap invalidates any partial character held before it.
                decoder.reset()
            self._append(decoder.decode(block.data))
            if block.eof:
                for decoder in decoders.values():
                    self._append(decoder.decode(b"", final=True))
                return

    async def wait(self) -> wire.WaitForTerminalExitResponse:
        code = await asyncio.shield(self.exit)
        return wire.WaitForTerminalExitResponse(
            exit_code=code if code >= 0 else None, signal=str(-code) if code < 0 else None
        )

    def snapshot(self) -> wire.TerminalOutputResponse:
        if self.reader.done():
            self.reader.result()
        status = None
        if self.exit.done():
            code = self.exit.result()
            status = wire.TerminalExitStatus(
                exit_code=code if code >= 0 else None, signal=str(-code) if code < 0 else None
            )
        return wire.TerminalOutputResponse(
            output=self.output.decode("utf-8"), truncated=self.truncated, exit_status=status
        )

    async def close(self) -> None:
        if self.closing is None:
            self.closing = asyncio.create_task(self._close())
        await _settle(self.closing)

    async def _close(self) -> None:
        try:
            await self.process.close()
        finally:
            # Provider close owns command settlement and unblocking outstanding reads.
            await asyncio.gather(self.reader, self.exit)


class WorkspaceCallbacks:
    def __init__(self, workspace: Workspace, cwd: str, output_limit: int, terminal_limit: int) -> None:
        self.workspace = workspace
        self.cwd = cwd
        self.output_limit = output_limit
        self.terminal_limit = terminal_limit
        self.terminals: dict[str, _Terminal] = {}
        self.starts: set[asyncio.Task[wire.CreateTerminalResponse]] = set()
        self.closed = False

    async def read(self, path: str, line: int | None, limit: int | None) -> wire.ReadTextFileResponse:
        if (line is not None and line < 1) or (limit is not None and limit < 0):
            raise RequestError.invalid_params({"details": "Invalid line range"})
        text = (await self.workspace.files.read(path)).decode("utf-8")
        if line is not None or limit is not None:
            start = (line or 1) - 1
            text = "".join(text.splitlines(keepends=True)[start : None if limit is None else start + limit])
        return wire.ReadTextFileResponse(content=text)

    async def write(self, path: str, content: str) -> wire.WriteTextFileResponse:
        info = await self.workspace.describe()
        target_path = PureWindowsPath(path) if info.path_style == "windows" else PurePosixPath(path)
        await self.workspace.files.create_directory(str(target_path.parent), recursive=True)
        await self.workspace.files.write(path, content.encode("utf-8"))
        return wire.WriteTextFileResponse()

    async def create(self, request: ProcessRequest, limit: int | None) -> wire.CreateTerminalResponse:
        if self.closed:
            raise RequestError.invalid_params({"details": "Workspace binding is closed"})
        if len(self.terminals) + len(self.starts) >= self.terminal_limit:
            raise RequestError.internal_error({"details": "Release a terminal before creating another"})
        if limit is not None and limit < 0:
            raise RequestError.invalid_params({"details": "Negative output limit"})
        task = asyncio.create_task(
            self._start(request, min(limit, self.output_limit) if limit is not None else self.output_limit)
        )
        self.starts.add(task)
        try:
            return await asyncio.shield(task)
        finally:
            # Keep cancelled callbacks' pending launches owned until close.
            if task.done():
                self.starts.discard(task)

    async def _start(self, request: ProcessRequest, limit: int) -> wire.CreateTerminalResponse:
        process = await self.workspace.start_process(request)
        if self.closed:
            await process.close()
            raise RequestError.invalid_params({"details": "Workspace binding closed during launch"})
        identity = "terminal_" + uuid4().hex
        self.terminals[identity] = _Terminal(process, limit)
        return wire.CreateTerminalResponse(terminal_id=identity)

    def get(self, identity: str) -> _Terminal:
        terminal = self.terminals.get(identity)
        if terminal is None:
            raise RequestError.invalid_params({"details": "Unknown or released terminal"})
        return terminal

    async def release(self, identity: str) -> None:
        terminal = self.get(identity)
        await terminal.close()
        self.terminals.pop(identity, None)

    async def close(self) -> None:
        self.closed = True
        results = await asyncio.gather(
            *(terminal.close() for terminal in self.terminals.values()), return_exceptions=True
        )
        await asyncio.gather(*self.starts, return_exceptions=True)
        self.terminals.clear()
        self.starts.clear()
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            raise ExceptionGroup("ACP terminal cleanup failed", errors)
