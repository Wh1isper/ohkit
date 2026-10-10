"""Bundled Claude CLI + loopback Anthropic fixture, isolated credentials/config."""

import asyncio
import json
import os
import runpy
from pathlib import Path

import pytest

from ohkit import Handlers
from ohkit.backends.claude import Claude
from ohkit.errors import UnavailableError

pytestmark = pytest.mark.skipif(os.environ.get("OHKIT_TEST_NATIVE") != "1", reason="Opt-in native executable tests")


fixture = runpy.run_path(str(Path(__file__).parent / "fixtures/anthropic_model.py"))["fixture"]


def test_native_claude_history_across_runs_and_reopened_backend(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            async with Claude(options=options, control_timeout=20) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                first = await thread.run("Remember the first goal")
                assert first.outcome == "completed", first
                assert first.output == "controlled answer 1"
                second = await thread.run("Continue the goal")
                assert second.outcome == "completed", second
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])
                ref = thread.ref
            async with Claude(options=options) as reopened:
                thread = await reopened.resume(ref, cwd=str(tmp_path))
                third = await thread.run("Finish")
                assert third.outcome == "completed", third
                assert "Remember the first goal" in json.dumps(model.calls[-1]["messages"])

    asyncio.run(exercise())


def test_native_claude_interrupt_waits_for_terminal_evidence(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            model.hold = True
            async with Claude(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                async with thread.stream("A slow answer") as run:
                    await asyncio.wait_for(model.entered.get(), 20)
                    await run.cancel()
                    async for _ in run:
                        pass
                    result = await run.result()
                    assert result.outcome == "cancelled", result

    asyncio.run(exercise())


@pytest.mark.parametrize("allow", [True, False])
def test_native_claude_permissions_control_real_tool_effects(tmp_path, monkeypatch, allow):
    async def exercise():
        approved = []

        async def handler(request):
            approved.append(request)
            assert request.native.decode()["tool_name"] == "Write"
            return request.choices[0 if allow else 1]

        async with fixture(tmp_path, monkeypatch) as (model, options):
            target = tmp_path / "controlled.txt"
            model.tools = [("Write", {"file_path": str(target), "content": "approved write\n"})]
            options.tools = ["Write"]
            options.permission_mode = "default"
            async with Claude(options=options) as backend:
                thread = await backend.new_thread(cwd=str(tmp_path))
                result = await thread.run("Write the requested file", handlers=Handlers(approval=handler))
                assert result.outcome == "completed", result
                assert len(approved) == 1, json.dumps(model.calls)
                assert target.exists() == allow
                if allow:
                    assert target.read_text() == "approved write\n"
                assert len(model.calls) == 2
                assert "tool_result" in json.dumps(model.calls[-1]["messages"])

    asyncio.run(exercise())


def test_native_claude_refused_resume_does_not_start_empty_history(tmp_path, monkeypatch):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, options):
            async with Claude(options=options) as backend:
                original = await backend.new_thread(cwd=str(tmp_path))
                thread = await backend.resume(original.ref, cwd=str(tmp_path))
                # No Run has persisted this UUID. The real CLI must refuse it,
                # either during initialization or as a failed native result.
                try:
                    result = await thread.run("Do not silently start over")
                except Exception as exc:
                    from claude_agent_sdk import ResultError

                    assert isinstance(exc, ResultError), exc
                    with pytest.raises(UnavailableError):
                        await thread.run("No implicit retry")
                else:
                    assert result.outcome == "failed", result
                assert not model.calls

    asyncio.run(exercise())


def test_native_claude_runnable_example(tmp_path, monkeypatch, capsys):
    async def exercise():
        async with fixture(tmp_path, monkeypatch) as (model, _):
            example = runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples/claude.py"))
            monkeypatch.setattr("sys.argv", ["claude.py", "--cwd", str(tmp_path)])
            await example["main"]()
            assert len(model.calls) == 2
            output = capsys.readouterr().out
            assert "Outcome: completed" in output
            assert "controlled answer 2" in output

    asyncio.run(exercise())
