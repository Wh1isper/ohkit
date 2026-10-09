"""Exactly one transport reader; synchronous routing never waits on handlers."""

import asyncio
from collections.abc import Callable, Coroutine

from ..._json import dumps, integer, loads, obj, string
from ...errors import NativeRejectedError, ProtocolError, UnavailableError, UnknownOutcomeError
from ...values import JSONValue
from ._transport import Transport

type RequestID = int | str


def request_id(value: JSONValue) -> RequestID:
    if isinstance(value, str):
        return value
    return integer(value)


class RPC:
    def __init__(
        self,
        transport: Transport,
        timeout: float,
        notification: Callable[[str, dict[str, JSONValue]], None],
        request: Callable[[RequestID, str, dict[str, JSONValue]], None],
        lost: Callable[[Exception], None],
    ) -> None:
        self.transport = transport
        self.timeout = timeout
        self.notification = notification
        self.request = request
        self.lost = lost
        self.pending: dict[RequestID, tuple[str, asyncio.Future[dict[str, JSONValue]]]] = {}
        self.next_id = 0
        self.requests: dict[RequestID, object] = {}
        self.write_lock = asyncio.Lock()
        self.failure: Exception | None = None
        self.reader = asyncio.create_task(self._read())

    def fail(self, error: Exception) -> None:
        if self.failure is not None:
            return
        self.failure = error
        for method, future in self.pending.values():
            if not future.done():
                future.set_exception(
                    UnknownOutcomeError(f"{method}: native acknowledgement unavailable; outcome unknown")
                )
        self.pending.clear()
        self.lost(error)

    async def _read(self) -> None:
        try:
            while True:
                message = obj(loads(await self.transport.receive()))
                if "method" in message:
                    if "result" in message or "error" in message:
                        raise ProtocolError("Native request contains response fields")
                    method = string(message["method"])
                    params = obj(message.get("params", {}))
                    if "id" in message:
                        identity = request_id(message["id"])
                        if identity in self.requests:
                            raise ProtocolError("Duplicate live native interaction identity")
                        self.requests[identity] = object()
                        self.request(identity, method, params)
                    else:
                        if method == "serverRequest/resolved":
                            self.requests.pop(request_id(params["requestId"]), None)
                        self.notification(method, params)
                elif "id" in message:
                    identity = request_id(message["id"])
                    pending = self.pending.get(identity)
                    if pending is None:
                        raise ProtocolError("Uncorrelated native response")
                    method, future = pending
                    if ("result" in message) == ("error" in message):
                        raise ProtocolError("Native response must contain exactly one result or error")
                    if "error" in message:
                        error = obj(message["error"])
                        future.set_exception(
                            NativeRejectedError(method, integer(error["code"]), string(error["message"]))
                        )
                    elif "result" in message:
                        future.set_result(obj(message["result"]))
                    self.pending.pop(identity)
                else:
                    raise ProtocolError("Invalid native message envelope")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.fail(exc)

    async def send(self, message: dict[str, JSONValue]) -> None:
        if self.failure is not None:
            raise UnavailableError("Codex connection unavailable")
        try:
            async with self.write_lock:
                await self.transport.send(dumps(message))
        except asyncio.CancelledError:
            self.fail(UnknownOutcomeError("Native write cancelled after possible dispatch"))
            raise
        except Exception as exc:
            self.fail(exc)
            raise UnknownOutcomeError("Native write failed after possible dispatch") from None

    async def call(self, method: str, params: dict[str, JSONValue]) -> dict[str, JSONValue]:
        if self.failure is not None:
            raise UnavailableError("Codex connection unavailable")
        self.next_id += 1
        identity = self.next_id
        future: asyncio.Future[dict[str, JSONValue]] = asyncio.get_running_loop().create_future()
        self.pending[identity] = (method, future)
        try:
            async with asyncio.timeout(self.timeout):
                await self.send({"id": identity, "method": method, "params": params})
                return await asyncio.shield(future)
        except (TimeoutError, asyncio.CancelledError):
            self.fail(UnknownOutcomeError(f"{method}: acknowledgement lost after possible dispatch"))
            # Consume the future's uncertainty; the driver records it independently.
            if future.done() and not future.cancelled():
                future.exception()
            raise UnknownOutcomeError(f"{method}: acknowledgement lost after possible dispatch") from None
        except Exception:
            if future.done() and not future.cancelled():
                future.exception()
            raise

    def _request_live(self, identity: RequestID) -> Callable[[], bool]:
        owner = self.requests.get(identity)
        return lambda: owner is not None and self.requests.get(identity) is owner

    async def _reply_live(self, message: dict[str, JSONValue], live: Callable[[], bool]) -> bool:
        async with self.write_lock:
            if not live():
                return False
            if self.failure is not None:
                raise UnavailableError("Codex connection unavailable")
            try:
                await self.transport.send(dumps(message))
            except asyncio.CancelledError:
                self.fail(UnknownOutcomeError("Interaction reply cancelled after possible dispatch"))
                raise
            except Exception as exc:
                self.fail(exc)
                raise UnknownOutcomeError("Interaction reply dispatch uncertain") from None
            return True

    async def reply_live(self, identity: RequestID, result: dict[str, JSONValue], live: Callable[[], bool]) -> bool:
        native_live = self._request_live(identity)
        return await self._reply_live({"id": identity, "result": result}, lambda: native_live() and live())

    def reject(
        self, identity: RequestID, message: str, live: Callable[[], bool] = lambda: True
    ) -> Coroutine[object, object, None]:
        # Capture ownership synchronously, before a queued task or write can run.
        # Resolved IDs may be reused; identity membership alone is not ownership.
        native_live = self._request_live(identity)

        async def send() -> None:
            await self._reply_live(
                {"id": identity, "error": {"code": -32601, "message": message}}, lambda: native_live() and live()
            )

        return send()

    async def close(self) -> None:
        self.fail(UnavailableError("Codex backend closed"))
        self.reader.cancel()
        await asyncio.gather(self.reader, return_exceptions=True)
        await self.transport.close()
