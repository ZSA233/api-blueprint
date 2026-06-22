from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import Any, Protocol, runtime_checkable


ProtocolCatalog = dict[str, Any]
ProtocolDocsPluginFn = Callable[[Mapping[str, Any]], Mapping[str, Any] | None]


@runtime_checkable
class ProtocolDocsPlugin(Protocol):
    name: str

    def build_protocol_interactions(self, catalog: Mapping[str, Any]) -> Mapping[str, Any] | None:
        ...


def load_protocol_docs_plugins(plugin_specs: Sequence[str]) -> tuple[ProtocolDocsPlugin | ProtocolDocsPluginFn, ...]:
    return tuple(_load_protocol_docs_plugin(spec) for spec in plugin_specs)


def apply_protocol_docs_plugins(
    catalog: Mapping[str, Any],
    plugins: Sequence[ProtocolDocsPlugin | ProtocolDocsPluginFn] = (),
) -> ProtocolCatalog:
    result = copy.deepcopy(dict(catalog))
    result["plugins"] = [{"name": "metadata-interactions"}]

    interactions: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, plugin in enumerate((metadata_interaction_plugin, *plugins)):
        plugin_result = _call_protocol_docs_plugin(plugin, result)
        if plugin_result is None:
            continue
        plugin_name = _plugin_name(plugin)
        if index > 0:
            result["plugins"].append({"name": plugin_name})
        for item in plugin_result.get("interactions") or []:
            if isinstance(item, Mapping):
                interactions.append(_json_safe_mapping(item))
        for item in plugin_result.get("warnings") or []:
            warnings.append(str(item))

    result["interactions"] = _dedupe_interactions(interactions)
    result["unpaired_messages"] = _unpaired_messages(result, result["interactions"])
    if warnings:
        result["warnings"] = warnings
    _attach_route_interaction_refs(result)
    return result


def metadata_interaction_plugin(catalog: Mapping[str, Any]) -> Mapping[str, Any]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for route in catalog.get("routes") or []:
        if not isinstance(route, Mapping):
            continue
        for message_ref in _iter_message_refs(route):
            metadata = message_ref.get("metadata") if isinstance(message_ref.get("metadata"), Mapping) else {}
            interaction_key = _first_string(metadata, "interaction", "interaction_id")
            if not interaction_key:
                continue
            route_id = str(message_ref["route_id"])
            group_key = (route_id, interaction_key)
            interaction = grouped.get(group_key)
            if interaction is None:
                interaction = _new_interaction(route, interaction_key, message_ref)
                grouped[group_key] = interaction
            _add_message_to_interaction(interaction, message_ref)

    return {"interactions": list(grouped.values())}


def _load_protocol_docs_plugin(spec: str) -> ProtocolDocsPlugin | ProtocolDocsPluginFn:
    if not spec or not spec.strip():
        raise ValueError("protocol_docs_plugins entries must be non-empty import paths")
    module_name, separator, attr_name = spec.partition(":")
    module = import_module(module_name)
    target = getattr(module, attr_name or "plugin") if separator else getattr(module, "plugin")
    if callable(target) and not _is_plugin_object(target):
        try:
            created = target()
        except TypeError:
            return target
        if created is not None:
            return created
    return target


def _is_plugin_object(value: object) -> bool:
    return hasattr(value, "build_protocol_interactions")


def _call_protocol_docs_plugin(
    plugin: ProtocolDocsPlugin | ProtocolDocsPluginFn,
    catalog: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    if hasattr(plugin, "build_protocol_interactions"):
        return plugin.build_protocol_interactions(catalog)  # type: ignore[union-attr]
    if callable(plugin):
        return plugin(catalog)
    raise TypeError(f"protocol docs plugin {plugin!r} is not callable")


def _plugin_name(plugin: ProtocolDocsPlugin | ProtocolDocsPluginFn) -> str:
    explicit = getattr(plugin, "name", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    return getattr(plugin, "__name__", plugin.__class__.__name__)


def _new_interaction(
    route: Mapping[str, Any],
    interaction_key: str,
    message_ref: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = message_ref.get("metadata") if isinstance(message_ref.get("metadata"), Mapping) else {}
    return {
        "id": f"{route.get('route_id') or route.get('id')}:{interaction_key}",
        "key": interaction_key,
        "name": (
            _first_string(metadata, "interaction_name", "name")
            or str(message_ref.get("name") or message_ref.get("variant_key") or interaction_key)
        ),
        "route_id": route.get("route_id") or route.get("id"),
        "kind": route.get("kind"),
        "root": route.get("root"),
        "group": route.get("group"),
        "group_path": route.get("group_path"),
        "path": route.get("path"),
        "tags": list(route.get("tags") or []),
        "summary": route.get("summary"),
        "description": _first_string(metadata, "interaction_description", "description") or route.get("description"),
        "request": None,
        "responses": [],
        "errors": [],
        "pushes": [],
        "opens": [],
        "closes": [],
        "messages": [],
        "metadata": {"source": "metadata", "interaction": interaction_key},
    }


def _add_message_to_interaction(interaction: dict[str, Any], message_ref: Mapping[str, Any]) -> None:
    message = _json_safe_mapping(message_ref)
    role = _message_role(message)
    interaction["messages"].append(message)
    if role == "request" and interaction.get("request") is None:
        interaction["request"] = message
    elif role in {"response", "ack"}:
        interaction["responses"].append(message)
    elif role == "error":
        interaction["errors"].append(message)
    elif role == "push":
        interaction["pushes"].append(message)
    elif role == "open":
        interaction["opens"].append(message)
    elif role == "close":
        interaction["closes"].append(message)


def _message_role(message_ref: Mapping[str, Any]) -> str:
    metadata = message_ref.get("metadata") if isinstance(message_ref.get("metadata"), Mapping) else {}
    explicit = _first_string(metadata, "role")
    if explicit:
        return explicit.strip().lower()
    direction = str(message_ref.get("direction") or "")
    if direction == "client":
        return "request"
    if direction == "server":
        return "response"
    if direction in {"open", "close"}:
        return direction
    return "message"


def _iter_message_refs(route: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for message in route.get("messages") or []:
        if not isinstance(message, Mapping):
            continue
        for variant in message.get("variants") or []:
            if not isinstance(variant, Mapping):
                continue
            metadata = variant.get("metadata") if isinstance(variant.get("metadata"), Mapping) else {}
            refs.append(
                {
                    "route_id": route.get("route_id") or route.get("id"),
                    "kind": route.get("kind"),
                    "group": route.get("group"),
                    "group_path": route.get("group_path"),
                    "path": route.get("path"),
                    "tags": list(route.get("tags") or []),
                    "direction": message.get("direction"),
                    "message": message.get("name"),
                    "variant_key": variant.get("key"),
                    "model": variant.get("model"),
                    "op": variant.get("op") if "op" in variant else metadata.get("op"),
                    "name": variant.get("name") or metadata.get("name") or variant.get("key"),
                    "description": variant.get("description") or metadata.get("description"),
                    "auth": variant.get("auth") or metadata.get("auth"),
                    "example": variant.get("example") if "example" in variant else metadata.get("example"),
                    "metadata": _json_safe_mapping(metadata),
                }
            )
    return refs


def _dedupe_interactions(interactions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for interaction in interactions:
        item = _json_safe_mapping(interaction)
        interaction_id = str(item.get("id") or "")
        if not interaction_id or interaction_id in seen:
            continue
        seen.add(interaction_id)
        result.append(item)
    return result


def _unpaired_messages(catalog: Mapping[str, Any], interactions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    paired = {
        _message_identity(message)
        for interaction in interactions
        for message in _interaction_messages(interaction)
    }
    result: list[dict[str, Any]] = []
    for route in catalog.get("routes") or []:
        if not isinstance(route, Mapping):
            continue
        for message in _iter_message_refs(route):
            if _message_identity(message) not in paired:
                result.append(message)
    return result


def _interaction_messages(interaction: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for field in ("messages", "responses", "errors", "pushes", "opens", "closes"):
        values = interaction.get(field)
        if isinstance(values, list):
            result.extend(value for value in values if isinstance(value, Mapping))
    request = interaction.get("request")
    if isinstance(request, Mapping):
        result.append(request)
    return result


def _message_identity(message: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(message.get("route_id") or ""),
        str(message.get("direction") or ""),
        str(message.get("message") or ""),
        str(message.get("variant_key") or ""),
        str(message.get("model") or ""),
        str(message.get("op") or ""),
    )


def _attach_route_interaction_refs(catalog: ProtocolCatalog) -> None:
    by_route: dict[str, list[str]] = {}
    for interaction in catalog.get("interactions") or []:
        if not isinstance(interaction, Mapping):
            continue
        route_id = str(interaction.get("route_id") or "")
        interaction_id = str(interaction.get("id") or "")
        if route_id and interaction_id:
            by_route.setdefault(route_id, []).append(interaction_id)
    for route in catalog.get("routes") or []:
        if isinstance(route, dict):
            route["interactions"] = by_route.get(str(route.get("route_id") or route.get("id") or ""), [])


def _first_string(metadata: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)
