"""Failures distinguish rejection, uncertain effects, and cleanup."""

from .values import Result


class OhkitError(Exception):
    """Base for library boundary failures."""


class UnsupportedError(OhkitError):
    pass


class BusyError(OhkitError):
    pass


class UnavailableError(OhkitError):
    pass


class InactiveRunError(OhkitError):
    pass


class UndrainedStreamError(OhkitError):
    pass


class ObservationOverflowError(OhkitError):
    pass


class ProtocolError(OhkitError):
    pass


class NativeRejectedError(OhkitError):
    def __init__(self, method: str, code: int, message: str) -> None:
        super().__init__(f"{method} rejected ({code}): {message}")
        self.method = method
        self.code = code


class UnknownOutcomeError(OhkitError):
    """A mutation may have executed. Never replay it automatically."""


class CleanupError(OhkitError):
    def __init__(self, message: str, result: Result | None = None) -> None:
        super().__init__(message)
        self.result = result
