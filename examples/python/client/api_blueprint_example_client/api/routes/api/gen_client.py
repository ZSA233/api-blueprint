from __future__ import annotations

from typing import Any

from ...runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


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
