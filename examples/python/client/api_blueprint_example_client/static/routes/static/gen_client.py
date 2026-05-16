from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from ...runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


from .gen_types import (
    DocJsonResponse,
    DochahaResponse,
)


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


class StaticClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    async def doc_json(self) -> Any:
        response_type: str | None = 'DocJsonResponse'
        payload = await self._transport.request(
            "GET",
            "/static/doc.json",
            route_id="static.static.get.docjson",
            response_type=response_type,
            response_envelope={"name": "NoEnvelope", "kind": "none", "error_identity": "none", "success_code": 0, "success_message": "ok", "fields": {}},
        )
        return _from_mapping(DocJsonResponse, payload)

    async def dochaha(self) -> Any:
        response_type: str | None = 'DochahaResponse'
        payload = await self._transport.request(
            "GET",
            "/static/dochaha",
            route_id="static.static.get.dochaha",
            response_type=response_type,
            response_envelope={"name": "NoEnvelope", "kind": "none", "error_identity": "none", "success_code": 0, "success_message": "ok", "fields": {}},
        )
        return _from_mapping(DochahaResponse, payload)
