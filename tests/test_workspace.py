"""Real filesystem/process provider and controlled executor-wire boundaries."""

import asyncio
import base64
import json
from contextlib import asynccontextmanager

import pytest

from examples.local_workspace import LocalWorkspace
from ohkit import ProtocolError
from ohkit.backends.codex import CodexExecBridge
from ohkit.workspace import EnvironmentPolicy, ProcessOutput, ProcessRequest


class Client:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.notifications = []
        self.number = 0

    async def messages(self):
        while (message := await self.incoming.get()) is not None:
            yield json.dumps(message)

    async def send(self, text):
        await self.outgoing.put(json.loads(text))

    async def call(self, method, **params):
        self.number += 1
        await self.incoming.put({"id": self.number, "method": method, "params": params})
        async with asyncio.timeout(5):
            while True:
                response = await self.outgoing.get()
                if "id" in response:
                    assert response["id"] == self.number
                    return response
                self.notifications.append(response)

    async def initialize(self):
        result = await self.call("initialize", clientName="test")
        assert "result" in result, result
        return result["result"]


@asynccontextmanager
async def client(bridge):
    peer = Client()
    task = asyncio.create_task(bridge.serve(peer.messages(), peer.send))
    try:
        await peer.initialize()
        yield peer, task
    finally:
        await peer.incoming.put(None)
        await task


def test_file_bytes_metadata_handles_canonicalize_and_mutations(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        bridge = CodexExecBridge(workspace)
        path = tmp_path / "data"
        async with client(bridge) as (peer, _):
            assert (await peer.call("fs/readFile", path=path.as_uri()))["error"]["code"] == -32004
            data = b"\xff\x00not text"
            assert "result" in await peer.call(
                "fs/writeFile", path=path.as_uri(), dataBase64=base64.b64encode(data).decode()
            )
            assert path.read_bytes() == data
            result = (await peer.call("fs/getMetadata", path=path.as_uri()))["result"]
            assert result["size"] == len(data) and result["isFile"]
            assert result["modifiedAtMs"] == path.stat().st_mtime_ns // 1_000_000
            assert result["createdAtMs"] == 0  # Native unavailable sentinel, never POSIX ctime.
            await peer.call("fs/open", path=path.as_uri(), handleId="read")
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"new")
            replacement.replace(path)
            result = (await peer.call("fs/readBlock", handleId="read", offset=0, len=3))["result"]
            assert base64.b64decode(result["chunk"]) == data[:3] and not result["eof"]
            await peer.call("fs/close", handleId="read")
            link = tmp_path / "link"
            link.symlink_to(path)
            result = (await peer.call("fs/getMetadata", path=link.as_uri()))["result"]
            assert result["isFile"] and result["isSymlink"]
            result = (await peer.call("fs/getMetadata", path=link.as_uri(), followSymlinks=False))["result"]
            assert not result["isFile"] and result["isSymlink"]
            assert (await peer.call("fs/canonicalize", path=link.as_uri()))["result"]["path"] == path.as_uri()
            directory = tmp_path / "sub" / "nested"
            await peer.call("fs/createDirectory", path=directory.as_uri(), recursive=True)
            await peer.call(
                "fs/copy", sourcePath=path.as_uri(), destinationPath=(directory / "copy").as_uri(), recursive=False
            )
            assert (directory / "copy").read_bytes() == b"new"
            entries = (await peer.call("fs/readDirectory", path=directory.as_uri()))["result"]["entries"]
            assert entries == [{"fileName": "copy", "isDirectory": False, "isFile": True}]
            assert "result" in await peer.call("fs/remove", path=(tmp_path / "sub").as_uri())
            assert not directory.exists()
            await peer.call("fs/remove", path=link.as_uri())
            assert path.exists() and not link.exists()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "extra",
    [
        {"sandbox": {"permissions": {"type": "readOnly"}}},
        {"enforceManagedNetwork": True},
        {"shellSnapshot": {"scopeId": "x"}},
        {"networkProxy": {"x": True}},
        {"unknownRestriction": True},
        {"tty": True},
        {"shellSnapshot": {}},
        {"managedNetwork": {}},
        {"networkProxy": {}},
        {"arg0": "custom"},
    ],
)
def test_unsupported_process_requirements_have_no_effect(tmp_path, extra):
    async def scenario():
        path = tmp_path / "effect"
        async with client(CodexExecBridge(LocalWorkspace(tmp_path, env={}))) as (peer, _):
            result = await peer.call(
                "process/start",
                **{
                    "processId": "p",
                    "argv": ["/bin/sh", "-c", f"touch {path}"],
                    "cwd": tmp_path.as_uri(),
                    "env": {},
                    "tty": False,
                    **extra,
                },
            )
            assert "error" in result
            assert not path.exists()

    asyncio.run(scenario())


def test_real_process_env_stdin_output_eof_and_connection_isolation(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={"KEEP": "yes", "DROP": "no"})
        bridge = CodexExecBridge(workspace)
        async with client(bridge) as (first, _), client(bridge) as (second, _):
            params = {
                "processId": "same",
                "argv": ["/bin/sh", "-c", 'read x; printf "%s:%s:%s" "$x" "$KEEP" "$DROP"'],
                "cwd": tmp_path.as_uri(),
                "env": {},
                "tty": False,
                "pipeStdin": True,
                "envPolicy": {
                    "inherit": "all",
                    "ignoreDefaultExcludes": True,
                    "exclude": ["drop"],
                    "set": {},
                    "includeOnly": [],
                },
            }
            assert "result" in await first.call("process/start", **params)
            assert "result" in await second.call("process/start", **params)
            await first.call("process/terminate", processId="same")
            await second.call(
                "process/write", processId="same", writeId="one", chunk=base64.b64encode(b"hello\n").decode()
            )
            chunks = []
            cursor = 0
            while True:
                result = (await second.call("process/read", processId="same", afterSeq=cursor, waitMs=500))["result"]
                chunks.extend(base64.b64decode(chunk["chunk"]) for chunk in result["chunks"])
                cursor = result["nextSeq"]
                if result["closed"]:
                    assert result["exitCode"] == 0
                    break
            assert b"".join(chunks) == b"hello:yes:"
            methods = [n["method"] for n in second.notifications]
            if "process/exited" in methods:
                assert methods.index("process/output") < methods.index("process/exited")
        # Shared provider remains borrowed and usable.
        assert (await workspace.describe()).cwd == str(tmp_path)

    asyncio.run(scenario())


class ControlledProcess:
    def __init__(self):
        self.output = asyncio.Queue()
        self.exited = asyncio.Event()
        self.closed = False
        self.written = []

    async def read(self, max_bytes):
        return await self.output.get()

    async def wait(self):
        await self.exited.wait()
        return 0

    async def write(self, data):
        self.written.append(data)

    async def close_stdin(self):
        pass

    async def signal(self, signal):
        self.exited.set()

    async def close(self):
        self.closed = True


class ControlledWorkspace(LocalWorkspace):
    def __init__(self, root):
        super().__init__(root, env={})
        self.process = ControlledProcess()
        self.launch_entered = asyncio.Event()
        self.launch_release = asyncio.Event()
        self.launch_release.set()
        self.requests = []

    async def start_process(self, request):
        self.requests.append(request)
        self.launch_entered.set()
        await self.launch_release.wait()
        return self.process


def start_params(root):
    return {"processId": "p", "argv": ["echo", "a b"], "cwd": root.as_uri(), "env": {}, "tty": False}


def test_exit_is_not_published_before_final_output_and_write_is_deduplicated(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        async with client(CodexExecBridge(workspace)) as (peer, _):
            await peer.call("process/start", **start_params(tmp_path))
            workspace.process.exited.set()
            await workspace.process.output.put(ProcessOutput(b"first"))
            result = (await peer.call("process/read", processId="p", waitMs=100))["result"]
            assert not result["exited"]
            await peer.call("process/write", processId="p", writeId="w", chunk="YQ==")
            await peer.call("process/write", processId="p", writeId="w", chunk="Yg==")
            assert workspace.process.written == [b"a"]
            await workspace.process.output.put(ProcessOutput(b"last", eof=True))
            result = (await peer.call("process/read", processId="p", afterSeq=1, waitMs=100))["result"]
            assert result["exited"] and result["exitCode"] == 0
            assert base64.b64decode(result["chunks"][-1]["chunk"]) == b"last"
        assert workspace.process.closed

    asyncio.run(scenario())


def test_provider_gap_fails_connection_instead_of_fabricating_completion(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        with pytest.raises(ProtocolError, match="output was lost"):
            async with client(CodexExecBridge(workspace)) as (peer, task):
                await peer.call("process/start", **start_params(tmp_path))
                await workspace.process.output.put(ProcessOutput(b"suffix", lost_bytes=10, eof=True))
                await task
        assert workspace.process.closed
        assert not any(n["method"] == "process/exited" for n in peer.notifications)

    asyncio.run(scenario())


def test_retention_gap_is_explicit_and_output_read_is_bounded(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        async with client(CodexExecBridge(workspace, output_capacity=4)) as (peer, _):
            await peer.call("process/start", **start_params(tmp_path))
            await workspace.process.output.put(ProcessOutput(b"aaaa"))
            await peer.call("process/read", processId="p", waitMs=100)
            await workspace.process.output.put(ProcessOutput(b"bbbb"))
            await peer.call("process/read", processId="p", afterSeq=1, waitMs=100)
            result = await peer.call("process/read", processId="p", afterSeq=0)
            assert result["error"]["code"] == -32602

    asyncio.run(scenario())


def test_cancel_during_launch_waits_for_handle_then_closes_it(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        workspace.launch_release.clear()
        peer = Client()
        task = asyncio.create_task(CodexExecBridge(workspace).serve(peer.messages(), peer.send))
        await peer.initialize()
        await peer.incoming.put({"id": 2, "method": "process/start", "params": start_params(tmp_path)})
        await workspace.launch_entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        workspace.launch_release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert workspace.process.closed

    asyncio.run(scenario())


def test_provider_output_loss_and_close_stdin(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={}, output_capacity=4)
        process = await workspace.start_process(
            ProcessRequest(("/bin/cat",), stdin=True, environment=EnvironmentPolicy("none"))
        )
        await process.write(b"abcdefgh")
        await process.close_stdin()
        await process.wait()
        result = await process.read(4)
        assert result.lost_bytes == 4 and result.data == b"efgh"
        await process.close()

    asyncio.run(scenario())


def test_disconnect_settles_only_its_connection_and_wakes_long_poll(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        bridge = CodexExecBridge(workspace)
        first = Client()
        first_task = asyncio.create_task(bridge.serve(first.messages(), first.send))
        await first.initialize()
        async with client(bridge) as (second, _):
            params = {**start_params(tmp_path), "argv": ["/bin/cat"], "pipeStdin": True}
            await first.call("process/start", **params)
            await second.call("process/start", **params)
            await first.incoming.put({"id": 3, "method": "process/read", "params": {"processId": "p", "waitMs": 30000}})
            await first.incoming.put(None)
            async with asyncio.timeout(2):
                await first_task
            assert "result" in await second.call("process/write", processId="p", writeId="w", chunk="aGVsbG8K")
            result = (await second.call("process/read", processId="p", waitMs=1000))["result"]
            assert base64.b64decode(result["chunks"][0]["chunk"]) == b"hello\n"
            assert not result["closed"]

    asyncio.run(scenario())


def test_late_file_handle_is_closed_and_cleanup_failures_reach_host(tmp_path):
    from ohkit import CleanupError

    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        entered, release = asyncio.Event(), asyncio.Event()
        closed = []

        class Files:
            async def open_read(self, path):
                entered.set()
                await release.wait()
                return self

            async def close(self):
                closed.append(True)
                raise OSError("cleanup failed")

        workspace.files = Files()
        peer = Client()
        task = asyncio.create_task(CodexExecBridge(workspace).serve(peer.messages(), peer.send))
        await peer.initialize()
        await peer.incoming.put({"id": 2, "method": "fs/open", "params": {"path": tmp_path.as_uri(), "handleId": "f"}})
        await entered.wait()
        await peer.incoming.put(None)
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(CleanupError):
            await task
        assert closed == [True]

    asyncio.run(scenario())


def test_copy_directory_symlink_preserves_link_and_existing_destination(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        directory = tmp_path / "directory"
        directory.mkdir()
        (directory / "file").write_bytes(b"data")
        source, destination = tmp_path / "source", tmp_path / "destination"
        source.symlink_to(directory)
        await workspace.files.copy(str(source), str(destination), recursive=False, overwrite=True)
        assert destination.is_symlink() and destination.readlink() == directory
        with pytest.raises(FileExistsError):
            await workspace.files.copy(str(source), str(destination), recursive=True, overwrite=True)
        assert (directory / "file").read_bytes() == b"data"

    asyncio.run(scenario())


@pytest.mark.parametrize("uri", ["file:relative", "file:///relative", "file:///C:relative"])
def test_windows_file_uri_must_be_absolute(tmp_path, uri):
    from dataclasses import replace

    async def scenario():
        class WindowsWorkspace(ControlledWorkspace):
            async def describe(self):
                return replace(await super().describe(), cwd="C:\\project", path_style="windows")

        workspace = WindowsWorkspace(tmp_path)
        async with client(CodexExecBridge(workspace)) as (peer, _):
            result = await peer.call("process/start", **{**start_params(tmp_path), "cwd": uri})
            assert result["error"]["code"] == -32602
            assert not workspace.requests

    asyncio.run(scenario())


def test_application_host_authorizes_exact_route_before_workspace_access(tmp_path):
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve
    from websockets.exceptions import InvalidStatus

    from examples.hosted_workspace import ExecutorHost

    async def scenario():
        root_a, root_b = tmp_path / "a", tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        host = ExecutorHost(
            {
                "/a": ("token-a", LocalWorkspace(root_a, env={})),
                "/b": ("token-b", LocalWorkspace(root_b, env={})),
            }
        )
        async with serve(host.handle, "127.0.0.1", 0, process_request=host.authorize) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            for path, token, status in [("/unknown", "token-a", 404), ("/a", "token-b", 401), ("/a", "", 401)]:
                with pytest.raises(InvalidStatus) as error:
                    async with connect(url + path, additional_headers={"Authorization": "Bearer " + token}):
                        pytest.fail("Unauthorized handshake accepted")
                assert error.value.response.status_code == status
            for path, token, root in [("/a", "token-a", root_a), ("/b", "token-b", root_b)]:
                async with connect(url + path, additional_headers={"Authorization": "Bearer " + token}) as connection:
                    await connection.send(
                        json.dumps({"id": 1, "method": "initialize", "params": {"clientName": "test"}})
                    )
                    result = json.loads(await connection.recv())["result"]
                    assert result["environmentInfo"]["cwd"] == root.as_uri()

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["terminate", "disconnect", "cancel"])
def test_blocked_stdin_does_not_block_termination_or_cleanup(tmp_path, action, monkeypatch):
    from examples.local_workspace import LocalProcess

    async def scenario():
        writing = asyncio.Event()
        handles = []
        original_write = LocalProcess.write

        async def write(handle, data):
            writing.set()
            await original_write(handle, data)

        monkeypatch.setattr(LocalProcess, "write", write)

        class Workspace(LocalWorkspace):
            async def start_process(self, request):
                handle = await super().start_process(request)
                handles.append(handle)
                return handle

        peer = Client()
        task = asyncio.create_task(CodexExecBridge(Workspace(tmp_path, env={})).serve(peer.messages(), peer.send))
        try:
            await peer.initialize()
            await peer.call(
                "process/start", **{**start_params(tmp_path), "argv": ["/bin/sleep", "60"], "pipeStdin": True}
            )
            await peer.incoming.put(
                {
                    "id": 3,
                    "method": "process/write",
                    "params": {
                        "processId": "p",
                        "writeId": "blocked",
                        "chunk": base64.b64encode(b"x" * 262144).decode(),
                    },
                }
            )
            await writing.wait()
            if action == "terminate":
                await peer.incoming.put({"id": 4, "method": "process/terminate", "params": {"processId": "p"}})
                async with asyncio.timeout(2):
                    while (response := await peer.outgoing.get()).get("id") != 4:
                        pass
                assert response["result"]["running"]
            if action == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    async with asyncio.timeout(2):
                        await asyncio.shield(task)
            else:
                await peer.incoming.put(None)
                async with asyncio.timeout(2):
                    await asyncio.shield(task)
            assert handles[0].process.returncode is not None
        finally:
            # A failing regression must not leave a real sleeping command or a
            # shielded connection cleanup behind.
            for handle in handles:
                await handle.signal("kill")
            await peer.incoming.put(None)
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_process_wait_observes_exit_before_inherited_output_closes(tmp_path):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        handle = await workspace.start_process(
            ProcessRequest(
                ("/bin/sh", "-c", "read line; sleep 60 & exit 7"),
                stdin=True,
            )
        )
        try:
            waiting = asyncio.create_task(handle.wait())
            await asyncio.sleep(0)  # Enter wait before releasing the child.
            await handle.write(b"go\n")
            async with asyncio.timeout(2):
                assert await waiting == 7
            assert handle.remaining == 2  # Background child still owns both pipes.
        finally:
            await handle.close()
        assert (await handle.read(1)).eof

    asyncio.run(scenario())


@pytest.mark.parametrize("recursive", [False, True])
@pytest.mark.parametrize("destination_kind", ["file_link", "dangling_link", "directory_link"])
def test_copy_rejects_destination_symlinks_without_modifying_referents(tmp_path, recursive, destination_kind):
    async def scenario():
        workspace = LocalWorkspace(tmp_path, env={})
        source, destination, referent = (tmp_path / name for name in ("source", "destination", "referent"))
        if destination_kind == "directory_link":
            referent.mkdir()
            (referent / "data").write_bytes(b"original")
        elif destination_kind == "file_link":
            referent.write_bytes(b"original")
        if recursive:
            source.mkdir()
            destination.mkdir()
            source = source / "entry"
            destination = destination / "entry"
        if destination_kind == "directory_link":
            source.mkdir()
            (source / "data").write_bytes(b"replacement")
        else:
            source.write_bytes(b"replacement")
        destination.symlink_to(referent)
        with pytest.raises(FileExistsError):
            await workspace.files.copy(
                "source", "destination", recursive=recursive or destination_kind == "directory_link", overwrite=True
            )
        assert destination.is_symlink()
        if destination_kind == "dangling_link":
            assert not referent.exists()
        else:
            assert (referent / "data" if referent.is_dir() else referent).read_bytes() == b"original"

    asyncio.run(scenario())


@pytest.mark.parametrize("cwd", [None, ".", "nested", "absolute"])
def test_process_cwd_uses_the_same_namespace_as_files(tmp_path, cwd):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        nested = root / "nested"
        nested.mkdir()
        absolute = tmp_path / "elsewhere"
        absolute.mkdir()
        workspace = LocalWorkspace(root, env={})
        requested = str(absolute) if cwd == "absolute" else cwd
        expected = absolute if cwd == "absolute" else nested if cwd == "nested" else root
        (expected / "marker").write_bytes(b"target")
        process = await workspace.start_process(ProcessRequest(("/bin/pwd",), cwd=requested))
        try:
            output = b""
            while True:
                block = await process.read(4096)
                output += block.data
                if block.eof:
                    break
            assert output.decode().strip() == str(expected)
            assert await workspace.files.read(str(expected / "marker")) == b"target"
        finally:
            await process.close()

    asyncio.run(scenario())


async def completed(peer, identity):
    async with asyncio.timeout(2):
        while True:
            result = (await peer.call("process/read", processId=identity, waitMs=100))["result"]
            if result["closed"]:
                return result


def test_completed_processes_release_resources_and_have_separate_bounded_replay(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        handles = []
        async with client(CodexExecBridge(workspace, handle_limit=1, replay_limit=2)) as (peer, _):
            for index in range(5):
                handle = workspace.process = ControlledProcess()
                handles.append(handle)
                identity = f"p{index}"
                assert "result" in await peer.call("process/start", **{**start_params(tmp_path), "processId": identity})
                handle.exited.set()
                await handle.output.put(ProcessOutput(str(index).encode(), eof=True))
                result = await completed(peer, identity)
                assert result["exitCode"] == 0 and handle.closed
            # The last two records survive without retaining their provider handles.
            for index in (3, 4):
                result = await completed(peer, f"p{index}")
                assert base64.b64decode(result["chunks"][0]["chunk"]) == str(index).encode()
            assert "error" in await peer.call("process/read", processId="p0")
            assert "error" in await peer.call("process/start", **{**start_params(tmp_path), "processId": "p0"})
            assert len(workspace.requests) == 5  # Eviction never makes a launch safe to replay.
            assert (await peer.call("process/write", processId="p0", writeId="late", chunk="YQ=="))["result"] == {
                "status": "unknownProcess"
            }
            assert (await peer.call("process/write", processId="p4", writeId="late", chunk="YQ=="))["result"] == {
                "status": "stdinClosed"
            }
            assert (await peer.call("process/terminate", processId="p4"))["result"] == {"running": False}
        assert all(handle.closed for handle in handles)

    asyncio.run(scenario())


def test_live_process_limit_and_write_deduplication_are_not_lifetime_command_quotas(tmp_path):
    async def scenario():
        workspace = ControlledWorkspace(tmp_path)
        async with client(CodexExecBridge(workspace, handle_limit=1)) as (peer, _):
            assert "result" in await peer.call("process/start", **start_params(tmp_path))
            assert "error" in await peer.call("process/start", **{**start_params(tmp_path), "processId": "second"})
            for index in range(300):
                response = await peer.call("process/write", processId="p", writeId=str(index), chunk="YQ==")
                assert response["result"] == {"status": "accepted"}
            response = await peer.call("process/write", processId="p", writeId="0", chunk="Yg==")
            assert response["result"] == {"status": "accepted"}
            assert workspace.process.written == [b"a"] * 300
            workspace.process.exited.set()
            await workspace.process.output.put(ProcessOutput(eof=True))
            await completed(peer, "p")
            response = await peer.call("process/write", processId="p", writeId="0", chunk="Yg==")
            assert response["result"] == {"status": "accepted"}
            workspace.process = ControlledProcess()
            assert "result" in await peer.call("process/start", **{**start_params(tmp_path), "processId": "second"})

    asyncio.run(scenario())


def test_cancellation_during_natural_release_waits_for_one_close(tmp_path):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        closes = []

        class SlowClose(ControlledProcess):
            async def close(self):
                closes.append(True)
                entered.set()
                await release.wait()
                await super().close()

        workspace = ControlledWorkspace(tmp_path)
        workspace.process = SlowClose()
        peer = Client()
        task = asyncio.create_task(CodexExecBridge(workspace).serve(peer.messages(), peer.send))
        await peer.initialize()
        await peer.call("process/start", **start_params(tmp_path))
        workspace.process.exited.set()
        await workspace.process.output.put(ProcessOutput(eof=True))
        try:
            async with asyncio.timeout(2):
                await entered.wait()
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not workspace.process.closed
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert closes == [True] and workspace.process.closed
        finally:
            release.set()
            await peer.incoming.put(None)
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_natural_process_release_failure_reaches_host_without_closed_notification(tmp_path):
    from ohkit import CleanupError

    async def scenario():
        closes = []

        class BrokenClose(ControlledProcess):
            async def close(self):
                closes.append(True)
                raise OSError("provider cleanup failed")

        workspace = ControlledWorkspace(tmp_path)
        workspace.process = BrokenClose()
        peer = Client()
        task = asyncio.create_task(CodexExecBridge(workspace).serve(peer.messages(), peer.send))
        await peer.initialize()
        await peer.call("process/start", **start_params(tmp_path))
        workspace.process.exited.set()
        await workspace.process.output.put(ProcessOutput(eof=True))
        with pytest.raises(CleanupError):
            async with asyncio.timeout(2):
                await task
        assert closes == [True]
        frames = []
        while not peer.outgoing.empty():
            frames.append(peer.outgoing.get_nowait())
        assert not any(frame.get("method") == "process/closed" for frame in frames)

    asyncio.run(scenario())


def test_uncertain_provider_launch_cannot_be_replayed_with_the_same_id(tmp_path):
    async def scenario():
        effects = []

        class Workspace(ControlledWorkspace):
            async def start_process(self, request):
                effects.append(request)
                raise OSError("acknowledgement lost after launch")

        async with client(CodexExecBridge(Workspace(tmp_path))) as (peer, _):
            for _ in range(2):
                assert "error" in await peer.call("process/start", **start_params(tmp_path))
            assert len(effects) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("overwrite", [False, True])
def test_recursive_copy_preserves_executable_mode(tmp_path, overwrite):
    async def scenario():
        source, destination = tmp_path / "source", tmp_path / "destination"
        (source / "bin").mkdir(parents=True)
        executable = source / "bin" / "command"
        executable.write_bytes(b"#!/bin/sh\nprintf copied")
        executable.chmod(0o755)
        if overwrite:
            (destination / "bin").mkdir(parents=True)
            (destination / "bin" / "command").write_bytes(b"old")
            (destination / "bin" / "command").chmod(0o600)
        workspace = LocalWorkspace(tmp_path, env={})
        await workspace.files.copy("source", "destination", recursive=True, overwrite=overwrite)
        copied = destination / "bin" / "command"
        assert copied.stat().st_mode & 0o777 == 0o755
        assert copied.stat().st_mtime_ns == executable.stat().st_mtime_ns
        process = await workspace.start_process(ProcessRequest((str(copied),)))
        try:
            assert await process.wait() == 0
            assert (await process.read(100)).data == b"copied"
        finally:
            await process.close()

    asyncio.run(scenario())


def test_copy_merge_preserves_source_links_and_overwrites_regular_files(tmp_path):
    async def scenario():
        source, destination = tmp_path / "source", tmp_path / "destination"
        source.mkdir()
        destination.mkdir()
        (source / "file").write_bytes(b"new")
        (source / "link").symlink_to("file")
        (destination / "file").write_bytes(b"old")
        (destination / "keep").write_bytes(b"keep")
        await LocalWorkspace(tmp_path, env={}).files.copy("source", "destination", recursive=True, overwrite=True)
        assert (destination / "file").read_bytes() == b"new"
        assert (destination / "link").is_symlink() and (destination / "link").readlink().as_posix() == "file"
        assert (destination / "keep").read_bytes() == b"keep"

    asyncio.run(scenario())
