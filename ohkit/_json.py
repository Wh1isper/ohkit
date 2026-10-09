"""One strict native JSON boundary. No Any escapes past decoding."""

import json
import math
from typing import cast

from .errors import ProtocolError
from .values import JSONValue, NativeData


def _validate(value: object) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [_validate(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        result: dict[str, JSONValue] = {}
        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                raise ProtocolError("JSON object key must be a string")
            result[key] = _validate(item)
        return result
    raise ProtocolError("Not a finite JSON value")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate JSON object key")
        result[key] = value
    return result


def loads(text: str) -> JSONValue:
    try:
        decoded: object = json.loads(text, object_pairs_hook=_pairs)
        return _validate(decoded)
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("Invalid native JSON") from exc


def dumps(value: JSONValue) -> str:
    return json.dumps(_validate(value), ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def native(value: JSONValue) -> NativeData:
    return NativeData("codex", dumps(value))


def obj(value: JSONValue) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise ProtocolError("Expected native object")
    return value


def array(value: JSONValue) -> list[JSONValue]:
    if not isinstance(value, list):
        raise ProtocolError("Expected native array")
    return value


def string(value: JSONValue) -> str:
    if not isinstance(value, str):
        raise ProtocolError("Expected native string")
    return value


def optional_string(value: JSONValue) -> str | None:
    return None if value is None else string(value)


def integer(value: JSONValue) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError("Expected native integer")
    return value


def boolean(value: JSONValue) -> bool:
    if not isinstance(value, bool):
        raise ProtocolError("Expected native boolean")
    return value


def strings(value: JSONValue) -> tuple[str, ...]:
    return tuple(string(item) for item in array(value))
