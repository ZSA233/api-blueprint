from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI

from api_blueprint_example_server.alt.transports.http.server import create_router as create_alt_router
from api_blueprint_example_server.api.runtime.errors import ApiError, ApiErrorPayload, ApiToastPayload
from api_blueprint_example_server.api.transports.http.server import create_router as create_api_router


app = FastAPI()


class DemoService:
    async def test_post(self, json: dict[str, Any] | None = None) -> dict[str, Any]:
        json = json or {}
        return {
            "list": ["test_post", json.get("req1")],
            "map": {"req2": {"haha": json.get("req2")}},
        }

    async def form_submit(self, form: dict[str, Any] | None = None) -> dict[str, Any]:
        form = form or {}
        return {
            "summary": form.get("title"),
            "count": int(form.get("count") or 0),
            "enabled": _bool_value(form.get("enabled")),
        }

    async def put_demo(
        self,
        query: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = query or {}
        json = json or {}
        arg2 = float(query.get("arg2") or 0)
        req2 = int(json.get("req2") or 0)
        return {
            "list": [query.get("arg1"), json.get("req1")],
            "anon_kv": {"kv1": req2, "kv2": [arg2, float(req2)]},
        }

    async def error_demo(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        mode = (query or {}).get("mode") or "ok"
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
        return {"status": "ok"}

    async def sweep_events(
        self,
        open_data: dict[str, Any] | None = None,
        stream: Any = None,
    ) -> None:
        await stream.send({"type": "state", "data": {"status": f"python sweep {(open_data or {}).get('run_id')}"}})
        await stream.close({"code": 1000, "reason": "example stream complete"})

    async def assistant_session(
        self,
        open_data: dict[str, Any] | None = None,
        channel: Any = None,
    ) -> None:
        session_id = (open_data or {}).get("session_id")
        first = await channel.receive()
        if first.get("type") == "input":
            text = (first.get("data") or {}).get("text")
            await channel.send({"type": "delta", "data": {"text": f"{session_id}:{text}"}})
        elif first.get("type") == "cancel":
            await channel.close({"code": 1000, "reason": (first.get("data") or {}).get("reason")})
            return
        second = await channel.receive()
        if second.get("type") == "cancel":
            await channel.close({"code": 1000, "reason": (second.get("data") or {}).get("reason")})


class BinaryService:
    async def packet(
        self,
        query: dict[str, Any] | None = None,
        binary: bytes | None = None,
    ) -> dict[str, Any]:
        packet = parse_packet(binary or b"")
        return {
            "trace": (query or {}).get("trace"),
            "version": packet.version,
            "item_count": len(packet.item_ids),
            "payload": packet.payload,
            "score_sum": round(packet.score_sum),
            "first_label": packet.first_label,
            "item_ids": packet.item_ids,
            "checksum": packet.checksum,
        }


class HelloService:
    async def string(self) -> dict[str, Any]:
        return {}

    async def hello_way(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"echo": (query or {}).get("arg1")}


class ConflictService:
    async def default(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"default": "api-default", "class_": (query or {}).get("class_"), "enum": "default"}


class AltConflictService:
    async def default(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"default": "alt-default", "class_": (query or {}).get("class_"), "enum": "class"}


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


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    addr = os.environ.get("API_BLUEPRINT_EXAMPLE_ADDR", "127.0.0.1:0")
    host, _, port = addr.partition(":")
    uvicorn.run(app, host=host or "127.0.0.1", port=int(port or "0"), log_level="warning")
