"""Regression coverage for schema-to-Python semantics at the wire boundary."""

import json
from pathlib import Path

import pytest

from ohkit.backends.codex import _generated as wire
from ohkit.backends.codex._wire import decode, encode
from ohkit.errors import ProtocolError

FIXTURES = Path(__file__).parent / "fixtures"


def test_aliases_and_omission_are_exact():
    params = wire.TurnSteerParams(
        thread_id="thread",
        expected_turn_id="turn",
        client_user_message_id="client",
        input=[wire.TextUserInput(type="text", text="hello")],
    )
    assert encode(params) == {
        "threadId": "thread",
        "expectedTurnId": "turn",
        "clientUserMessageId": "client",
        "input": [{"type": "text", "text": "hello"}],
    }
    assert encode(wire.ThreadStartParams()) == {}
    assert encode(wire.ThreadStartParams(model=None)) == {"model": None}
    assert encode(wire.ThreadStartParams(model=None), exclude_none=True) == {}


def test_required_nullable_is_not_optional():
    raw = json.loads((FIXTURES / "thread.json").read_text())
    assert raw["thread"]["projectId"] is None
    assert encode(decode(wire.ThreadStartResponse, raw)) == raw
    del raw["thread"]["projectId"]
    with pytest.raises(ProtocolError):
        decode(wire.ThreadStartResponse, raw)


def test_required_initialize_fields_are_validated():
    raw = json.loads((FIXTURES / "initialize.json").read_text())
    assert encode(decode(wire.InitializeResponse, raw)) == raw
    raw["platformOs"] = None
    with pytest.raises(ProtocolError):
        decode(wire.InitializeResponse, raw)


def test_defaults_do_not_inject_fields_or_admit_null():
    raw = {"id": "q", "header": "Header", "question": "Pick one"}
    value = decode(wire.ToolRequestUserInputQuestion, raw)
    assert value.is_other is False and value.is_secret is False
    assert encode(value) == raw
    for name in ("isOther", "isSecret"):
        with pytest.raises(ProtocolError):
            decode(wire.ToolRequestUserInputQuestion, {**raw, name: None})
    text = decode(wire.TextUserInput, {"type": "text", "text": "hi"})
    assert text.text_elements == []
    assert encode(text) == {"type": "text", "text": "hi"}
    with pytest.raises(ProtocolError):
        decode(wire.TextUserInput, {"type": "text", "text": "hi", "text_elements": None})


@pytest.mark.parametrize(
    "image",
    [
        {"type": "image", "url": "https://example.test/image.png"},
        {"type": "image", "fileId": "file-1"},
        {"type": "image", "url": "https://example.test/image.png", "fileId": "file-1"},
        {"type": "localImage", "path": "/native/image.png"},
    ],
)
def test_input_union_preserves_native_image_alternatives(image):
    raw = {"threadId": "thread", "input": [image]}
    assert encode(decode(wire.TurnStartParams, raw)) == raw


@pytest.mark.parametrize("bad", [True, "1", 1.5])
def test_strict_native_integers(bad):
    with pytest.raises(ProtocolError):
        decode(
            wire.TokenUsageBreakdown,
            {
                "cachedInputTokens": 0,
                "inputTokens": bad,
                "outputTokens": 0,
                "reasoningOutputTokens": 0,
                "totalTokens": 0,
            },
        )


def test_additive_fields_and_open_error_info_survive():
    raw = {
        "turn": {
            "id": "turn",
            "items": [],
            "status": "failed",
            "error": {
                "message": "failed",
                "codexErrorInfo": {"futureFailure": {"code": 2}},
            },
            "future": {"nested": [None, True]},
        }
    }
    assert encode(decode(wire.TurnStartResponse, raw)) == raw


def test_validation_error_does_not_disclose_native_values():
    private = "private-native-input"
    with pytest.raises(ProtocolError) as caught:
        decode(wire.TurnInterruptParams, {"threadId": private, "turnId": {"secret": private}})
    assert str(caught.value) == "Malformed native TurnInterruptParams"
    assert private not in str(caught.value)
    assert caught.value.__suppress_context__


def test_no_discriminator_default_is_invented():
    with pytest.raises(ProtocolError):
        decode(wire.TextUserInput, {"text": "missing type"})


def test_numeric_bounds_and_mutable_defaults_follow_schema():
    with pytest.raises(ProtocolError):
        decode(wire.ByteRange, {"start": -1, "end": 0})
    first = wire.TextUserInput(type="text", text="first")
    second = wire.TextUserInput(type="text", text="second")
    assert first.text_elements is not second.text_elements


def test_thread_session_id_is_required_nonnullable():
    raw = json.loads((FIXTURES / "thread.json").read_text())["thread"]
    raw["sessionId"] = None
    with pytest.raises(ProtocolError):
        decode(wire.Thread, raw)
    del raw["sessionId"]
    with pytest.raises(ProtocolError):
        decode(wire.Thread, raw)


def test_native_decoder_does_not_accept_python_names_as_wire_aliases():
    with pytest.raises(ProtocolError):
        decode(wire.TurnSteerResponse, {"turn_id": "turn"})
    raw = {"fileSystem": {"glob_scan_max_depth": 2}}
    value = decode(wire.RequestPermissionProfile, raw)
    assert value.file_system.glob_scan_max_depth is None
    assert value.file_system.model_extra == {"glob_scan_max_depth": 2}
    # Internal construction remains Pythonic; raw approvals are retained outside
    # model serialization to avoid Pydantic fields_set/extra-name collisions.
    assert encode(wire.TurnSteerResponse(turn_id="turn")) == {"turnId": "turn"}
