"""Application-hosted Codex file/process executor; one scope per connection."""

from __future__ import annotations

# pyright: reportPrivateUsage=false
import asyncio
import base64
import binascii
from collections import OrderedDict, deque
from collections.abc import AsyncIterable, Awaitable, Callable
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from ..._json import dumps, loads, obj, string
from ...errors import CleanupError, ProtocolError, UnsupportedError
from ...execution import _settle
from ...values import JSONValue
from ...workspace import EnvironmentPolicy, Process, ProcessRequest, ReadFile, Workspace, WorkspaceInfo
from . import _exec_wire as wire
from ._rpc import request_id
from ._wire import decode


def _base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _bytes(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ProtocolError("Invalid base64") from None


class _Paths:
    def __init__(self, info: WorkspaceInfo) -> None:
        self.windows = info.path_style == "windows"

    def path(self, uri: str) -> str:
        parsed = urlsplit(uri)
        if parsed.scheme != "file" or parsed.query or parsed.fragment:
            raise ProtocolError("Expected an absolute file URI")
        path = unquote(parsed.path, errors="strict")
        if self.windows:
            value = PureWindowsPath("//" + parsed.netloc + path if parsed.netloc else path.removeprefix("/"))
            if not value.is_absolute():
                raise ProtocolError("Expected an absolute Windows file URI")
            return str(value)
        if parsed.netloc not in ("", "localhost") or not path.startswith("/"):
            raise UnsupportedError("Non-local file URI authority on a POSIX target")
        return path

    def uri(self, path: str) -> str:
        value = PureWindowsPath(path) if self.windows else PurePosixPath(path)
        if not value.is_absolute():
            raise ProtocolError("Workspace must report absolute paths")
        normalized = value.as_posix()
        if self.windows and normalized.startswith("//"):
            return "file:" + quote(normalized, safe="/:")
        return "file://" + ("/" if self.windows else "") + quote(normalized, safe="/:")


def _unsandboxed(sandbox: dict[str, JSONValue] | None) -> None:
    if sandbox is None:
        return
    # Disabled is explicit native intent, not permission to discard a policy.
    if (
        sandbox.get("permissions") != {"type": "disabled"}
        or sandbox.get("windowsSandboxLevel", "disabled") != "disabled"
        or sandbox.get("useLegacyLandlock", False) is not False
        or set(sandbox) - {"permissions", "policyContext", "userHomeDir", "windowsSandboxLevel", "useLegacyLandlock"}
    ):
        raise UnsupportedError("This executor does not implement native sandbox policies")


class CodexExecBridge:
    """Borrow a Workspace without owning its listener, provider, or authority.

    Call serve once per authenticated connection. One bridge configuration may
    serve many connections concurrently; no handles are shared between them.
    The initial mode accepts explicit unsandboxed file/process operations only.
    """

    def __init__(
        self,
        workspace: Workspace,
        *,
        output_capacity: int = 1024 * 1024,
        handle_limit: int = 256,
        replay_limit: int = 256,
        request_limit: int = 256,
    ) -> None:
        if min(output_capacity, handle_limit, replay_limit, request_limit) < 1:
            raise ValueError("Capacities must be positive")
        self.workspace = workspace
        self.output_capacity = output_capacity
        self.handle_limit = handle_limit
        self.replay_limit = replay_limit
        self.request_limit = request_limit

    async def serve(self, incoming: AsyncIterable[str], send: Callable[[str], Awaitable[None]]) -> None:
        """Process complete text messages and settle connection-owned resources.

        Providers must settle admitted operations even on cancellation. Transport
        loss never retries a mutation; cleanup closes existing processes to
        unblock I/O, then settles admitted calls and their late returned handles.
        Cleanup failures are raised to the host.
        """
        connection = _Connection(self, send)
        try:
            await connection.serve(incoming)
        finally:
            connection.closing = True
            await _settle(asyncio.create_task(connection.close()))


class _Connection:
    def __init__(self, bridge: CodexExecBridge, send: Callable[[str], Awaitable[None]]) -> None:
        self.bridge = bridge
        self.workspace = bridge.workspace
        self.send_text = send
        self.closing = False
        self.initialized = False
        self.info: WorkspaceInfo | None = None
        self.paths: _Paths | None = None
        self.files: dict[str, ReadFile] = {}
        self.processes: dict[str, _Process] = {}
        self.completed: OrderedDict[str, _Process] = OrderedDict()
        # Retain only identity tombstones after replay eviction. Arbitrary native
        # IDs have no ordering from which we could infer that an old ID is stale.
        self.started: set[str] = set()
        self.requests: dict[int | str, asyncio.Task[None]] = {}
        self.write_lock = asyncio.Lock()
        self.operation_lock = asyncio.Lock()
        self.failure: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    async def send(self, message: dict[str, JSONValue]) -> None:
        async with self.write_lock:
            if not self.closing:
                await self.send_text(dumps(message))

    def failed(self, error: BaseException) -> None:
        if not self.failure.done():
            self.failure.set_exception(error)

    async def serve(self, incoming: AsyncIterable[str]) -> None:
        iterator = aiter(incoming)

        async def receive() -> str:
            return await anext(iterator)

        next_message: asyncio.Task[str] | None = None
        try:
            while True:
                next_message = asyncio.create_task(receive())
                done, _ = await asyncio.wait((next_message, self.failure), return_when=asyncio.FIRST_COMPLETED)
                if self.failure in done:
                    self.failure.result()
                try:
                    message = obj(loads(next_message.result()))
                except StopAsyncIteration:
                    break
                method = string(message.get("method"))
                if "id" not in message:
                    if method != "initialized":
                        raise ProtocolError("Unsupported executor notification")
                    continue
                identity = request_id(message["id"])
                if identity in self.requests or len(self.requests) >= self.bridge.request_limit:
                    raise ProtocolError("Duplicate or excessive in-flight executor requests")
                raw_params = message.get("params")
                params = {} if raw_params is None else obj(raw_params)
                task = asyncio.create_task(self.request(identity, method, params))
                self.requests[identity] = task
                task.add_done_callback(lambda _, key=identity: self.requests.pop(key, None))
        finally:
            if next_message is not None and not next_message.done():
                next_message.cancel()
                await asyncio.gather(next_message, return_exceptions=True)

    async def request(self, identity: int | str, method: str, params: dict[str, JSONValue]) -> None:
        try:
            try:
                # Pipe backpressure and long polls must not serialize termination.
                if method == "process/read":
                    result = await self.read_process(decode(wire.Read, params))
                elif method in ("process/write", "process/signal", "process/terminate"):
                    result = await self.dispatch(method, params)
                else:
                    async with self.operation_lock:
                        result = await self.dispatch(method, params)
            except Exception as error:
                code = -32603
                if isinstance(error, UnsupportedError):
                    code = -32601
                elif isinstance(error, ProtocolError):
                    code = -32602
                elif isinstance(error, FileNotFoundError):
                    code = -32004
                elif isinstance(error, PermissionError):
                    code = -32003
                # Provider exceptions can contain credentials and host paths.
                await self.send({"id": identity, "error": {"code": code, "message": type(error).__name__}})
            else:
                await self.send({"id": identity, "result": result})
                if method == "process/start":
                    self.processes[string(result["processId"])].ready.set()
        except BaseException as error:
            self.failed(error)

    def environment_info(self) -> dict[str, JSONValue]:
        assert self.info is not None and self.paths is not None
        return {
            "shell": {"name": self.info.shell.name, "path": self.info.shell.path},
            "cwd": self.paths.uri(self.info.cwd),
            "userHomeDir": self.paths.uri(self.info.home) if self.info.home else None,
            "platformOs": self.info.platform,
            "executorVersion": "0.0.0",
            "capabilities": {},
        }

    async def dispatch(self, method: str, params: dict[str, JSONValue]) -> dict[str, JSONValue]:
        if method == "initialize":
            initialization = decode(wire.Initialize, params)
            if self.initialized or initialization.resume_session_id is not None:
                raise UnsupportedError("Executor session recovery is not supported")
            self.info = await self.workspace.describe()
            self.paths = _Paths(self.info)
            info = self.environment_info()
            self.initialized = True
            return {"sessionId": uuid4().hex, "environmentInfo": info}
        if not self.initialized:
            raise ProtocolError("Initialize before executor operations")
        assert self.paths is not None
        if method in ("environment/info", "environment/status"):
            decode(wire.Params, params)
            return self.environment_info() if method == "environment/info" else {"status": "ready"}
        if method.startswith("fs/"):
            return await self.file_operation(method, params)
        if method == "process/start":
            return await self.start_process(decode(wire.Start, params))
        if method == "process/write":
            write = decode(wire.Write, params)
            process = self.process(write.process_id)
            if process is None:
                return {"status": "unknownProcess"}
            return await process.write(write)
        if method == "process/signal":
            signal = decode(wire.Signal, params)
            process = self.process(signal.process_id)
            if process is None:
                raise ProtocolError("Process is unknown or no longer retained")
            if process.handle is not None:
                await process.handle.signal(signal.signal)
            return {}
        if method == "process/terminate":
            terminate = decode(wire.Process, params)
            process = self.process(terminate.process_id)
            if process is None:
                return {"running": False}
            running = process.handle is not None and process.exit_code is None and process.failure is None
            if running and process.handle is not None:
                await process.handle.signal("kill")
            return {"running": running}
        raise UnsupportedError("Executor method not implemented")

    def process(self, identity: str) -> _Process | None:
        return self.processes.get(identity) or self.completed.get(identity)

    def retire(self, process: _Process) -> None:
        del self.processes[process.identity]
        self.completed[process.identity] = process
        while len(self.completed) > self.bridge.replay_limit:
            self.completed.popitem(last=False)

    async def start_process(self, start: wire.Start) -> dict[str, JSONValue]:
        assert self.paths is not None
        _unsandboxed(start.sandbox)
        if (
            start.shell_snapshot is not None
            or start.enforce_managed_network
            or start.managed_network is not None
            or start.network_proxy is not None
        ):
            raise UnsupportedError("Shell snapshots and managed networking are not supported")
        if start.process_id in self.started or len(self.processes) >= self.bridge.handle_limit:
            raise ProtocolError("Process identity reused or live process limit exceeded")
        policy = start.env_policy
        environment = EnvironmentPolicy()
        if policy is not None:
            # Native default secret exclusions are part of the requested policy.
            excludes = tuple(policy.exclude)
            if not policy.ignore_default_excludes:
                excludes = ("*KEY*", "*SECRET*", "*TOKEN*", *excludes)
            environment = EnvironmentPolicy(
                policy.inherit, excludes, tuple(policy.include_only), tuple(policy.set.items())
            )
        request = ProcessRequest(
            argv=tuple(start.argv),
            cwd=self.paths.path(start.cwd),
            env=tuple(start.env.items()),
            environment=environment,
            stdin=start.pipe_stdin,
            tty=start.tty,
            argv0=start.arg0,
        )
        # A provider error can follow side effects. The same native launch ID
        # cannot be dispatched again even if no handle or replay was returned.
        self.started.add(start.process_id)
        process = await self.workspace.start_process(request)
        owned = _Process(self, start.process_id, process)
        self.processes[start.process_id] = owned
        owned.pump = asyncio.create_task(owned.observe())
        return {"processId": start.process_id, "sandboxType": "none"}

    async def file_operation(self, method: str, params: dict[str, JSONValue]) -> dict[str, JSONValue]:
        assert self.paths is not None
        files = self.workspace.files
        if method == "fs/readBlock":
            block = decode(wire.ReadBlock, params)
            if block.len > self.bridge.output_capacity:
                raise UnsupportedError("File read block exceeds connection capacity")
            result = await self.files[block.handle_id].read(block.offset, block.len)
            if len(result.data) > block.len:
                raise ProtocolError("Provider exceeded file read bound")
            return {"chunk": _base64(result.data), "eof": result.eof}
        if method == "fs/close":
            handle = decode(wire.Handle, params)
            opened = self.files.get(handle.handle_id)
            if opened is not None:
                await opened.close()
                del self.files[handle.handle_id]
            return {}
        if method == "fs/copy":
            copy = decode(wire.Copy, params)
            _unsandboxed(copy.sandbox)
            await files.copy(
                self.paths.path(copy.source_path),
                self.paths.path(copy.destination_path),
                recursive=copy.recursive,
                overwrite=True,
            )
            return {}
        models: dict[str, type[wire.PathParams]] = {
            "fs/readFile": wire.FollowPath,
            "fs/writeFile": wire.WriteFile,
            "fs/getMetadata": wire.FollowPath,
            "fs/createDirectory": wire.Directory,
            "fs/remove": wire.Remove,
            "fs/canonicalize": wire.PathParams,
            "fs/readDirectory": wire.PathParams,
            "fs/open": wire.Open,
        }
        model = models.get(method)
        if model is None:
            raise UnsupportedError("Filesystem operation not implemented")
        request = decode(model, params)
        _unsandboxed(request.sandbox)
        path = self.paths.path(request.path)
        follow = request.follow_symlinks is not False if isinstance(request, wire.FollowPath) else True
        if method == "fs/readFile":
            return {"dataBase64": _base64(await files.read(path, follow_symlinks=follow))}
        if isinstance(request, wire.WriteFile):
            await files.write(path, _bytes(request.data_base64), follow_symlinks=follow)
        elif isinstance(request, wire.Remove):
            await files.remove(
                path,
                recursive=request.recursive is not False,
                missing_ok=request.force is not False,
                follow_symlinks=follow,
            )
        elif isinstance(request, wire.Directory):
            await files.create_directory(path, recursive=bool(request.recursive), follow_symlinks=follow)
        elif isinstance(request, wire.Open):
            if request.mode != "read":
                raise UnsupportedError("Writable streams not supported")
            if request.handle_id in self.files or len(self.files) >= self.bridge.handle_limit:
                raise ProtocolError("File identity reused or connection handle limit exceeded")
            self.files[request.handle_id] = await files.open_read(path)
            return {"handleId": request.handle_id}
        elif method == "fs/getMetadata":
            metadata = await files.metadata(path, follow_symlinks=follow)
            return {
                "isDirectory": metadata.kind == "directory",
                "isFile": metadata.kind == "file",
                "isSymlink": metadata.is_symlink or metadata.kind == "symlink",
                "size": metadata.size,
                "createdAtMs": metadata.created_at_ms or 0,
                "modifiedAtMs": metadata.modified_at_ms or 0,
            }
        elif method == "fs/canonicalize":
            return {"path": self.paths.uri(await files.canonicalize(path))}
        elif method == "fs/readDirectory":
            return {
                "entries": [
                    {"fileName": entry.name, "isDirectory": entry.kind == "directory", "isFile": entry.kind == "file"}
                    for entry in await files.list_directory(path)
                ]
            }
        return {}

    async def read_process(self, request: wire.Read) -> dict[str, JSONValue]:
        if not self.initialized:
            raise ProtocolError("Initialize before executor operations")
        process = self.process(request.process_id)
        if process is None:
            raise ProtocolError("Process is unknown or no longer retained")
        after = request.after_seq or 0
        if after >= process.seq and not process.closed and request.wait_ms and not self.closing:
            try:
                async with asyncio.timeout(min(request.wait_ms / 1000, 30)):
                    await process.changed.wait()
            except TimeoutError:
                pass
        if after < process.dropped_through:
            raise ProtocolError("Requested process output has been evicted")
        chunks: list[JSONValue] = []
        size = 0
        next_seq = after
        for seq, stream, data in process.output:
            if seq <= after:
                continue
            if chunks and size + len(data) > (request.max_bytes or self.bridge.output_capacity):
                break
            chunks.append({"seq": seq, "stream": stream, "chunk": _base64(data)})
            size += len(data)
            next_seq = seq
        all_read = not process.output or next_seq >= process.output[-1][0]
        return {
            "chunks": chunks,
            "nextSeq": process.seq if all_read else next_seq,
            "exited": process.exit_code is not None and all_read,
            "exitCode": process.exit_code if all_read else None,
            "closed": process.closed and all_read,
            "failure": process.failure,
            "sandboxDenied": False,
        }

    async def close(self) -> None:
        errors: list[Exception] = []

        async def close_handle(handle: ReadFile | _Process) -> None:
            try:
                await handle.close()
            except Exception as error:
                errors.append(error)

        # Settle existing processes first: their close unblocks admitted stdin
        # writes. Keep waiting for late launch/open results, then close those too.
        existing = set(self.processes.values())
        await asyncio.gather(*(close_handle(process) for process in existing))
        await asyncio.gather(*tuple(self.requests.values()), return_exceptions=True)
        await asyncio.gather(
            *(close_handle(handle) for handle in self.files.values()),
            *(close_handle(process) for process in self.processes.values() if process not in existing),
        )
        if self.failure.done():
            self.failure.exception()
        if errors:
            raise CleanupError("Executor connection could not settle all owned handles") from ExceptionGroup(
                "Handle cleanup", errors
            )


class _Process:
    def __init__(self, connection: _Connection, identity: str, handle: Process) -> None:
        self.connection = connection
        self.identity = identity
        self.handle: Process | None = handle
        self.release_task: asyncio.Task[None] | None = None
        self.output: deque[tuple[int, str, bytes]] = deque()
        self.bytes = 0
        self.seq = 0
        self.dropped_through = 0
        self.exit_code: int | None = None
        self.failure: str | None = None
        self.closed = False
        self.changed = asyncio.Event()
        self.writes: set[str] = set()
        self.stdin_lock = asyncio.Lock()
        self.ready = asyncio.Event()
        self.pump: asyncio.Task[None] | None = None

    async def write(self, request: wire.Write) -> dict[str, JSONValue]:
        async with self.stdin_lock:
            data = _bytes(request.chunk)
            if request.write_id in self.writes:
                return {"status": "accepted"}
            if self.connection.closing or self.handle is None or self.exit_code is not None:
                return {"status": "stdinClosed"}
            try:
                await self.handle.write(data)
            except (BrokenPipeError, ConnectionResetError):
                return {"status": "stdinClosed"}
            self.writes.add(request.write_id)
            return {"status": "accepted"}

    async def close(self) -> None:
        self.changed.set()
        if self.pump is not None:
            self.pump.cancel()
            await asyncio.gather(self.pump, return_exceptions=True)
        await self.release()

    async def release(self) -> None:
        if self.release_task is None:
            assert self.handle is not None
            self.release_task = asyncio.create_task(self.handle.close())
        # Natural completion and connection cleanup share exactly one release.
        # Cancelling the output pump must not abandon a close already in flight.
        await asyncio.shield(self.release_task)
        self.handle = None

    async def notify(self, method: str, fields: dict[str, JSONValue]) -> None:
        self.seq += 1
        self.changed.set()
        self.changed = asyncio.Event()
        await self.connection.send(
            {"method": method, "params": {"processId": self.identity, "seq": self.seq, **fields}}
        )

    async def observe(self) -> None:
        try:
            await self.ready.wait()
            handle = self.handle
            assert handle is not None
            while True:
                block = await handle.read(min(16384, self.connection.bridge.output_capacity))
                if block.lost_bytes:
                    raise ProtocolError("Provider process output was lost")
                if len(block.data) > min(16384, self.connection.bridge.output_capacity):
                    raise ProtocolError("Provider exceeded process output bound")
                if block.data:
                    self.output.append((self.seq + 1, block.stream, block.data))
                    self.bytes += len(block.data)
                    while self.bytes > self.connection.bridge.output_capacity:
                        seq, _, data = self.output.popleft()
                        self.bytes -= len(data)
                        self.dropped_through = seq
                    await self.notify("process/output", {"stream": block.stream, "chunk": _base64(block.data)})
                if block.eof:
                    break
            # Codex treats exit as final output: drain before announcing it.
            self.exit_code = await handle.wait()
            await self.release()
            await self.notify("process/exited", {"exitCode": self.exit_code})
            self.closed = True
            await self.notify("process/closed", {})
            self.connection.retire(self)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = type(error).__name__
            self.closed = True
            self.changed.set()
            # No native notification represents output loss faithfully. Fail the
            # connection rather than synthesizing an exit code or complete bytes.
            self.connection.failed(error)
