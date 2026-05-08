from __future__ import annotations

from typing import Any

from ....runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


class DemoClient:
    def __init__(self, transport: ApiClientTransport):
        self._transport = transport

    async def abc(
        self,
        query: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'ApiDemoA'
        return await self._transport.request(
            "GET",
            "/api/demo/abc",
            query=query,
            response_type=response_type,
        )

    async def test_post(
        self,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'RSP_TestPost'
        return await self._transport.request(
            "POST",
            "/api/demo/test_post",
            json=json,
            response_type=response_type,
        )

    async def z1put(
        self,
        query: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'RSP_Func1put'
        return await self._transport.request(
            "PUT",
            "/api/demo/1put",
            query=query,
            json=json,
            response_type=response_type,
        )

    async def delete(
        self,
        query: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'RSP_Delete'
        return await self._transport.request(
            "DELETE",
            "/api/demo/delete$",
            query=query,
            response_type=response_type,
        )

    def connect_ws(
        self,
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> ApiSocketBridge[Any, Any]:
        return self._transport.connect_socket(
            route_id="api.demo.ws.ws",
            path="/api/demo/ws",
            query=query,
            headers=headers,
            protocols=protocols,
        )

    def subscribe_sweep_events(
        self,
        open_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiStreamBridge[Any, Any]:
        return self._transport.open_stream(
            route_id="api.demo.stream.sweepevents",
            path="/api/demo/sweep-events",
            open_data=open_data,
            headers=headers,
        )

    def open_assistant_session(
        self,
        open_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> ApiChannelBridge[Any, Any, Any]:
        return self._transport.open_channel(
            route_id="api.demo.channel.assistantsession",
            path="/api/demo/assistant-session",
            open_data=open_data,
            headers=headers,
            protocols=protocols,
        )

    async def post_deprecated(
        self,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response_type: str | None = 'RSP_PostDeprecated'
        return await self._transport.request(
            "POST",
            "/api/demo/post_deprecated",
            json=json,
            response_type=response_type,
        )

    async def raw(self) -> Any:
        response_type: str | None = 'RSP_Raw'
        return await self._transport.request(
            "POST",
            "/api/demo/raw",
            response_type=response_type,
        )

    async def map_model(self) -> Any:
        response_type: str | None = 'RSP_MapModel'
        return await self._transport.request(
            "POST",
            "/api/demo/map_model",
            response_type=response_type,
        )
