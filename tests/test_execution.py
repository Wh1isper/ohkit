import asyncio

import pytest

from ohkit import Capabilities, Thread, ThreadRef, UnavailableError


@pytest.mark.parametrize("fails", [False, True])
def test_thread_close_shares_settlement_and_retains_failure_after_caller_cancellation(fails):
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        error = OSError("resource cleanup failed")
        calls = 0

        class Binding:
            async def close(self):
                nonlocal calls
                calls += 1
                entered.set()
                await release.wait()
                if fails:
                    raise error

        thread = Thread(ThreadRef("test", "history", "scope"), Capabilities(), Binding(), 10)
        first = asyncio.create_task(thread.close())
        await entered.wait()
        first.cancel()
        second = asyncio.create_task(thread.close())
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        pending = not first.done() and not second.done()
        with pytest.raises(UnavailableError):
            await thread.run("not admitted")
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert pending and calls == 1
        if fails:
            assert results == [error, error]
            with pytest.raises(OSError) as repeated:
                await thread.close()
            assert repeated.value is error
        else:
            assert isinstance(results[0], asyncio.CancelledError) and results[1] is None
            await thread.close()
        assert calls == 1

    asyncio.run(exercise())


def test_thread_close_settles_admitted_start_before_driver_and_binding():
    async def exercise():
        entered, release, yielded = asyncio.Event(), asyncio.Event(), asyncio.Event()
        effects = []

        class Driver:
            async def start(self, input):
                entered.set()
                await release.wait()
                effects.append("started")

            async def close(self):
                assert "started" in effects
                effects.append("driver closed")

        class Binding:
            def driver(self, run, handlers):
                return Driver()

            async def close(self):
                assert "driver closed" in effects
                effects.append("binding closed")

        thread = Thread(ThreadRef("test", "history", "scope"), Capabilities(), Binding(), 10)

        async def work():
            async with thread.stream("admitted"):
                yielded.set()

        working = asyncio.create_task(work())
        await entered.wait()
        closing = asyncio.create_task(thread.close())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        premature = bool(effects) or closing.done()
        release.set()
        await asyncio.gather(working, closing)
        assert not premature and yielded.is_set()
        assert effects.count("binding closed") == 1

    asyncio.run(exercise())


def test_thread_close_retains_driver_failure_when_cancelled_stream_clears_active_slot():
    async def exercise():
        error = OSError("driver cleanup failed")
        entered, release = asyncio.Event(), asyncio.Event()

        class Driver:
            async def start(self, input):
                entered.set()
                await release.wait()

            async def close(self):
                raise error

        class Binding:
            def driver(self, run, handlers):
                return Driver()

            async def close(self):
                pass

        thread = Thread(ThreadRef("test", "history", "scope"), Capabilities(), Binding(), 10)

        async def work():
            async with thread.stream("work"):
                pass

        working = asyncio.create_task(work())
        await entered.wait()
        working.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        closing = asyncio.create_task(thread.close())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(closing, working, return_exceptions=True)
        assert results == [error, error], "close lost the active driver failure during startup settlement"
        with pytest.raises(OSError) as repeated:
            await thread.close()
        assert repeated.value is error

    asyncio.run(exercise())
