"""Borrowed target I/O, independent of native protocols and transport hosting.

Providers own authority and path resolution. Raise ordinary typed OSError
subclasses for filesystem failures and UnsupportedError before unsupported
operations have effects. A handle stays on its original target until closed.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class Shell:
    name: str
    path: str


@dataclass(frozen=True, slots=True)
class WorkspaceInfo:
    cwd: str
    shell: Shell
    platform: str
    path_style: Literal["posix", "windows"] = "posix"
    home: str | None = None


@dataclass(frozen=True, slots=True)
class FileInfo:
    kind: Literal["file", "directory", "symlink", "other"]
    size: int
    modified_at_ms: int | None = None
    created_at_ms: int | None = None
    is_symlink: bool = False


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    name: str
    kind: Literal["file", "directory", "symlink", "other"]


@dataclass(frozen=True, slots=True)
class FileBlock:
    data: bytes
    eof: bool


class ReadFile(Protocol):
    """One opened resource, not a path reopened for each read."""

    async def read(self, offset: int, max_bytes: int) -> FileBlock: ...
    async def close(self) -> None: ...


class FileSystem(Protocol):
    async def read(self, path: str, *, follow_symlinks: bool = True, target: str | None = None) -> bytes: ...
    async def write(
        self, path: str, data: bytes, *, follow_symlinks: bool = True, target: str | None = None
    ) -> None: ...
    async def open_read(self, path: str, *, target: str | None = None) -> ReadFile: ...
    async def metadata(self, path: str, *, follow_symlinks: bool = True, target: str | None = None) -> FileInfo: ...
    async def list_directory(self, path: str, *, target: str | None = None) -> tuple[DirectoryEntry, ...]: ...
    async def create_directory(
        self, path: str, *, recursive: bool = False, follow_symlinks: bool = True, target: str | None = None
    ) -> None: ...
    async def remove(
        self,
        path: str,
        *,
        recursive: bool = False,
        missing_ok: bool = False,
        follow_symlinks: bool = True,
        target: str | None = None,
    ) -> None: ...
    async def copy(
        self,
        source: str,
        destination: str,
        *,
        recursive: bool = False,
        overwrite: bool = False,
        target: str | None = None,
    ) -> None: ...
    async def canonicalize(self, path: str, *, target: str | None = None) -> str: ...


@dataclass(frozen=True, slots=True)
class EnvironmentPolicy:
    """Construct against the target's base environment, then apply request.env.

    Filtering patterns use case-insensitive glob matching. Native adapters must
    reject policies they cannot faithfully express; providers do the same.
    """

    inherit: Literal["all", "none", "core"] = "all"
    exclude: tuple[str, ...] = ()
    include_only: tuple[str, ...] = ()
    assignments: tuple[tuple[str, str], ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    argv: tuple[str, ...]
    cwd: str | None = None
    env: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    environment: EnvironmentPolicy = EnvironmentPolicy()
    stdin: bool = False
    tty: bool = False
    argv0: str | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("Process argv cannot be empty")


@dataclass(frozen=True, slots=True)
class ProcessOutput:
    """A bounded read from the handle's single consuming output stream.

    eof closes all output streams, independently of process exit. lost_bytes
    reports discarded bytes before this block; consumers must not hide that gap.
    """

    data: bytes = b""
    stream: Literal["stdout", "stderr", "pty"] = "stdout"
    eof: bool = False
    lost_bytes: int = 0


class Process(Protocol):
    async def read(self, max_bytes: int) -> ProcessOutput:
        """Wait for bytes or output EOF. Never return more than max_bytes."""
        ...

    async def wait(self) -> int:
        """Observe exit independently of output drainage."""
        ...

    async def write(self, data: bytes) -> None: ...
    async def close_stdin(self) -> None: ...
    async def signal(self, signal: Literal["interrupt", "terminate", "kill"]) -> None: ...
    async def close(self) -> None:
        """Settle the command, unblock pending I/O, and release its handle; idempotent."""
        ...


class Workspace(Protocol):
    @property
    def files(self) -> FileSystem: ...
    async def describe(self) -> WorkspaceInfo: ...
    async def start_process(self, request: ProcessRequest) -> Process: ...
