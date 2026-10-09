"""Backend-independent immutable execution values."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

# Native data has an explicit JSON-only boundary, never arbitrary Python objects.
type JSONValue = bool | int | float | str | list[JSONValue] | dict[str, JSONValue] | None


@dataclass(frozen=True, slots=True)
class NativeData:
    """Validated JSON text; immutable ownership, with detached decoding on demand.

    Native observations may contain private inputs. They are not safe-to-publish logs.
    """

    namespace: str
    json: str = field(repr=False)

    def __post_init__(self) -> None:
        from ._json import loads

        loads(self.json)

    def decode(self) -> JSONValue:
        from ._json import loads

        return loads(self.json)


@dataclass(frozen=True, slots=True)
class ThreadRef:
    backend: str
    id: str
    scope: str


@dataclass(frozen=True, slots=True)
class Capabilities:
    steer: bool = False
    resume: bool = False
    fork: bool = False
    approvals: bool = False
    questions: bool = False
    workspace: bool = False


@dataclass(frozen=True, slots=True)
class Text:
    text: str


@dataclass(frozen=True, slots=True)
class Image:
    url: str


@dataclass(frozen=True, slots=True)
class LocalImage:
    path: str


type Input = str | tuple[Text | Image | LocalImage, ...]
type Outcome = Literal["completed", "failed", "cancelled", "unknown"]


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Result:
    thread: ThreadRef
    run_id: str
    outcome: Outcome
    output: str
    usage: Usage | None = None
    failure: Failure | None = None
    native_turn_id: str | None = None
    native_status: str | None = None
    native: NativeData | None = None


@dataclass(frozen=True, slots=True)
class ApprovalChoice:
    """Return an offered choice unchanged; scope is native, not a policy override."""

    kind: Literal["accept", "acceptForSession", "decline", "cancel", "execpolicy", "network", "permissions"]
    scope: Literal["action", "turn", "session", "persistent"]
    native: NativeData | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    thread: ThreadRef
    run_id: str
    id: str
    kind: Literal["command", "file_change", "permissions"]
    item_id: str
    reason: str | None
    choices: tuple[ApprovalChoice, ...]
    command: str | None = None
    cwd: str | None = None
    grant_root: str | None = None
    # Exact native permission overlay, proposed amendments, environment identity,
    # and effective scope remain available without a lossy normalization.
    native: NativeData | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class QuestionOption:
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    header: str
    text: str
    options: tuple[QuestionOption, ...] | None
    allow_other: bool = False
    secret: bool = False


@dataclass(frozen=True, slots=True)
class QuestionRequest:
    thread: ThreadRef
    run_id: str
    id: str
    item_id: str
    questions: tuple[Question, ...]
    blocking: bool


@dataclass(frozen=True, slots=True)
class Answer:
    question_id: str
    values: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class QuestionResponse:
    answers: tuple[Answer, ...]


@dataclass(frozen=True, slots=True)
class Handlers:
    approval: Callable[[ApprovalRequest], Awaitable[ApprovalChoice]] | None = None
    question: Callable[[QuestionRequest], Awaitable[QuestionResponse]] | None = None


@dataclass(frozen=True, slots=True)
class ContentEvent:
    thread: ThreadRef
    run_id: str
    item_id: str
    text: str
    channel: Literal["assistant", "reasoning", "tool"]
    kind: Literal["content"] = field(default="content", init=False)


@dataclass(frozen=True, slots=True)
class ToolEvent:
    thread: ThreadRef
    run_id: str
    item_id: str
    name: str
    phase: Literal["started", "completed"]
    native: NativeData
    kind: Literal["tool"] = field(default="tool", init=False)


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    thread: ThreadRef
    run_id: str
    request_id: str
    phase: Literal["requested", "answered", "withdrawn", "failed"]
    request: ApprovalRequest | QuestionRequest | None = None
    kind: Literal["interaction"] = field(default="interaction", init=False)


@dataclass(frozen=True, slots=True)
class UsageEvent:
    thread: ThreadRef
    run_id: str
    usage: Usage
    kind: Literal["usage"] = field(default="usage", init=False)


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    thread: ThreadRef
    run_id: str
    phase: Literal["started", "cancelling", "terminal"]
    result: Result | None = None
    kind: Literal["lifecycle"] = field(default="lifecycle", init=False)


@dataclass(frozen=True, slots=True)
class NativeEvent:
    thread: ThreadRef
    run_id: str
    method: str
    native: NativeData
    kind: Literal["native"] = field(default="native", init=False)


type Event = ContentEvent | ToolEvent | InteractionEvent | UsageEvent | LifecycleEvent | NativeEvent
