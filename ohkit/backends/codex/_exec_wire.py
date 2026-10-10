"""Private exec-server ingress shapes pinned to rust-v0.162.0.

Unlike app-server, exec-server has no CLI schema export. These selected request
shapes follow exec-server-protocol/src/protocol.rs; see docs/codex-protocol.md.
Unknown operation requirements are rejected rather than silently discarded.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ...values import JSONValue

Positive = Annotated[int, Field(gt=0)]
Nonnegative = Annotated[int, Field(ge=0)]


class Params(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", alias_generator=to_camel, populate_by_name=True)


class Initialize(Params):
    client_name: str
    resume_session_id: str | None = None


class PathParams(Params):
    path: str
    sandbox: dict[str, JSONValue] | None = None


class FollowPath(PathParams):
    follow_symlinks: bool | None = None


class WriteFile(FollowPath):
    data_base64: str


class Directory(FollowPath):
    recursive: bool | None = None


class Remove(Directory):
    force: bool | None = None


class Copy(Params):
    source_path: str
    destination_path: str
    recursive: bool
    sandbox: dict[str, JSONValue] | None = None


class Open(PathParams):
    handle_id: str
    mode: Literal["read", "replace"] = "read"


class Handle(Params):
    handle_id: str


class ReadBlock(Handle):
    offset: Nonnegative
    len: Nonnegative


class EnvPolicy(Params):
    inherit: Literal["all", "none", "core"]
    ignore_default_excludes: bool
    exclude: list[str]
    set: dict[str, str]
    include_only: list[str]


class Start(Params):
    process_id: str
    metadata: dict[str, JSONValue] | None = None
    argv: Annotated[list[str], Field(min_length=1)]
    cwd: str
    env_policy: EnvPolicy | None = None
    env: dict[str, str]
    tty: bool
    pipe_stdin: bool = False
    arg0: str | None = None
    sandbox: dict[str, JSONValue] | None = None
    shell_snapshot: dict[str, JSONValue] | None = None
    enforce_managed_network: bool = False
    managed_network: dict[str, JSONValue] | None = None
    network_proxy: dict[str, JSONValue] | None = None


class Process(Params):
    process_id: str


class Read(Process):
    after_seq: Nonnegative | None = None
    max_bytes: Positive | None = None
    wait_ms: Nonnegative | None = None


class Write(Process):
    chunk: str
    write_id: str


class Signal(Process):
    signal: Literal["interrupt"]
