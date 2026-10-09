"""Executable reference provider for trusted, unsandboxed POSIX applications.

The cwd is NOT a security boundary. Commands and files have the host account's
full authority. Production applications should supply their actual provider.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import platform
import shutil
import signal
import stat
from collections import deque
from pathlib import Path
from typing import BinaryIO, Literal

from ohkit import UnsupportedError
from ohkit.workspace import (
    DirectoryEntry,
    FileBlock,
    FileInfo,
    ProcessOutput,
    ProcessRequest,
    Shell,
    WorkspaceInfo,
)


class LocalReadFile:
    def __init__(self, file: BinaryIO) -> None:
        self.file = file
        self.lock = asyncio.Lock()

    async def read(self, offset: int, max_bytes: int) -> FileBlock:
        if offset < 0 or max_bytes < 0:
            raise ValueError("Read bounds must be nonnegative")

        def read() -> FileBlock:
            self.file.seek(offset)
            data = self.file.read(max_bytes)
            return FileBlock(data, offset + len(data) >= os.fstat(self.file.fileno()).st_size)

        async with self.lock:
            return await asyncio.to_thread(read)

    async def close(self) -> None:
        async with self.lock:
            await asyncio.to_thread(self.file.close)


def _kind(mode: int) -> Literal["file", "directory", "symlink", "other"]:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


class LocalFiles:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def path(self, path: str, target: str | None, follow: bool = True) -> Path:
        if target is not None:
            raise UnsupportedError("This provider has no target selector")
        result = self.cwd / path
        if not follow and any(p.is_symlink() for p in (result, *result.parents)):
            raise UnsupportedError("This example rejects no-follow traversal through symlinks")
        return result

    async def read(self, path: str, *, follow_symlinks: bool = True, target: str | None = None) -> bytes:
        return await asyncio.to_thread(self.path(path, target, follow_symlinks).read_bytes)

    async def write(self, path: str, data: bytes, *, follow_symlinks: bool = True, target: str | None = None) -> None:
        await asyncio.to_thread(self.path(path, target, follow_symlinks).write_bytes, data)

    async def open_read(self, path: str, *, target: str | None = None) -> LocalReadFile:
        return LocalReadFile(await asyncio.to_thread(self.path(path, target).open, "rb"))

    async def metadata(self, path: str, *, follow_symlinks: bool = True, target: str | None = None) -> FileInfo:
        value = await asyncio.to_thread(self.path(path, target).stat, follow_symlinks=follow_symlinks)
        # POSIX ctime is metadata-change time, not creation time. Do not invent it.
        return FileInfo(
            _kind(value.st_mode),
            value.st_size,
            value.st_mtime_ns // 1_000_000,
            is_symlink=await asyncio.to_thread(self.path(path, target).is_symlink),
        )

    async def list_directory(self, path: str, *, target: str | None = None) -> tuple[DirectoryEntry, ...]:
        def entries() -> tuple[DirectoryEntry, ...]:
            with os.scandir(self.path(path, target)) as iterator:
                return tuple(
                    DirectoryEntry(entry.name, _kind(entry.stat(follow_symlinks=False).st_mode)) for entry in iterator
                )

        return await asyncio.to_thread(entries)

    async def create_directory(
        self, path: str, *, recursive: bool = False, follow_symlinks: bool = True, target: str | None = None
    ) -> None:
        await asyncio.to_thread(self.path(path, target, follow_symlinks).mkdir, parents=recursive, exist_ok=recursive)

    async def remove(
        self,
        path: str,
        *,
        recursive: bool = False,
        missing_ok: bool = False,
        follow_symlinks: bool = True,
        target: str | None = None,
    ) -> None:
        resolved = self.path(path, target, follow_symlinks)

        def remove() -> None:
            try:
                if resolved.is_dir() and not resolved.is_symlink():
                    shutil.rmtree(resolved) if recursive else resolved.rmdir()
                else:
                    resolved.unlink()
            except FileNotFoundError:
                if not missing_ok:
                    raise

        await asyncio.to_thread(remove)

    async def copy(
        self,
        source: str,
        destination: str,
        *,
        recursive: bool = False,
        overwrite: bool = False,
        target: str | None = None,
    ) -> None:
        src, dst = self.path(source, target), self.path(destination, target)

        def copy() -> None:
            if not overwrite and (dst.exists() or dst.is_symlink()):
                raise FileExistsError(str(dst))
            if src.is_symlink():
                dst.symlink_to(os.readlink(src))
            elif src.is_dir():
                if not recursive:
                    raise IsADirectoryError(str(src))
                shutil.copytree(src, dst, dirs_exist_ok=overwrite, symlinks=True)
            else:
                shutil.copyfile(src, dst, follow_symlinks=False)

        await asyncio.to_thread(copy)

    async def canonicalize(self, path: str, *, target: str | None = None) -> str:
        return str(await asyncio.to_thread(self.path(path, target).resolve, strict=True))


class LocalProcess:
    def __init__(self, process: asyncio.subprocess.Process, capacity: int) -> None:
        self.process = process
        self.capacity = capacity
        self.output: deque[tuple[Literal["stdout", "stderr"], bytes]] = deque()
        self.retained = 0
        self.lost = 0
        self.changed = asyncio.Event()
        self.remaining = 2
        assert process.stdout is not None and process.stderr is not None
        self.readers = [
            asyncio.create_task(self.capture(process.stdout, "stdout")),
            asyncio.create_task(self.capture(process.stderr, "stderr")),
        ]
        self.close_task: asyncio.Task[None] | None = None

    async def capture(self, reader: asyncio.StreamReader, stream: Literal["stdout", "stderr"]) -> None:
        try:
            while data := await reader.read(min(16384, self.capacity)):
                self.output.append((stream, data))
                self.retained += len(data)
                while self.retained > self.capacity:
                    _, removed = self.output.popleft()
                    self.retained -= len(removed)
                    self.lost += len(removed)
                self.changed.set()
        finally:
            self.remaining -= 1
            self.changed.set()

    async def read(self, max_bytes: int) -> ProcessOutput:
        if max_bytes < 1:
            raise ValueError("Output bound must be positive")
        while not self.output and self.remaining:
            self.changed.clear()
            await self.changed.wait()
        lost, self.lost = self.lost, 0
        if not self.output:
            return ProcessOutput(eof=True, lost_bytes=lost)
        stream, data = self.output.popleft()
        result, rest = data[:max_bytes], data[max_bytes:]
        if rest:
            self.output.appendleft((stream, rest))
        self.retained -= len(result)
        return ProcessOutput(result, stream, not self.output and not self.remaining, lost)

    async def wait(self) -> int:
        # asyncio's wait may also wait for inherited output pipes to close.
        # Observe the child's returncode independently of those stream handles.
        while self.process.returncode is None:
            await asyncio.sleep(0.01)
        return self.process.returncode

    async def write(self, data: bytes) -> None:
        if self.process.stdin is None or self.process.stdin.is_closing():
            raise BrokenPipeError("Stdin is not open")
        self.process.stdin.write(data)
        await self.process.stdin.drain()

    async def close_stdin(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
            await self.process.stdin.wait_closed()

    async def signal(self, signal: Literal["interrupt", "terminate", "kill"]) -> None:
        signals = {"interrupt": 2, "terminate": 15, "kill": 9}
        try:
            os.killpg(self.process.pid, signals[signal])
        except ProcessLookupError:
            pass

    async def close(self) -> None:
        if self.close_task is None:
            self.close_task = asyncio.create_task(self._close())
        await asyncio.shield(self.close_task)

    async def _close(self) -> None:
        # Own the process group, including children retaining stdout after exit.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await self.process.wait()
        await asyncio.gather(*self.readers)
        try:
            await self.close_stdin()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Killing an owned child can discard pending stdin bytes.
        self.output.clear()


class LocalWorkspace:
    """Full host-account authority; only use with trusted peers and commands."""

    def __init__(self, cwd: Path, *, env: dict[str, str] | None = None, output_capacity: int = 1024 * 1024) -> None:
        if os.name != "posix":
            raise UnsupportedError("The reference process provider requires POSIX process groups")
        if output_capacity < 1:
            raise ValueError("Output capacity must be positive")
        self.cwd = cwd.resolve(strict=True)
        self.files = LocalFiles(self.cwd)
        self.env = dict(os.environ if env is None else env)
        self.output_capacity = output_capacity

    async def describe(self) -> WorkspaceInfo:
        return WorkspaceInfo(
            str(self.cwd), Shell("sh", "/bin/sh"), platform.system().lower(), home=self.env.get("HOME")
        )

    async def start_process(self, request: ProcessRequest) -> LocalProcess:
        if request.target is not None or request.tty or request.argv0 is not None:
            raise UnsupportedError("Reference provider does not support targets, TTY, or argv0 overrides")
        policy = request.environment
        if policy.inherit == "core":
            raise UnsupportedError("Native core environment inheritance is not portable")
        env = dict(self.env) if policy.inherit == "all" else {}

        def matches(name: str, patterns: tuple[str, ...]) -> bool:
            return any(fnmatch.fnmatchcase(name.upper(), pattern.upper()) for pattern in patterns)

        env = {key: value for key, value in env.items() if not matches(key, policy.exclude)}
        env.update(policy.assignments)
        if policy.include_only:
            env = {key: value for key, value in env.items() if matches(key, policy.include_only)}
        env.update(request.env)
        process = await asyncio.create_subprocess_exec(
            *request.argv,
            cwd=request.cwd or str(self.cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE if request.stdin else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        return LocalProcess(process, self.output_capacity)
