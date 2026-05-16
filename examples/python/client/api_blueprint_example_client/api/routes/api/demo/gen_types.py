from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AbcQuery:
    arg1: bool | None = None
    arg3: str | None = None
    arg2: float | None = None


@dataclass
class AbcResponse:
    bc: str | None = None
    a: int | None = None
    efg: float | None = None
    hijk: list[Any] | None = None
    lmnop: list[Any] | None = None
    enum_color: Any | None = None
    enum_status: Any | None = None
    enum_list: list[Any] | None = None


@dataclass
class TestPostJSON:
    req1: str | None = None
    req2: int | None = None


@dataclass
class TestPostResponse:
    list: list[Any] | None = None
    map: dict[Any, Any] | None = None


@dataclass
class PutDemoQuery:
    arg1: str | None = None
    arg2: float | None = None
    arg3: str | None = None


@dataclass
class PutDemoJSON:
    req1: str | None = None
    req2: int | None = None


@dataclass
class PutDemoResponse:
    list: list[Any] | None = None
    anon_kv: dict[str, Any] | None = None


@dataclass
class DeleteQuery:
    arg1: str | None = None
    arg2: float | None = None


@dataclass
class DeleteResponse:
    list: list[Any] | None = None
    anon_list: list[Any] | None = None


@dataclass
class WsQuery:
    hello: dict[Any, Any] | None = None
    amap: list[Any] | None = None


@dataclass
class SweepEventsOpen:
    run_id: str | None = None
    replay_from: str | None = None


@dataclass
class AssistantSessionOpen:
    session_id: str | None = None


@dataclass
class PostDeprecatedJSON:
    req1: str | None = None
    req2: int | None = None


@dataclass
class PostDeprecatedResponse:
    list: list[Any] | None = None


@dataclass
class RawResponse:
    list: list[Any] | None = None
    list2: dict[Any, Any] | None = None


@dataclass
class ErrorDemoQuery:
    mode: str | None = None


@dataclass
class ErrorDemoResponse:
    status: str | None = None
