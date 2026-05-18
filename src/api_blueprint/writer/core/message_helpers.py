from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

MessageDirection = Literal["server", "client"]


@dataclass(frozen=True)
class MessageVariantDescriptor:
    key: str
    model: str


@dataclass(frozen=True)
class MessageHelperDescriptor:
    name: str
    direction: MessageDirection
    variants: tuple[MessageVariantDescriptor, ...]


def named_message_helpers_from_route(route: Mapping[str, Any]) -> tuple[MessageHelperDescriptor, ...]:
    connection = route.get("connection")
    if not isinstance(connection, Mapping):
        return ()
    helpers: list[MessageHelperDescriptor] = []
    for field, direction in (("server_message", "server"), ("client_message", "client")):
        helper = named_message_helper_from_contract(connection.get(field), direction=direction)
        if helper is not None:
            helpers.append(helper)
    return tuple(helpers)


def named_message_helper_from_contract(
    contract: object,
    *,
    direction: MessageDirection,
) -> MessageHelperDescriptor | None:
    if not isinstance(contract, Mapping):
        return None
    name = contract.get("name")
    if not isinstance(name, str) or not name:
        return None
    variants = _message_variants(contract.get("variants"))
    if not variants:
        return None
    return MessageHelperDescriptor(name=name, direction=direction, variants=variants)


def unique_named_message_helpers(routes: Sequence[Mapping[str, Any]]) -> tuple[MessageHelperDescriptor, ...]:
    helpers: dict[str, MessageHelperDescriptor] = {}
    for route in routes:
        for helper in named_message_helpers_from_route(route):
            helpers.setdefault(helper.name, helper)
    return tuple(helpers.values())


def _message_variants(raw_variants: object) -> tuple[MessageVariantDescriptor, ...]:
    if not isinstance(raw_variants, list):
        return ()
    variants: list[MessageVariantDescriptor] = []
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, Mapping):
            continue
        key = raw_variant.get("key")
        model = raw_variant.get("model")
        if isinstance(key, str) and key and isinstance(model, str) and model:
            variants.append(MessageVariantDescriptor(key=key, model=model))
    return tuple(variants)
