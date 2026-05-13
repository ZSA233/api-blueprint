from __future__ import annotations

from typing import Any, AsyncIterator, Generic, Mapping, Protocol, TypeVar

from .binary import ApiBinaryBody


RecvT = TypeVar("RecvT")
SendT = TypeVar("SendT")
CloseT = TypeVar("CloseT")


class ApiClientTransport(Protocol):
    async def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json: Any = None,
        form: Mapping[str, Any] | None = None,
        binary: bytes | ApiBinaryBody | None = None,
        open_data: Mapping[str, Any] | None = None,
        response_type: str | None = None,
    ) -> Any:
        ...

    def connect_socket(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> "ApiSocketBridge[Any, Any]":
        ...

    def open_stream(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        open_data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> "ApiStreamBridge[Any, Any]":
        ...

    def open_channel(
        self,
        *,
        route_id: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        open_data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        protocols: tuple[str, ...] = (),
    ) -> "ApiChannelBridge[Any, Any, Any]":
        ...


class ApiSocketBridge(Protocol, Generic[SendT, RecvT]):
    async def send(self, message: SendT) -> None:
        ...

    def __aiter__(self) -> AsyncIterator[RecvT]:
        ...

    async def close(self) -> None:
        ...


class ApiStreamBridge(Protocol, Generic[RecvT, CloseT]):
    def __aiter__(self) -> AsyncIterator[RecvT]:
        ...

    async def close(self) -> CloseT | None:
        ...


class ApiChannelBridge(ApiStreamBridge[RecvT, CloseT], Protocol, Generic[RecvT, SendT, CloseT]):
    async def send(self, message: SendT) -> None:
        ...
