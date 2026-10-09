"""Real owned child lifecycle; the child is controlled, not native Codex."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from ohkit import UnavailableError, UnknownOutcomeError
from ohkit.backends.codex import Codex, CodexOptions

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Executable fixture uses a POSIX shebang")


def options(tmp_path):
    executable = tmp_path / "controlled-codex"
    source = Path(__file__).parent / "fixtures" / "stdio_peer.py"
    executable.write_text(f"#!{sys.executable}\n" + source.read_text())
    executable.chmod(0o700)
    return CodexOptions(
        executable=str(executable),
        env=(
            ("HOME", str(tmp_path)),
            ("OHKIT_TEST_FIXTURES", str(source.parent)),
            ("OHKIT_TEST_PID", str(tmp_path / "pid")),
            ("OHKIT_TEST_CALLS", str(tmp_path / "calls")),
        ),
        request_timeout=2,
        cleanup_timeout=2,
    )


def assert_exited(tmp_path):
    pid = int((tmp_path / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_stdio_context_early_exit_interrupts_and_reaps_owned_child(tmp_path):
    async def scenario():
        async with Codex(options=options(tmp_path)) as backend:
            thread = await backend.new_thread()
            async with thread.stream("active") as run:
                pass  # Context exit settles foreground work before process close.
            async for _ in run:
                pass
            assert (await run.result()).outcome == "cancelled"
        assert_exited(tmp_path)
        calls = (tmp_path / "calls").read_text().splitlines()
        assert calls.count("turn/start") == 1 and calls.count("turn/interrupt") == 1

    asyncio.run(scenario())


def test_stdio_child_death_during_submission_is_unknown_not_replayed(tmp_path):
    async def scenario():
        async with Codex(options=options(tmp_path)) as backend:
            thread = await backend.new_thread()
            with pytest.raises(UnknownOutcomeError):
                await thread.run("die")
            with pytest.raises(UnavailableError):
                await thread.run("retry")
        assert_exited(tmp_path)
        assert (tmp_path / "calls").read_text().splitlines().count("turn/start") == 1

    asyncio.run(scenario())
