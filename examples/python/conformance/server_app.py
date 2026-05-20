from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI

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
from api_blueprint_example_server.api.routes.api.binary.gen_types import PacketQuery, PacketResponse
from api_blueprint_example_server.api.routes.api.conflict.gen_types import (
    DefaultQuery,
    DefaultResponse,
    KeywordEnum,
)
from api_blueprint_example_server.api.routes.api.demo.gen_types import (
    ANONFunc1putAnonKv,
    ApiDemoMap,
    AssistantCancel,
    AssistantDelta,
    AssistantInput,
    AssistantServerMessageVariants,
    AssistantSessionClose,
    AssistantSessionOpen,
    ErrorDemoQuery,
    ErrorDemoResponse,
    FormSubmitForm,
    FormSubmitResponse,
    PutDemoJSON,
    PutDemoQuery,
    PutDemoResponse,
    SweepEventsClose,
    SweepEventsOpen,
    SweepState,
    SweepStreamMessageVariants,
    TestPostJSON,
    TestPostResponse,
)
from api_blueprint_example_server.api.routes.api.hello.gen_types import HelloWayQuery
from api_blueprint_example_server.api.runtime.errors import ApiError, ApiErrorPayload, ApiToastPayload
from api_blueprint_example_server.api.transports.http.server import create_router as create_api_router


app = FastAPI()


class DemoService:
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


class HelloService:
    async def string(self) -> dict[str, Any]:
        return {}

    async def hello_way(self, query: HelloWayQuery) -> dict[str, Any]:
        return {"echo": None if query.arg1 is None else query.arg1.value}


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
        binary_service=BinaryService(),
        conflict_service=ConflictService(),
        demo_service=DemoService(),
        hello_service=HelloService(),
    )
)
app.include_router(create_alt_router(conflict_service=AltConflictService()))


@dataclass(frozen=True)
class ParsedPacket:
    version: int
    payload: str
    score_sum: float
    first_label: str
    item_ids: list[int]
    checksum: int


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


def _read_u24(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)


if __name__ == "__main__":
    addr = os.environ.get("API_BLUEPRINT_EXAMPLE_ADDR", "127.0.0.1:0")
    host, _, port = addr.partition(":")
    uvicorn.run(app, host=host or "127.0.0.1", port=int(port or "0"), log_level="warning")
