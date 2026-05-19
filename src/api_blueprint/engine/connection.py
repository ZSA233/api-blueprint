from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from api_blueprint.engine.schema import Int, Model, String


ModelRef = Union[Model, type[Model]]


class ConnectionScope(str, Enum):
    SESSION = "session"
    APP = "app"
    TOPIC = "topic"


class ConnectionDelivery(str, Enum):
    ORDERED = "ordered"
    UNORDERED = "unordered"


class ConnectionKind(str, Enum):
    RPC = "rpc"
    STREAM = "stream"
    CHANNEL = "channel"


class DefaultConnectionClose(Model):
    code = Int(description="logical close code", omitempty=True)
    reason = String(description="close reason", omitempty=True)
    error = String(description="machine-readable error key", omitempty=True)


@dataclass(frozen=True)
class MessageVariant:
    key: str
    model: ModelRef


@dataclass(frozen=True)
class MessageContract:
    name: str | None
    variants: tuple[MessageVariant, ...]

    @property
    def is_union(self) -> bool:
        return self.name is not None

    @property
    def single_model(self) -> ModelRef | None:
        if len(self.variants) != 1 or self.name is not None:
            return None
        return self.variants[0].model


def normalize_message_contract(args: tuple[object, ...], variants: dict[str, ModelRef]) -> MessageContract:
    if variants:
        if len(args) != 1 or not isinstance(args[0], str):
            raise ValueError("multi-variant messages require exactly one positional union name string")
        for key, model in variants.items():
            if not key:
                raise ValueError("message variant keys must not be empty")
            ensure_model_ref(model, label=f"message variant[{key}]")
        return MessageContract(
            name=args[0],
            variants=tuple(MessageVariant(key=key, model=model) for key, model in variants.items()),
        )

    if len(args) != 1:
        raise ValueError("single messages require exactly one model argument")
    if isinstance(args[0], str):
        raise ValueError("multi-variant messages require at least one keyword variant")
    model = args[0]
    if not _is_model_ref(model):
        raise TypeError("message contract argument must be a Model class or Model instance")
    return MessageContract(name=None, variants=(MessageVariant(key="", model=model),))


def ensure_model_ref(model: object, *, label: str) -> ModelRef:
    if not _is_model_ref(model):
        raise TypeError(f"{label} must be a Model class or Model instance")
    return model


def _is_model_ref(model: object) -> bool:
    if isinstance(model, Model):
        return True
    return isinstance(model, type) and issubclass(model, Model)
