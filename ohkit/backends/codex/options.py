"""Native Codex settings, not a universal agent configuration."""

from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class CodexOptions:
    executable: str = "codex"
    # Native CLI -c overrides can contain credentials: never include them in repr.
    config: tuple[str, ...] = field(default=(), repr=False)
    env: tuple[tuple[str, str], ...] | None = field(default=None, repr=False)
    websocket_url: str | None = field(default=None, repr=False)
    headers: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    # Scope is a caller-owned non-secret storage/service identity for remote use.
    history_scope: str | None = None
    event_capacity: int = 256
    request_timeout: float = 30.0
    cleanup_timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.event_capacity < 1 or self.request_timeout <= 0 or self.cleanup_timeout <= 0:
            raise ValueError("Buffer capacity and timeouts must be positive")
        if self.websocket_url is not None:
            url = urlsplit(self.websocket_url)
            if url.scheme not in ("ws", "wss") or not url.hostname or url.username or url.password:
                raise ValueError("Use a ws/wss endpoint without embedded credentials")
            if not self.history_scope:
                raise ValueError("Remote Codex requires a non-secret history_scope")
            if self.env is not None or self.config:
                raise ValueError("Remote connections cannot set native process environment/config")


@dataclass(frozen=True, slots=True)
class CodexThreadOptions:
    model: str | None = None
    model_provider: str | None = None
    approval_policy: Literal["untrusted", "on-request", "never"] | None = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    base_instructions: str | None = field(default=None, repr=False)
    developer_instructions: str | None = field(default=None, repr=False)
