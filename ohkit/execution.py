"""Shared single-owner execution and nonblocking observation."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol
from uuid import uuid4

from .errors import BusyError, ObservationOverflowError, UnavailableError, UndrainedStreamError
from .values import Capabilities, Event, Handlers, Input, LifecycleEvent, Result, ThreadRef


class _Driver(Protocol):
    async def start(self, input: Input) -> None: ...
    async def steer(self, input: Input) -> None: ...
    async def cancel(self) -> None: ...
    async def close(self) -> None: ...
    def overflow(self) -> None: ...


class _Binding(Protocol):
    def driver(self, run: Run, handlers: Handlers) -> _Driver: ...
    async def close(self) -> None: ...


async def _settle(task: asyncio.Task[None]) -> None:
    """Finish owned cleanup even when its caller is cancelled again."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


class Run(AsyncIterator[Event]):
    """One foreground unit, one event consumer. Use Thread.stream to create it."""

    def __init__(self, thread: Thread, capacity: int) -> None:
        self.thread = thread.ref
        self.id = "run_" + uuid4().hex
        self._events: deque[Event] = deque()
        self._capacity = capacity
        self._changed = asyncio.Event()
        self._terminal: Result | None = None
        self._drained = False
        self._overflow = False
        self._reading = False
        self._consumer: asyncio.Task[object] | None = None
        self._driver: _Driver | None = None

    def _emit(self, event: Event) -> None:
        if self._terminal is not None:
            return
        if len(self._events) >= self._capacity:
            if not self._overflow:
                self._overflow = True
                assert self._driver is not None
                self._driver.overflow()
        elif not self._overflow:
            self._events.append(event)
        self._changed.set()

    def _finish(self, result: Result) -> None:
        if self._terminal is not None:
            return
        # Terminal evidence is out-of-band and cannot be lost to observation pressure.
        self._terminal = result
        self._changed.set()

    def __aiter__(self) -> Run:
        return self

    async def __anext__(self) -> Event:
        task = asyncio.current_task()
        if self._reading or (self._consumer is not None and self._consumer is not task):
            raise RuntimeError("A Run has exactly one event consumer")
        self._consumer = task
        self._reading = True
        try:
            while True:
                if self._events:
                    return self._events.popleft()
                if self._terminal is not None:
                    if not self._drained:
                        self._drained = True
                        if self._overflow:
                            raise ObservationOverflowError("Run observations exceeded the bounded buffer")
                        return LifecycleEvent(self.thread, self.id, "terminal", self._terminal)
                    raise StopAsyncIteration
                self._changed.clear()
                await self._changed.wait()
        finally:
            self._reading = False

    async def steer(self, input: Input) -> None:
        assert self._driver is not None
        await self._driver.steer(input)

    async def cancel(self) -> None:
        """Request interruption; drainage still waits for native termination evidence."""
        assert self._driver is not None
        await self._driver.cancel()

    async def result(self) -> Result:
        if not self._drained or self._terminal is None:
            raise UndrainedStreamError(
                "Drain the Run stream before calling result(); use Thread.run for result-only work"
            )
        return self._terminal


class Thread:
    """A process-local live owner of native conversation history."""

    def __init__(self, ref: ThreadRef, capabilities: Capabilities, binding: _Binding, capacity: int) -> None:
        self.ref = ref
        self.capabilities = capabilities
        self._binding = binding
        self._capacity = capacity
        self._active: Run | None = None
        self._available = True
        self._closed = False
        self._closing: asyncio.Task[None] | None = None
        self._starting: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def stream(self, input: Input, *, handlers: Handlers | None = None) -> AsyncGenerator[Run]:
        if not self._available or self._closed:
            raise UnavailableError("Thread owner is unavailable; explicitly resume history into a new owner")
        if self._active is not None:
            raise BusyError("Thread already owns a Run; inputs are not queued")
        run = Run(self, self._capacity)
        driver = self._binding.driver(run, handlers or Handlers())
        run._driver = driver
        self._active = run
        start = asyncio.create_task(driver.start(input))
        self._starting = start
        try:
            await asyncio.shield(start)
            yield run
        finally:

            async def cleanup() -> None:
                try:
                    # Start is still owned after caller cancellation. Lost acceptance
                    # must settle as unknown, never be replayed.
                    try:
                        await start
                    except Exception:
                        pass
                    await driver.close()
                finally:
                    self._active = None
                    self._starting = None

            await _settle(asyncio.create_task(cleanup()))

    async def run(self, input: Input, *, handlers: Handlers | None = None) -> Result:
        async with self.stream(input, handlers=handlers) as run:
            async for _ in run:
                pass
            return await run.result()

    async def close(self) -> None:
        if self._closing is None:
            self._closed = True
            self._closing = asyncio.create_task(self._close(self._active, self._starting))
        await _settle(self._closing)

    async def _close(self, run: Run | None, start: asyncio.Task[None] | None) -> None:
        try:
            # Capture ownership before scheduling: stream cleanup can clear the
            # live slot while this close is settling the admitted submission.
            if start is not None:
                await asyncio.gather(start, return_exceptions=True)
            if run is not None:
                assert run._driver is not None
                await run._driver.close()
        finally:
            await self._binding.close()
