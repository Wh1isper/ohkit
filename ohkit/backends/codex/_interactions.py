"""Lossless offered decisions; callers cannot manufacture wider native grants."""

from ..._json import array, boolean, native, obj, optional_string, string, strings
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
from ._rpc import RequestID


def _choice(value: JSONValue) -> ApprovalChoice:
    if isinstance(value, str):
        match value:
            case "accept":
                return ApprovalChoice("accept", "action")
            case "acceptForSession":
                return ApprovalChoice("acceptForSession", "session")
            case "decline":
                return ApprovalChoice("decline", "action")
            case "cancel":
                return ApprovalChoice("cancel", "action")
            case _:
                raise UnsupportedError("Unknown native approval decision")
    decision = obj(value)
    if set(decision) == {"acceptWithExecpolicyAmendment"}:
        strings(obj(decision["acceptWithExecpolicyAmendment"])["execpolicy_amendment"])
        return ApprovalChoice("execpolicy", "persistent", native(decision))
    if set(decision) == {"applyNetworkPolicyAmendment"}:
        amendment = obj(obj(decision["applyNetworkPolicyAmendment"])["network_policy_amendment"])
        string(amendment["host"])
        if amendment["action"] not in ("allow", "deny"):
            raise UnsupportedError("Unknown network policy action")
        return ApprovalChoice("network", "persistent", native(decision))
    raise UnsupportedError("Unrepresentable native approval decision")


def _command_choices(params: dict[str, JSONValue]) -> tuple[ApprovalChoice, ...]:
    offered = params.get("availableDecisions")
    if offered is not None:
        return tuple(_choice(value) for value in array(offered))
    # Pinned TUI approval_events.rs default_available_decisions, not all
    # values the response enum can deserialize. Wider choices would grant
    # authority the native prompt did not offer.
    defaults: list[JSONValue] = ["accept"]
    if params.get("networkApprovalContext") is not None:
        defaults.append("acceptForSession")
        amendments = params.get("proposedNetworkPolicyAmendments")
        if amendments is not None:
            for value in array(amendments):
                amendment = obj(value)
                if amendment.get("action") == "allow":
                    defaults.append({"applyNetworkPolicyAmendment": {"network_policy_amendment": amendment}})
                    break
    elif params.get("additionalPermissions") is None:
        amendment = params.get("proposedExecpolicyAmendment")
        if amendment is not None:
            strings(amendment)
            defaults.append({"acceptWithExecpolicyAmendment": {"execpolicy_amendment": amendment}})
    defaults.append("cancel")
    return tuple(_choice(value) for value in defaults)


def approval(
    ref: ThreadRef, run_id: str, identity: RequestID, method: str, params: dict[str, JSONValue]
) -> ApprovalRequest:
    item_id = string(params["itemId"])
    reason = optional_string(params.get("reason"))
    choices: tuple[ApprovalChoice, ...]
    if method == "item/commandExecution/requestApproval":
        choices = _command_choices(params)
        return ApprovalRequest(
            ref,
            run_id,
            str(identity),
            "command",
            item_id,
            reason,
            choices,
            command=optional_string(params.get("command")),
            cwd=optional_string(params.get("cwd")),
            native=native(params),
        )
    if method == "item/fileChange/requestApproval":
        choices = tuple(_choice(value) for value in ("accept", "acceptForSession", "decline", "cancel"))
        return ApprovalRequest(
            ref,
            run_id,
            str(identity),
            "file_change",
            item_id,
            reason,
            choices,
            grant_root=optional_string(params.get("grantRoot")),
            native=native(params),
        )
    if method == "item/permissions/requestApproval":
        permissions = obj(params["permissions"])
        if set(permissions) - {"fileSystem", "network"}:
            raise UnsupportedError("Unknown native permission family")
        # Response objects preserve the requested profile exactly. No subset or
        # invented grants: choose deny, exact turn grant, or exact session grant.
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
            item_id,
            reason,
            choices,
            cwd=string(params["cwd"]),
            native=native(params),
        )
    raise UnsupportedError("Unsupported native approval method")


def approval_response(request: ApprovalRequest, choice: ApprovalChoice) -> dict[str, JSONValue]:
    if choice not in request.choices:
        raise ProtocolError("Handler must return an offered approval choice unchanged")
    if request.kind == "permissions":
        assert choice.native is not None
        return obj(choice.native.decode())
    if choice.native is not None:
        return {"decision": choice.native.decode()}
    return {"decision": choice.kind}


def default_choice(request: ApprovalRequest) -> ApprovalChoice:
    for kind in ("decline", "cancel"):
        for choice in request.choices:
            if choice.kind == kind:
                return choice
    raise UnsupportedError("Native request offers no non-approval decision")


def questions(ref: ThreadRef, run_id: str, identity: RequestID, params: dict[str, JSONValue]) -> QuestionRequest:
    result: list[Question] = []
    for value in array(params["questions"]):
        question = obj(value)
        offered = question.get("options")
        options = (
            None
            if offered is None
            else tuple(
                QuestionOption(string(obj(option)["label"]), string(obj(option)["description"]))
                for option in array(offered)
            )
        )
        result.append(
            Question(
                string(question["id"]),
                string(question["header"]),
                string(question["question"]),
                options,
                boolean(question.get("isOther", False)),
                boolean(question.get("isSecret", False)),
            )
        )
    if len({q.id for q in result}) != len(result):
        raise ProtocolError("Duplicate question identities")
    return QuestionRequest(
        ref, run_id, str(identity), string(params["itemId"]), tuple(result), boolean(params["isBlocking"])
    )


def question_response(request: QuestionRequest, response: QuestionResponse) -> dict[str, JSONValue]:
    answers: dict[str, JSONValue] = {}
    expected = {q.id: q for q in request.questions}
    for answer in response.answers:
        if answer.question_id not in expected or answer.question_id in answers:
            raise ProtocolError("Question response has unknown or duplicate identity")
        question = expected[answer.question_id]
        if question.options is not None and not question.allow_other:
            offered = {option.label for option in question.options}
            if any(value not in offered for value in answer.values):
                raise ProtocolError("Question response uses an unavailable option")
        answers[answer.question_id] = {"answers": list(answer.values)}
    if set(answers) != set(expected):
        raise ProtocolError("Question response must answer exactly the requested questions")
    return {"answers": answers}
