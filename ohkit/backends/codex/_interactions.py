"""Project validated native interactions without widening offered authority."""

from typing import Literal

from ..._json import native, obj
from ...errors import ProtocolError, UnsupportedError
from ...values import (
    ApprovalChoice,
    ApprovalRequest,
    JSONValue,
    Question,
    QuestionOption,
    QuestionRequest,
    QuestionResponse,
    ThreadRef,
)
from . import _generated as wire
from ._rpc import RequestID
from ._wire import decode, encode

type Decision = (
    Literal["accept", "acceptForSession", "decline", "cancel"]
    | wire.AcceptWithExecpolicyAmendmentCommandExecutionApprovalDecision
    | wire.ApplyNetworkPolicyAmendmentCommandExecutionApprovalDecision
)


def _choice(value: Decision) -> ApprovalChoice:
    if isinstance(value, str):
        if value == "acceptForSession":
            return ApprovalChoice("acceptForSession", "session")
        return ApprovalChoice(value, "action")
    if isinstance(value, wire.AcceptWithExecpolicyAmendmentCommandExecutionApprovalDecision):
        return ApprovalChoice("execpolicy", "persistent", native(encode(value)))
    return ApprovalChoice("network", "persistent", native(encode(value)))


def _command_choices(params: wire.CommandExecutionRequestApprovalParams) -> tuple[ApprovalChoice, ...]:
    if params.available_decisions is not None:
        return tuple(_choice(value) for value in params.available_decisions)
    # Native TUI default_available_decisions, not every deserializable decision.
    defaults: list[ApprovalChoice] = [_choice("accept")]
    if params.network_approval_context is not None:
        defaults.append(_choice("acceptForSession"))
        for amendment in params.proposed_network_policy_amendments or ():
            if amendment.action == "allow":
                defaults.append(
                    ApprovalChoice(
                        "network",
                        "persistent",
                        native(
                            {
                                "applyNetworkPolicyAmendment": {"network_policy_amendment": encode(amendment)},
                            }
                        ),
                    )
                )
                break
    elif params.additional_permissions is None and params.proposed_execpolicy_amendment is not None:
        defaults.append(
            ApprovalChoice(
                "execpolicy",
                "persistent",
                native(
                    {
                        "acceptWithExecpolicyAmendment": {
                            "execpolicy_amendment": list(params.proposed_execpolicy_amendment)
                        },
                    }
                ),
            )
        )
    defaults.append(_choice("cancel"))
    return tuple(defaults)


def approval(
    ref: ThreadRef, run_id: str, identity: RequestID, method: str, params: dict[str, JSONValue]
) -> ApprovalRequest:
    if method == "item/commandExecution/requestApproval":
        command = decode(wire.CommandExecutionRequestApprovalParams, params)
        return ApprovalRequest(
            ref,
            run_id,
            str(identity),
            "command",
            command.item_id,
            command.reason,
            _command_choices(command),
            command=command.command,
            cwd=command.cwd,
            native=native(params),
        )
    if method == "item/fileChange/requestApproval":
        change = decode(wire.FileChangeRequestApprovalParams, params)
        return ApprovalRequest(
            ref,
            run_id,
            str(identity),
            "file_change",
            change.item_id,
            change.reason,
            tuple(_choice(value) for value in ("accept", "acceptForSession", "decline", "cancel")),
            grant_root=change.grant_root,
            native=native(params),
        )
    if method == "item/permissions/requestApproval":
        permission = decode(wire.PermissionsRequestApprovalParams, params)
        permissions = obj(params["permissions"])
        if set(permissions) - {"fileSystem", "network"}:
            raise UnsupportedError("Unknown native permission family")
        # Preserve the exact requested profile. The generated schema validates
        # structure; our interaction policy decides which grants may be offered.
        choices = (
            ApprovalChoice("decline", "turn", native({"permissions": {}, "scope": "turn"})),
            ApprovalChoice("permissions", "turn", native({"permissions": permissions, "scope": "turn"})),
            ApprovalChoice("permissions", "session", native({"permissions": permissions, "scope": "session"})),
        )
        return ApprovalRequest(
            ref,
            run_id,
            str(identity),
            "permissions",
            permission.item_id,
            permission.reason,
            choices,
            cwd=permission.cwd,
            native=native(params),
        )
    raise UnsupportedError("Unsupported native approval method")


def approval_response(request: ApprovalRequest, choice: ApprovalChoice) -> dict[str, JSONValue]:
    if choice not in request.choices:
        raise ProtocolError("Handler must return an offered approval choice unchanged")
    if request.kind == "permissions":
        assert choice.native is not None
        response = obj(choice.native.decode())
        decode(wire.PermissionsRequestApprovalResponse, response)
        return response
    decision = choice.kind if choice.native is None else choice.native.decode()
    if request.kind == "command":
        decode(wire.CommandExecutionRequestApprovalResponse, {"decision": decision})
    else:
        decode(wire.FileChangeRequestApprovalResponse, {"decision": decision})
    return {"decision": decision}


def default_choice(request: ApprovalRequest) -> ApprovalChoice:
    for kind in ("decline", "cancel"):
        for choice in request.choices:
            if choice.kind == kind:
                return choice
    raise UnsupportedError("Native request offers no non-approval decision")


def questions(ref: ThreadRef, run_id: str, identity: RequestID, params: dict[str, JSONValue]) -> QuestionRequest:
    prompt = decode(wire.ToolRequestUserInputParams, params)
    result = tuple(
        Question(
            question.id,
            question.header,
            question.question,
            None
            if question.options is None
            else tuple(QuestionOption(option.label, option.description) for option in question.options),
            question.is_other,
            question.is_secret,
        )
        for question in prompt.questions
    )
    if len({q.id for q in result}) != len(result):
        raise ProtocolError("Duplicate question identities")
    return QuestionRequest(ref, run_id, str(identity), prompt.item_id, result, prompt.is_blocking)


def question_response(request: QuestionRequest, response: QuestionResponse) -> dict[str, JSONValue]:
    answers: dict[str, wire.ToolRequestUserInputAnswer] = {}
    expected = {q.id: q for q in request.questions}
    for answer in response.answers:
        if answer.question_id not in expected or answer.question_id in answers:
            raise ProtocolError("Question response has unknown or duplicate identity")
        question = expected[answer.question_id]
        if question.options is not None and not question.allow_other:
            offered = {option.label for option in question.options}
            if any(value not in offered for value in answer.values):
                raise ProtocolError("Question response uses an unavailable option")
        answers[answer.question_id] = wire.ToolRequestUserInputAnswer(answers=list(answer.values))
    if set(answers) != set(expected):
        raise ProtocolError("Question response must answer exactly the requested questions")
    return encode(wire.ToolRequestUserInputResponse(answers=answers))
