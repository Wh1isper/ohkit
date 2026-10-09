"""Shared policy for generated wire models, not public ohkit values."""

from pydantic import BaseModel, ConfigDict, ValidationError

from ..._json import loads, obj
from ...errors import ProtocolError
from ...values import JSONValue


class WireModel(BaseModel):
    # Additive native fields survive round trips; known fields never coerce.
    model_config = ConfigDict(strict=True, extra="allow", populate_by_name=True)


def decode[T: BaseModel](model: type[T], value: dict[str, JSONValue]) -> T:
    try:
        return model.model_validate(value, strict=True, by_alias=True, by_name=False)
    except ValidationError:
        # Native fields may contain private input. Never expose validation dumps.
        raise ProtocolError(f"Malformed native {model.__name__}") from None


def encode(model: BaseModel, *, exclude_none: bool = False) -> dict[str, JSONValue]:
    # Preserve explicit null versus omission, including unknown native fields.
    return obj(loads(model.model_dump_json(by_alias=True, exclude_unset=True, exclude_none=exclude_none)))
