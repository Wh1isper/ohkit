import asyncio
import runpy
from pathlib import Path

import pytest
from acp import RequestError

from ohkit.backends.acp._workspace import WorkspaceCallbacks, _Terminal
from ohkit.workspace import ProcessOutput, ProcessRequest


class Process:
    def __init__(self):
        self.blocks = asyncio.Queue()
        self.exited = asyncio.Event()
        self.close_count = 0
        self.signals = []

    async def read(self, max_bytes):
        return await self.blocks.get()

    async def wait(self):
        await self.exited.wait()
        return 0

    async def close(self):
        self.close_count += 1
        self.exited.set()
        await self.blocks.put(ProcessOutput(eof=True))

    async def signal(self, value):
        self.signals.append(value)
        self.exited.set()


@pytest.mark.parametrize(
    "limit,expected,truncated", [(8, "a€b", False), (4, "€b", True), (3, "b", True), (0, "", True)]
)
def test_terminal_incremental_utf8_and_byte_bounded_snapshots(limit, expected, truncated):
    async def exercise():
        process = Process()
        terminal = _Terminal(process, limit)
        await process.blocks.put(ProcessOutput(b"a\xe2"))
        await process.blocks.put(ProcessOutput(b"\x82\xacb", eof=True))
        await terminal.reader
        first = terminal.snapshot()
        assert first.output == expected and first.truncated == truncated
        assert terminal.snapshot() == first
        await terminal.close()

    asyncio.run(exercise())


def test_terminal_loss_and_separate_stream_decoders():
    async def exercise():
        process = Process()
        terminal = _Terminal(process, 100)
        await process.blocks.put(ProcessOutput(b"\xe2"))
        await process.blocks.put(ProcessOutput(b"err", stream="stderr"))
        await process.blocks.put(ProcessOutput(b"\x82\xac"))
        await process.blocks.put(ProcessOutput(b"\xff", lost_bytes=5, eof=True))
        await terminal.reader
        assert terminal.snapshot().output == "err€�"
        assert terminal.snapshot().truncated
        await terminal.close()

    asyncio.run(exercise())


def test_terminal_exit_does_not_require_output_eof_and_close_is_shared():
    async def exercise():
        process = Process()
        terminal = _Terminal(process, 100)
        process.exited.set()
        assert (await terminal.wait()).exit_code == 0
        assert not terminal.reader.done()
        await asyncio.gather(terminal.close(), terminal.close())
        assert process.close_count == 1

    asyncio.run(exercise())


def test_workspace_retains_terminal_until_release_and_reclaims_capacity():
    async def exercise():
        process = Process()

        class Workspace:
            async def start_process(self, request):
                assert request.argv == ("command",)
                return process

        workspace = WorkspaceCallbacks(Workspace(), "/target", 100, 1)
        identity = (await workspace.create(ProcessRequest(("command",)), None)).terminal_id
        process.exited.set()
        await workspace.get(identity).wait()
        with pytest.raises(RequestError):
            await workspace.create(ProcessRequest(("command",)), None)
        assert workspace.get(identity).process is process
        await workspace.release(identity)
        with pytest.raises(RequestError):
            workspace.get(identity)
        next_id = (await workspace.create(ProcessRequest(("command",)), None)).terminal_id
        assert next_id != identity
        await workspace.close()

    asyncio.run(exercise())


def test_workspace_close_owns_cancelled_late_launch():
    async def exercise():
        process, entered, release = Process(), asyncio.Event(), asyncio.Event()

        class Workspace:
            async def start_process(self, request):
                entered.set()
                await release.wait()
                return process

        workspace = WorkspaceCallbacks(Workspace(), "/target", 100, 1)
        creating = asyncio.create_task(workspace.create(ProcessRequest(("command",)), None))
        await entered.wait()
        creating.cancel()
        with pytest.raises(asyncio.CancelledError):
            await creating
        closing = asyncio.create_task(workspace.close())
        await asyncio.sleep(0)
        assert not closing.done()
        release.set()
        await closing
        assert process.close_count == 1 and not workspace.terminals

    asyncio.run(exercise())


def test_workspace_text_projection_strict_encoding_and_preserved_lines(tmp_path):
    LocalWorkspace = runpy.run_path(str(Path(__file__).parents[1] / "examples/local_workspace.py"))["LocalWorkspace"]

    async def exercise():
        workspace = WorkspaceCallbacks(LocalWorkspace(tmp_path), str(tmp_path), 100, 1)
        await workspace.write("nested/text", "a\r\nb\r\nc\n")
        assert (await workspace.read("nested/text", 2, 1)).content == "b\r\n"
        (tmp_path / "invalid").write_bytes(b"\xff")
        with pytest.raises(UnicodeDecodeError):
            await workspace.read("invalid", None, None)
        with pytest.raises(RequestError):
            await workspace.read("nested/text", 0, None)
        await workspace.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("cancel_create", [False, True])
@pytest.mark.parametrize("close_fails", [False, True])
def test_workspace_close_observes_late_launch_cleanup(cancel_create, close_fails):
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        error = OSError("process termination unconfirmed")
        calls = 0

        class LateProcess:
            async def close(self):
                nonlocal calls
                calls += 1
                if close_fails:
                    raise error

        class Workspace:
            async def start_process(self, request):
                entered.set()
                await release.wait()
                return LateProcess()

        workspace = WorkspaceCallbacks(Workspace(), "/target", 100, 1)
        creating = asyncio.create_task(workspace.create(ProcessRequest(("command",)), None))
        await entered.wait()
        if cancel_create:
            creating.cancel()
            with pytest.raises(asyncio.CancelledError):
                await creating
        closing = asyncio.create_task(workspace.close())
        await asyncio.sleep(0)
        assert workspace.closed and not closing.done()
        release.set()
        results = await asyncio.gather(creating, closing, return_exceptions=True)
        assert calls == 1
        if close_fails:
            assert isinstance(results[1], ExceptionGroup)
            assert results[1].exceptions == (error,)
            with pytest.raises(ExceptionGroup) as repeated:
                await workspace.close()
            assert repeated.value is results[1]
        else:
            assert results[1] is None
            assert isinstance(results[0], asyncio.CancelledError if cancel_create else RequestError)
            await workspace.close()
        assert calls == 1

    asyncio.run(exercise())
