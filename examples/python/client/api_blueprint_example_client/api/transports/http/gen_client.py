from __future__ import annotations

from typing import Any, Mapping

import httpx

from ...runtime.client import ApiChannelBridge, ApiClientTransport, ApiSocketBridge, ApiStreamBridge


class HttpClientTransport(ApiClientTransport):
    def __init__(
        self,
        base_url: str = "http://localhost:2333",
        *,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json: Any = None,
        form: Mapping[str, Any] | None = None,
        binary: bytes | None = None,
        open_data: Mapping[str, Any] | None = None,
        response_type: str | None = None,
    ) -> Any:
        request_kwargs: dict[str, Any] = {}
        if query:
            request_kwargs["params"] = {key: value for key, value in query.items() if value is not None}
        if json is not None:
            request_kwargs["json"] = json
        elif form is not None:
            request_kwargs["data"] = form
        elif binary is not None:
            request_kwargs["content"] = binary
        elif open_data is not None:
            request_kwargs["json"] = open_data

        response = await self._client.request(method, self._url(path), **request_kwargs)
        response.raise_for_status()
        if not response.content:
            return None

        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type == "application/json" or content_type.endswith("+json"):
            return response.json()
        if response_type == "bytes":
            return response.content
        return response.text

    def connect_socket(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> ApiSocketBridge[Any, Any]:
        raise NotImplementedError("HTTP WebSocket client transport is not implemented by the default httpx adapter")

    def open_stream(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        open_data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ApiStreamBridge[Any, Any]:
        raise NotImplementedError("HTTP stream client transport is not implemented by the default httpx adapter")

    def open_channel(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        open_data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> ApiChannelBridge[Any, Any, Any]:
        raise NotImplementedError("HTTP channel client transport is not implemented by the default httpx adapter")

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        if not self.base_url:
            return normalized_path
        return f"{self.base_url}{normalized_path}"
