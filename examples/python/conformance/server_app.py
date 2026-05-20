from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from api_blueprint_example_server.alt.routes.alt.conflict.gen_types import (
    DefaultQuery as AltDefaultQuery,
)
from api_blueprint_example_server.alt.routes.alt.conflict.gen_types import (
    DefaultResponse as AltDefaultResponse,
)
from api_blueprint_example_server.alt.routes.alt.conflict.gen_types import (
    KeywordEnum as AltKeywordEnum,
)
from api_blueprint_example_server.alt.transports.http.server import create_router as create_alt_router
from api_blueprint_example_server.api.routes.api.binary.gen_types import (
    AuditPacketQuery,
    AuditPacketResponse,
    PacketQuery,
    PacketResponse,
)
from api_blueprint_example_server.api.routes.api.conflict.gen_types import (
    DefaultQuery,
    DefaultResponse,
    KeywordEnum,
)
from api_blueprint_example_server.api.routes.api.demo.gen_types import (
    ANONDeleteAnonList,
    ANONFunc1putAnonKv,
    AbcQuery,
    AbcResponse,
    ApiDemoA,
    ApiDemoMap,
    ApiDemoSubA,
    AssistantCancel,
    AssistantDelta,
    AssistantInput,
    AssistantServerMessageVariants,
    AssistantSessionClose,
    AssistantSessionOpen,
    ColorEnum,
    DeleteQuery,
    DeleteResponse,
    ErrorDemoQuery,
    ErrorDemoResponse,
    FormSubmitForm,
    FormSubmitResponse,
    PostDeprecatedJSON,
    PostDeprecatedResponse,
    PutDemoJSON,
    PutDemoQuery,
    PutDemoResponse,
    RawResponse,
    StatusEnum,
    SweepEventsClose,
    SweepEventsOpen,
    SweepState,
    SweepStreamMessageVariants,
    TestPostJSON,
    TestPostResponse,
)
from api_blueprint_example_server.api.routes.api.gen_types import (
    HelloChannelClose,
    HelloChannelMessage,
    HelloChannelMsgTypeEnum,
)
from api_blueprint_example_server.api.routes.api.hello.gen_types import (
    AbcQuery as HelloAbcQuery,
)
from api_blueprint_example_server.api.routes.api.hello.gen_types import ApiHelloMap, HelloWayQuery, MapEnum
from api_blueprint_example_server.api.runtime.errors import ApiError, ApiErrorPayload, ApiToastPayload
from api_blueprint_example_server.api.transports.http.server import create_router as create_api_router
from api_blueprint_example_server.static.routes.static.gen_types import DocJsonResponse, DochahaResponse
from api_blueprint_example_server.static.transports.http.server import create_router as create_static_router


app = FastAPI()


@app.middleware("http")
async def require_demo_header(request: Request, call_next):
    if request.url.path == "/api/demo/abc" and request.headers.get("x-token") != "conformance-token":
        return JSONResponse({"detail": "missing conformance token"}, status_code=418)
    return await call_next(request)


class ApiService:
    async def hello_channel(self, channel: Any = None) -> None:
        first = await channel.receive()
        if first is not None:
            await channel.send(
                HelloChannelMessage(type=HelloChannelMsgTypeEnum.PONG, data={"source": "python"})
            )
        await channel.close(HelloChannelClose(code=1000, reason="single channel complete"))


class DemoService:
    async def abc(self, query: AbcQuery) -> AbcResponse:
        return demo_model("header-ok")

    async def test_post(self, json: TestPostJSON) -> TestPostResponse:
        req1 = json.req1
        req2 = 0 if json.req2 is None else json.req2
        return TestPostResponse(
            list=["test_post", req1],
            map={"req2": ApiDemoMap(haha=req2)},
        )

    async def form_submit(self, form: FormSubmitForm) -> FormSubmitResponse:
        return FormSubmitResponse(
            summary=form.title,
            count=0 if form.count is None else form.count,
            enabled=False if form.enabled is None else form.enabled,
        )

    async def put_demo(
        self,
        query: PutDemoQuery,
        json: PutDemoJSON,
    ) -> PutDemoResponse:
        arg1 = "" if query.arg1 is None else query.arg1
        arg2 = 0.0 if query.arg2 is None else query.arg2
        req1 = json.req1
        req2 = 0 if json.req2 is None else json.req2
        return PutDemoResponse(
            list=[arg1, req1],
            anon_kv=ANONFunc1putAnonKv(kv1=req2, kv2=[arg2, float(req2)]),
        )

    async def delete(self, query: DeleteQuery) -> DeleteResponse:
        return DeleteResponse(
            list=["" if query.arg1 is None else query.arg1],
            anon_list=[ANONDeleteAnonList(kv1=7, kv2=["xml"])],
        )

    async def post_deprecated(self, json: PostDeprecatedJSON) -> PostDeprecatedResponse:
        return PostDeprecatedResponse(list=[json.req1])

    async def raw(self) -> RawResponse:
        return RawResponse(list=["raw"], list2={1: [demo_model("raw")]})

    async def map_model(self) -> dict[int, ApiDemoMap]:
        return {1: ApiDemoMap(haha=101)}

    async def error_demo(self, query: ErrorDemoQuery) -> ErrorDemoResponse:
        mode = "ok" if query.mode is None else query.mode
        if mode == "rate_limit":
            raise ApiError(
                ApiErrorPayload(
                    id="DemoErr.RATE_LIMITED",
                    group="",
                    key="",
                    code=42901,
                    message="",
                    toast=ApiToastPayload(
                        key="demo.rate_limited",
                        level="warning",
                        default="请求过于频繁，请稍后再试",
                        text="请等待 30 秒后重试",
                    ),
                )
            )
        if mode == "unknown":
            raise ApiError(
                ApiErrorPayload(
                    id="",
                    group="",
                    key="",
                    code=70001,
                    message="example undefined business error",
                    toast=ApiToastPayload(level="error"),
                )
            )
        return ErrorDemoResponse(status="ok")

    async def sweep_events(
        self,
        open_data: SweepEventsOpen,
        stream: Any = None,
    ) -> None:
        run_id = open_data.run_id
        await stream.send(SweepStreamMessageVariants.state(SweepState(status=f"python sweep {run_id}")))
        await stream.close(SweepEventsClose(code=1000, reason="example stream complete"))

    async def assistant_session(
        self,
        open_data: AssistantSessionOpen,
        channel: Any = None,
    ) -> None:
        session_id = open_data.session_id
        first = await channel.receive()
        if first.type == "input":
            payload = AssistantInput.from_value(first.data)
            await channel.send(
                AssistantServerMessageVariants.delta(AssistantDelta(text=f"{session_id}:{payload.text}"))
            )
        elif first.type == "cancel":
            payload = AssistantCancel.from_value(first.data)
            await channel.close(AssistantSessionClose(code=1000, reason=payload.reason))
            return
        second = await channel.receive()
        if second.type == "cancel":
            payload = AssistantCancel.from_value(second.data)
            await channel.close(AssistantSessionClose(code=1000, reason=payload.reason))


class BinaryService:
    async def packet(
        self,
        query: PacketQuery,
        binary: bytes | None = None,
    ) -> PacketResponse:
        packet = parse_packet(binary or b"")
        return PacketResponse(
            trace="" if query.trace is None else query.trace,
            version=packet.version,
            item_count=len(packet.item_ids),
            payload=packet.payload,
            score_sum=round(packet.score_sum),
            first_label=packet.first_label,
            item_ids=packet.item_ids,
            checksum=packet.checksum,
        )

    async def audit_packet(
        self,
        query: AuditPacketQuery,
        binary: bytes | None = None,
    ) -> AuditPacketResponse:
        packet = parse_audit_packet(binary or b"")
        return AuditPacketResponse(
            trace="" if query.trace is None else query.trace,
            item_count=packet.item_count,
            checksum=packet.checksum,
        )


class HelloService:
    async def abc(self, query: HelloAbcQuery) -> dict[str, ApiHelloMap]:
        key = "ping" if query.type is None else query.type.value
        return {"hello": ApiHelloMap(haha=1001), key: ApiHelloMap(haha=1)}

    async def map_enum(self) -> dict[MapEnum, ApiHelloMap]:
        return {MapEnum.A: ApiHelloMap(haha=11), MapEnum.B: ApiHelloMap(haha=22)}

    async def list_enum(self) -> list[MapEnum]:
        return [MapEnum.A, MapEnum.B]

    async def string(self) -> str:
        return "hello-string"

    async def uint64(self) -> int:
        return 9007199254740991

    async def string_emun(self) -> MapEnum:
        return MapEnum.A

    async def hello_way(self, query: HelloWayQuery) -> dict[str, Any]:
        return {"echo": None if query.arg1 is None else query.arg1.value}


class StaticService:
    async def doc_json(self) -> DocJsonResponse:
        return DocJsonResponse()

    async def dochaha(self) -> DochahaResponse:
        return DochahaResponse(a="hello world")


class ConflictService:
    async def default(self, query: DefaultQuery) -> DefaultResponse:
        return DefaultResponse(
            default="api-default",
            class_="" if query.class_ is None else query.class_,
            enum=KeywordEnum.DEFAULT,
        )


class AltConflictService:
    async def default(self, query: AltDefaultQuery) -> AltDefaultResponse:
        return AltDefaultResponse(
            default="alt-default",
            class_="" if query.class_ is None else query.class_,
            enum=AltKeywordEnum.CLASS,
        )


app.include_router(
    create_api_router(
        api_service=ApiService(),
        binary_service=BinaryService(),
        conflict_service=ConflictService(),
        demo_service=DemoService(),
        hello_service=HelloService(),
    )
)
app.include_router(create_alt_router(conflict_service=AltConflictService()))
app.include_router(create_static_router(static_service=StaticService()))


@dataclass(frozen=True)
class ParsedPacket:
    version: int
    payload: str
    score_sum: float
    first_label: str
    item_ids: list[int]
    checksum: int


@dataclass(frozen=True)
class ParsedAuditPacket:
    item_count: int
    checksum: int


def demo_model(label: str) -> AbcResponse:
    return AbcResponse(
        bc=label,
        a=1,
        efg=1.5,
        hijk=[1, 2, 3],
        lmnop=[ApiDemoSubA(hello={"a": 1}, amap=[ApiDemoMap(haha=1)])],
        enum_color=ColorEnum.RED,
        enum_status=StatusEnum.RUNNING,
        enum_list=[StatusEnum.PENDING, StatusEnum.RUNNING],
    )


def parse_packet(data: bytes) -> ParsedPacket:
    offset = 0
    magic = data[offset : offset + 4].decode("utf-8")
    offset += 4
    if magic != "ABP1":
        raise ValueError(f"binary magic mismatch: {magic}")
    version, kind = struct.unpack_from("<HH", data, offset)
    offset += 4
    if kind != 1:
        raise ValueError(f"binary kind mismatch: {kind}")
    (flags,) = struct.unpack_from("<I", data, offset)
    offset += 4
    if flags & 1 == 0:
        raise ValueError(f"binary flags missing payload bit: {flags}")
    offset += 3
    short_code = _read_u24(data, offset)
    offset += 3
    if short_code != 0x010203:
        raise ValueError(f"binary short code mismatch: {short_code}")
    offset += 3
    item_count, payload_len, score_count = struct.unpack_from("<HIH", data, offset)
    offset += 8
    item_ids: list[int] = []
    first_label = ""
    for index in range(item_count):
        item_id = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        item_ids.append(item_id)
        offset += 1
        offset += 8
        label_len = data[offset]
        offset += 1
        label = data[offset : offset + label_len].decode("utf-8")
        offset += label_len
        if index == 0:
            first_label = label
    payload = data[offset : offset + payload_len].decode("utf-8")
    offset += payload_len
    score_sum = 0.0
    for _ in range(score_count):
        score_sum += struct.unpack_from("<d", data, offset)[0]
        offset += 8
    checksum = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if offset != len(data):
        raise ValueError(f"binary packet has trailing bytes: {len(data) - offset}")
    return ParsedPacket(version, payload, score_sum, first_label, item_ids, checksum)


def parse_audit_packet(data: bytes) -> ParsedAuditPacket:
    offset = 0
    (kind,) = struct.unpack_from("<H", data, offset)
    offset += 2
    if kind != 2:
        raise ValueError(f"audit kind mismatch: {kind}")
    (flags,) = struct.unpack_from("<I", data, offset)
    offset += 4
    if flags & 1 == 0:
        raise ValueError(f"audit flags missing items bit: {flags}")
    (item_count,) = struct.unpack_from("<H", data, offset)
    offset += 2
    for _ in range(item_count):
        offset += 4
        offset += 2
    (checksum,) = struct.unpack_from("<I", data, offset)
    offset += 4
    if offset != len(data):
        raise ValueError(f"audit packet has trailing bytes: {len(data) - offset}")
    return ParsedAuditPacket(item_count=item_count, checksum=checksum)


def _read_u24(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)


if __name__ == "__main__":
    addr = os.environ.get("API_BLUEPRINT_EXAMPLE_ADDR", "127.0.0.1:0")
    host, _, port = addr.partition(":")
    uvicorn.run(app, host=host or "127.0.0.1", port=int(port or "0"), log_level="warning")
