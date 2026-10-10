"""Real third-party ACP agent and its Claude runtime, with a loopback model."""

import asyncio
import json
import os
import runpy
from pathlib import Path

import pytest

from examples.local_workspace import LocalFiles, LocalWorkspace
from ohkit import ContentEvent, Handlers
from ohkit.backends.acp import ACP, ACPOptions

pytestmark = pytest.mark.skipif(os.environ.get("OHKIT_TEST_ACP_NATIVE") != "1", reason="Opt-in third-party ACP tests")
ROOT = Path(__file__).resolve().parents[1]
fixture = runpy.run_path(str(Path(__file__).parent / "fixtures/anthropic_model.py"))["fixture"]
AGENT = Path(
    os.environ.get(
        "OHKIT_ACP_AGENT",
        str(ROOT / "tests/fixtures/acp/node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js"),
    )
)


def test_native_acp_history(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, _):
            options = ACPOptions(command=("node", str(AGENT)), env=tuple(os.environ.items()), control_timeout=30)
            async with ACP(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                events = []
                async with thread.stream("Remember the first goal") as run:
                    async for event in run:
                        events.append(event)
                    first = await run.result()
                assert any(isinstance(event, ContentEvent) for event in events)
                assert first.outcome == "completed", first
                assert first.output == "controlled answer 1"
                second = await thread.run("Continue the goal")
                assert second.outcome == "completed", second
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])
                assert thread.capabilities.resume
                ref = thread.ref
            async with ACP(options=options) as reopened:
                thread = await reopened.resume(ref, cwd=str(tmp_path))
                result = await thread.run("Finish")
                assert result.outcome == "completed", result
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])

    asyncio.run(exercise())


class ObservedFiles(LocalFiles):
    def __init__(self, cwd):
        super().__init__(cwd)
        self.calls = []

    async def read(self, path, **kwargs):
        self.calls.append(("read", path))
        return await super().read(path, **kwargs)

    async def write(self, path, data, **kwargs):
        self.calls.append(("write", path))
        return await super().write(path, data, **kwargs)


class ObservedWorkspace(LocalWorkspace):
    def __init__(self, cwd):
        super().__init__(cwd)
        self.files = ObservedFiles(cwd)
        self.starts = []

    async def start_process(self, request):
        self.starts.append(request)
        return await super().start_process(request)


@pytest.mark.parametrize("allow", [True, False])
def test_native_acp_tools_and_workspace_coverage(tmp_path, monkeypatch, allow):
    async def exercise():
        decisions = []

        async def handler(request):
            decisions.append(request)
            kind = "allow_once" if allow else "reject_once"
            return next(choice for choice in request.choices if choice.native.decode()["kind"] == kind)

        async with fixture(tmp_path, monkeypatch) as (model, _):
            source = tmp_path / "source.txt"
            source.write_text("source marker\n")
            target = tmp_path / "changed.txt"
            command_target = tmp_path / "command.txt"
            model.tools = [
                ("Read", {"file_path": str(source)}),
                ("Write", {"file_path": str(target), "content": "approved write\n"}),
                (
                    "Bash",
                    {"command": f"printf command-marker > '{command_target}'", "description": "Write fixture marker"},
                ),
            ]
            workspace = ObservedWorkspace(tmp_path)
            options = ACPOptions(command=("node", str(AGENT)), env=tuple(os.environ.items()))
            async with ACP(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path), workspace=workspace)
                result = await thread.run(
                    "Read, change, and run the requested command", handlers=Handlers(approval=handler)
                )
                assert result.outcome == "completed", result
                assert result.output == "controlled answer 4", result
                assert len(decisions) >= 2, decisions
                assert target.exists() == allow
                assert command_target.exists() == allow
                if allow:
                    assert target.read_text() == "approved write\n"
                    assert command_target.read_text() == "command-marker"
                assert "source marker" in json.dumps(model.calls[-1]["messages"])
            # This agent version uses native tools, not ACP client I/O callbacks.
            assert workspace.files.calls == []
            assert workspace.starts == []

    asyncio.run(exercise())


def test_native_acp_cancel_and_reuse(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, _):
            options = ACPOptions(command=("node", str(AGENT)), env=tuple(os.environ.items()))
            async with ACP(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                model.hold = True
                async with thread.stream("Wait for cancellation") as run:
                    await asyncio.wait_for(model.entered.get(), 20)
                    await run.cancel()
                    async for _ in run:
                        pass
                    assert (await run.result()).outcome == "cancelled"
                model.hold = False
                model.release.set()
                assert (await thread.run("Continue after cancellation")).outcome == "completed"

    asyncio.run(exercise())


def test_native_acp_runnable_example(tmp_path, monkeypatch, capsys):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, _):
            example = runpy.run_path(str(ROOT / "examples/acp.py"))
            monkeypatch.setattr("sys.argv", ["acp.py", "--cwd", str(tmp_path), "--", "node", str(AGENT)])
            await example["main"]()
            # The agent may make an additional native session-title request.
            assert len(model.calls) >= 2
            history = json.dumps(model.calls[-1]["messages"])
            assert "Describe this project without changing files." in history
            assert "Summarize that in one sentence." in history
            output = capsys.readouterr().out
            assert "Outcome: completed" in output
            assert f"controlled answer {len(model.calls)}" in output

    asyncio.run(exercise())
