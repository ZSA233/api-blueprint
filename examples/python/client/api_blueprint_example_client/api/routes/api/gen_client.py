from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from ...runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


def _to_mapping(value: object) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return {key: item for key, item in asdict(value).items() if item is not None}
    raise TypeError(f"expected mapping or dataclass request model, got {type(value).__name__}")


def _from_mapping(model_type, value):
    if value is None or isinstance(value, model_type):
        return value
    if isinstance(value, Mapping):
        return model_type(**{key: value.get(key) for key in model_type.__dataclass_fields__})
    return value


class ApiClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    def connect_ws(
        self,
        headers: dict[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> ApiSocketBridge[Any, Any]:
        return self._transport.connect_socket(
            route_id="api.api.ws.ws",
            path="/api/ws",
            headers=headers,
            protocols=protocols,
        )
