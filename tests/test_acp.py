import asyncio
import runpy
import sys
from pathlib import Path

import pytest

from ohkit import ApprovalChoice, ContentEvent, Handlers, Image
from ohkit.backends.acp import ACP, ACPOptions
from ohkit.errors import (
    BusyError,
    InactiveRunError,
    ObservationOverflowError,
    UnavailableError,
    UnknownOutcomeError,
    UnsupportedError,
)

PEER = Path(__file__).parent / "fixtures" / "acp_agent.py"


def options(**kwargs):
    return ACPOptions(command=(sys.executable, str(PEER)), control_timeout=2, cleanup_timeout=0.3, **kwargs)


def test_acp_public_execution_resume_and_native_stop_reason():
    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/native/namespace")
            assert thread.capabilities.resume and not thread.capabilities.steer
            assert not thread.capabilities.fork and not thread.capabilities.workspace
            result = await thread.run("hello")
            assert result.outcome == "completed" and result.output == "answer:hello"
            assert result.native_status == "end_turn"
            assert result.native.namespace == "acp"
            resumed = await backend.resume(thread.ref, cwd="/native/namespace")
            assert resumed.ref == thread.ref
            assert (await resumed.run("next")).output == "answer:next"
            with pytest.raises(UnavailableError):
                await thread.run("closed")
            with pytest.raises(UnsupportedError):
                await backend.fork(resumed.ref, cwd="/native/namespace")

    asyncio.run(exercise())


def test_acp_ordered_updates_and_unsupported_input():
    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            with pytest.raises(UnsupportedError):
                await thread.run((Image("https://example.invalid/image.png"),))
            result = await thread.run("burst")
            assert result.output == "".join(f"{i}," for i in range(100))

    asyncio.run(exercise())


def test_acp_busy_cancel_and_early_exit():
    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            async with thread.stream("wait") as run:
                async for event in run:
                    if isinstance(event, ContentEvent):
                        with pytest.raises(BusyError):
                            await thread.run("other")
                        with pytest.raises(UnsupportedError):
                            await run.steer("change")
                        await run.cancel()
                assert (await run.result()).outcome == "cancelled"
                with pytest.raises(InactiveRunError):
                    await run.cancel()
            async with thread.stream("wait") as run:
                async for event in run:
                    if isinstance(event, ContentEvent):
                        break
            assert (await thread.run("again")).outcome == "completed"

    asyncio.run(exercise())


@pytest.mark.parametrize("choice", [None, 0, 1, "invalid", "raises"])
def test_acp_permissions_preserve_native_option_identity(choice):
    async def handler(request):
        assert request.kind == "tool"
        assert [value.native.decode()["kind"] for value in request.choices] == ["allow_once", "reject_always"]
        assert all(value.scope == "native" for value in request.choices)
        if choice == "invalid":
            return ApprovalChoice("accept", "action")
        if choice == "raises":
            raise RuntimeError("handler failed")
        return request.choices[choice]

    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            result = await thread.run("permission", handlers=Handlers(approval=handler if choice is not None else None))
            if choice in (0, 1):
                assert '"outcome": "selected"' in result.output
                assert ('"once"' if choice == 0 else '"always"') in result.output
            else:
                assert '"outcome": "cancelled"' in result.output

    asyncio.run(exercise())


def test_acp_cancel_with_pending_permission():
    async def exercise():
        waiting = asyncio.Event()
        withdrawn = asyncio.Event()

        async def handler(request):
            waiting.set()
            try:
                await asyncio.Event().wait()
            finally:
                withdrawn.set()

        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            async with thread.stream("permission", handlers=Handlers(approval=handler)) as run:
                await waiting.wait()
                await run.cancel()
                async for _ in run:
                    pass
                assert withdrawn.is_set()
                assert '"cancelled"' in (await run.result()).output

    asyncio.run(exercise())


@pytest.mark.parametrize("input,outcome", [("reject", "failed"), ("disconnect", "unknown")])
def test_acp_native_failure_is_not_success(input, outcome):
    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            result = await thread.run(input)
            assert result.outcome == outcome
            if outcome == "unknown":
                with pytest.raises(UnavailableError):
                    await thread.run("no replay")

    asyncio.run(exercise())


def test_acp_cleanup_timeout_invalidates_owner():
    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd="/remote")
            with pytest.raises(UnknownOutcomeError):
                async with thread.stream("ignore_cancel") as run:
                    async for event in run:
                        if isinstance(event, ContentEvent):
                            break
            with pytest.raises(UnavailableError):
                await thread.run("unsafe")

    asyncio.run(exercise())


def test_acp_overflow_is_explicit():
    async def exercise():
        async with ACP(options=options(event_capacity=2)) as backend:
            thread = await backend.new_thread(cwd="/remote")
            with pytest.raises(ObservationOverflowError):
                async with thread.stream("burst") as run:
                    await asyncio.sleep(0.2)
                    async for _ in run:
                        pass

    asyncio.run(exercise())


def test_acp_wire_workspace_callbacks_use_real_target(tmp_path):
    LocalWorkspace = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "local_workspace.py"))[
        "LocalWorkspace"
    ]

    async def exercise():
        async with ACP(options=options()) as backend:
            thread = await backend.new_thread(cwd=str(tmp_path), workspace=LocalWorkspace(tmp_path))
            assert thread.capabilities.workspace
            result = await thread.run("workspace")
            assert result.outcome == "completed"
            assert result.output == f"target:{tmp_path}\n"
            assert (tmp_path / "nested/test.txt").read_bytes() == b"one\r\ntwo\r\nthree\n"

    asyncio.run(exercise())


@pytest.mark.parametrize("pending", [True, False])
def test_acp_overflow_settles_permission_without_admitting_late_handlers(pending):
    async def exercise():
        entered, withdrawn = asyncio.Event(), asyncio.Event()

        async def handler(request):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                withdrawn.set()

        async with ACP(options=options(event_capacity=2 if pending else 1)) as backend:
            thread = await backend.new_thread(cwd="/remote")
            with pytest.raises(ObservationOverflowError):
                async with thread.stream("permission", handlers=Handlers(approval=handler)) as run:
                    if pending:
                        await asyncio.wait_for(entered.wait(), 2)
                        run._emit(ContentEvent(run.thread, run.id, "assistant", "overflow", "assistant"))
                    async with asyncio.timeout(2):
                        while not run._overflow:
                            await asyncio.sleep(0.001)
                    try:
                        await run.cancel()
                    except InactiveRunError:
                        pass  # Overflow may already have completed native cancellation.
                    for _ in range(100):
                        if run._terminal is not None:
                            break
                        await asyncio.sleep(0.005)
                    settled = run._terminal is not None
                    admitted = entered.is_set()
                    was_withdrawn = withdrawn.is_set()
                    # Bound failure cleanup so the regression reports an assertion,
                    # not a hung ACP agent waiting for the leaked decision.
                    if not settled:
                        for decision in run._driver.decisions:
                            decision.cancel()
                    async with asyncio.timeout(2):
                        async for _ in run:
                            pass
            assert settled, "overflow left the native permission unresolved"
            assert admitted == pending
            assert was_withdrawn == pending

    asyncio.run(exercise())
