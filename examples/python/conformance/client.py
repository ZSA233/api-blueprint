from __future__ import annotations

import asyncio
import gzip
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))

from api_blueprint_example_client.alt.client import create_client as create_alt_client
from api_blueprint_example_client.alt.routes.alt.conflict.gen_types import DefaultQuery as AltDefaultQuery
from api_blueprint_example_client.api.client import create_client
from api_blueprint_example_client.api.gen_client import ApiClient
from api_blueprint_example_client.api.routes.api.binary.gen_types import (
    AuditPacket,
    AuditPacketBody,
    AuditPacketFlags,
    AuditPacketHeader,
    AuditPacketItem,
    AuditPacketWire,
    AuditPacketQuery,
    DemoPacket,
    DemoPacketBody,
    DemoPacketFlags,
    DemoPacketHeader,
    DemoPacketItem,
    DemoPacketWire,
    PacketQuery,
)
from api_blueprint_example_client.api.routes.api.conflict.gen_types import DefaultQuery
from api_blueprint_example_client.api.routes.api.conflict.gen_types import KeywordEnum as ApiKeywordEnum
from api_blueprint_example_client.api.routes.api.demo.gen_types import (
    AssistantSessionOpen,
    ErrorDemoQuery,
    FormSubmitForm,
    PostDeprecatedJSON,
    PutDemoJSON,
    PutDemoQuery,
    RequestOptionsQuery,
    SweepEventsOpen,
    TestPostJSON,
)
from api_blueprint_example_client.api.routes.api.gen_types import HelloChannelMsgTypeEnum
from api_blueprint_example_client.api.routes.api.hello.gen_types import AbcQuery as HelloAbcQuery
from api_blueprint_example_client.api.routes.api.hello.gen_types import MapEnum
from api_blueprint_example_client.api.routes.api.media.gen_types import MediaErrorFrameQuery, MediaPreviewForm
from api_blueprint_example_client.api.runtime.errors import (
    ApiError,
    ApiErrors,
    is_api_error,
    resolve_api_toast,
)
from api_blueprint_example_client.api.transports.http.client import HttpClientTransport
from api_blueprint_example_client.legacy.client import create_client as create_legacy_client
from api_blueprint_example_client.legacy.routes.legacy.account.gen_types import (
    AccountProfileResponse as LegacyAccountProfileResponse,
)
from api_blueprint_example_client.legacy.routes.legacy.legacy_json.gen_types import LegacyJsonCompatResponse
from api_blueprint_example_client.legacy.routes.legacy.room.gen_types import (
    RoomListResponse as LegacyRoomListResponse,
)
from api_blueprint_example_client.static.client import create_client as create_static_client


SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x01\x00\x01\x00\x00\xff\xd9"
MJPEG_BOUNDARY = b"--frame"


def scenario_set(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def build_packet() -> DemoPacket:
    return DemoPacket(
        header=DemoPacketHeader(
            flags=DemoPacketFlags.HasPayload | DemoPacketFlags.HasScores,
            short_code=0x010203,
            signed_delta=7,
            item_count=2,
            payload_len=len(b"payload-ok"),
        ),
        body=DemoPacketBody(
            items=[
                DemoPacketItem(id=11, enabled=True, value=1.25, label_len=5, label=b"alpha"),
                DemoPacketItem(id=22, enabled=False, value=2.5, label_len=4, label=b"beta"),
            ],
            payload=b"payload-ok",
            scores=[3.5, 4.5],
            checksum=12,
        ),
    )


def build_audit_packet() -> AuditPacket:
    return AuditPacket(
        header=AuditPacketHeader(
            flags=AuditPacketFlags.HasItems,
            item_count=2,
        ),
        body=AuditPacketBody(
            items=[
                AuditPacketItem(id=11, code=101),
                AuditPacketItem(id=22, code=202),
            ],
            checksum=2,
        ),
    )


def field(value, name: str):
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)


async def check_rpc(api) -> None:
    post = await api.demo.test_post(json=TestPostJSON(req1="python", req2=7))
    assert post.list == ["test_post", "python"], post
    assert field(post.map["req2"], "haha") == 7, post

    put = await api.demo.put_demo(
        query=PutDemoQuery(arg1="query", arg2=3.5),
        json=PutDemoJSON(req1="body", req2=9),
    )
    assert put.list == ["query", "body"], put
    assert field(put.anon_kv, "kv1") == 9, put


async def check_raw(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post("/api/demo/raw")
    assert response.status_code == 200, response.text


async def check_xml(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.delete("/api/demo/delete$", params={"arg1": "python-xml", "arg2": "7"})
    assert response.status_code == 200, response.text
    assert "python-xml" in response.text, response.text


async def check_static(base_url: str) -> None:
    async with create_static_client(base_url) as static_api:
        await static_api.static.doc_json()
        response = await static_api.static.dochaha()
    assert response.a == "hello world", response


async def check_header(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.get("/api/demo/abc", headers={"x-token": "conformance-token"})
    assert response.status_code == 200, response.text
    assert "header-ok" in response.text, response.text


async def check_scalar(api) -> None:
    text = await api.hello.string()
    value = await api.hello.uint64()
    assert text == "hello-string", text
    assert value == 9007199254740991, value


async def check_enum(api) -> None:
    item = await api.hello.string_emun()
    items = await api.hello.list_enum()
    assert item is MapEnum.A, item
    assert items == [MapEnum.A, MapEnum.B], items


async def check_map(api) -> None:
    model = await api.demo.map_model()
    assert model[1].haha == 101, model
    hello = await api.hello.abc(query=HelloAbcQuery(type=HelloChannelMsgTypeEnum.PING))
    assert hello["ping"].haha == 1, hello
    enum_map = await api.hello.map_enum()
    assert enum_map[MapEnum.A].haha == 11, enum_map


async def check_deprecated(api) -> None:
    response = await api.demo.post_deprecated(json=PostDeprecatedJSON(req1="python-deprecated", req2=3))
    assert response.list == ["python-deprecated"], response


async def check_form(api) -> None:
    response = await api.demo.form_submit(form=FormSubmitForm(title="python-form", count=4, enabled=True))
    assert response.summary == "python-form", response
    assert response.count == 4, response
    assert response.enabled is True, response


async def check_binary(api, base_url: str) -> None:
    response = await api.binary.packet(query=PacketQuery(trace="python-typed"), binary=build_packet())
    expected = {
        "trace": "python-typed",
        "version": 1,
        "item_count": 2,
        "payload": "payload-ok",
        "score_sum": 8,
        "first_label": "alpha",
        "item_ids": [11, 22],
        "checksum": 12,
    }
    actual = response.__dict__ if hasattr(response, "__dict__") else response
    assert actual == expected, actual

    packet_bytes = DemoPacketWire.to_binary_body(build_packet()).to_bytes()
    async with httpx.AsyncClient(base_url=base_url) as client:
        gzip_response = await client.post(
            "/api/binary/packet",
            params={"trace": "python-gzip"},
            content=gzip.compress(packet_bytes),
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "gzip",
            },
        )
        assert gzip_response.status_code == 200, gzip_response.text
        gzip_payload = gzip_response.json().get("data", gzip_response.json())
        assert gzip_payload["trace"] == "python-gzip", gzip_payload
        assert gzip_payload["payload"] == "payload-ok", gzip_payload

        br_response = await client.post(
            "/api/binary/packet",
            params={"trace": "python-br"},
            content=packet_bytes,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "br",
            },
        )
        assert br_response.status_code == 415, br_response.text

        audit_bytes = AuditPacketWire.to_binary_body(build_audit_packet()).to_bytes()
        audit_gzip_response = await client.post(
            "/api/binary/audit-packet",
            params={"trace": "python-audit-gzip"},
            content=gzip.compress(audit_bytes),
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "gzip",
            },
        )
        assert audit_gzip_response.status_code == 415, audit_gzip_response.text


async def check_binary_br(base_url: str) -> None:
    packet_bytes = DemoPacketWire.to_binary_body(build_packet()).to_bytes()
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post(
            "/api/binary/packet",
            params={"trace": "python-br-registered"},
            content=b"BRSTUB\x00" + packet_bytes,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Encoding": "br",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json().get("data", response.json())
        assert payload["trace"] == "python-br-registered", payload
        assert payload["payload"] == "payload-ok", payload


async def check_audit_binary(api) -> None:
    response = await api.binary.audit_packet(query=AuditPacketQuery(trace="python-audit"), binary=build_audit_packet())
    assert response.trace == "python-audit", response
    assert response.item_count == 2, response
    assert response.checksum == 2, response


async def check_binary_response(api) -> None:
    response = await api.binary.audit_packet_response()
    assert response.header.flags == AuditPacketFlags.HasItems, response
    assert response.header.item_count == 2, response
    assert response.body.items[0].id == 11, response
    assert response.body.items[1].code == 202, response
    assert response.body.checksum == 2, response


async def check_media(api) -> None:
    preview = await api.media.media_preview(
        multipart=MediaPreviewForm(
            title="python-media",
            image=("preview.jpg", SAMPLE_JPEG, "image/jpeg"),
        )
    )
    assert preview.status == 200, preview
    assert preview.content_type == "image/jpeg", preview
    assert preview.body.startswith(b"\xff\xd8"), preview.body

    frame = await api.media.media_frame()
    assert frame.content_type == "image/jpeg", frame
    assert frame.body == SAMPLE_JPEG, frame.body

    download = await api.media.media_download()
    assert download.status == 200, download
    assert download.filename == "media-report.xlsx", download
    assert download.body.startswith(b"PK"), download.body

    dynamic = await api.media.media_download_dynamic()
    assert dynamic.status == 200, dynamic
    assert dynamic.filename == "media-report-dynamic.xlsx", dynamic
    assert dynamic.body.startswith(b"PK"), dynamic.body

    stream = await api.media.media_mjpeg()
    try:
        first = b""
        async for chunk in stream:
            first += chunk
            break
        assert MJPEG_BOUNDARY in first, first
    finally:
        await stream.aclose()


async def check_request_options(base_url: str) -> None:
    async_client = httpx.AsyncClient(
        headers={"x-options-default": "default", "x-options-token": "default"},
        timeout=0.02,
    )
    api = ApiClient(HttpClientTransport(base_url, client=async_client))
    try:
        ok = await api.demo.request_options(
            query=RequestOptionsQuery(delay_ms=30),
            headers={"x-options-token": "per-call"},
            timeout=1.0,
        )
        assert ok.status == "ok", ok
        assert ok.delay_ms == 30, ok

        timed_out = False
        try:
            await api.demo.request_options(
                query=RequestOptionsQuery(delay_ms=120),
                headers={"x-options-token": "per-call"},
                timeout=0.01,
            )
        except (httpx.TimeoutException, httpx.RequestError):
            timed_out = True
        assert timed_out, "short per-call timeout did not fail"
    finally:
        await api.aclose()


async def check_media_filename_edge(api) -> None:
    response = await api.media.media_download_filename_edge()
    assert response.status == 200, response
    assert response.filename == "媒体报告.xlsx", response
    assert response.body.startswith(b"PK"), response.body


async def check_media_error(api) -> None:
    ok = await api.media.media_error_frame(query=MediaErrorFrameQuery(mode="ok"))
    assert ok.content_type == "image/jpeg", ok
    assert ok.body.startswith(b"\xff\xd8"), ok.body

    rate_limited = await expect_api_error(
        lambda: api.media.media_error_frame(query=MediaErrorFrameQuery(mode="rate_limit")),
        route_id="api.media.get.errorframe",
    )
    assert is_api_error(rate_limited, ApiErrors.DemoErr.RATE_LIMITED), rate_limited


async def check_typed_errors(api) -> None:
    ok = await api.demo.error_demo(query=ErrorDemoQuery(mode="ok"))
    assert ok.status == "ok", ok

    rate_limited = await expect_api_error(lambda: api.demo.error_demo(query=ErrorDemoQuery(mode="rate_limit")))
    assert is_api_error(rate_limited, ApiErrors.DemoErr.RATE_LIMITED), rate_limited
    assert resolve_api_toast(rate_limited.toast, fallback_message=str(rate_limited)) == "请等待 30 秒后重试"

    unknown = await expect_api_error(lambda: api.demo.error_demo(query=ErrorDemoQuery(mode="unknown")))
    assert unknown.id == "", unknown
    assert unknown.code == 70001, unknown
    assert str(unknown) == "example undefined business error", unknown


async def check_naming(api, alt_api) -> None:
    api_response = await api.conflict.default(query=DefaultQuery(class_="python-api"))
    assert api_response.default == "api-default", api_response
    assert api_response.class_ == "python-api", api_response
    assert api_response.enum is ApiKeywordEnum.DEFAULT, api_response

    alt_response = await alt_api.conflict.default(query=AltDefaultQuery(class_="python-alt"))
    assert alt_response.default == "alt-default", alt_response
    assert alt_response.class_ == "python-alt", alt_response
    assert alt_response.enum.value == "class", alt_response


async def check_legacy_json(api) -> None:
    profile = await api.account.account_profile()
    assert profile.user_id == "1000010", profile
    assert profile.nickname == "legacy-user", profile

    rooms = await api.room.room_list()
    assert rooms.rooms[0].room_id == "100", rooms
    assert rooms.rooms[0].title == "legacy-room", rooms

    compat = await api.legacy_json.legacy_json_compat()
    assert compat.target == ["legacy-room", "backup-room"], compat
    assert compat.ids == ["1", 2, "3"], compat
    assert compat.normalized_ids == ["1", "2", "3"], compat

    numeric_profile = LegacyAccountProfileResponse.from_value(
        {"user_id": 1000010, "nickname": "legacy-user"}
    )
    assert numeric_profile.user_id == "1000010", numeric_profile

    numeric_rooms = LegacyRoomListResponse.from_value(
        {"rooms": [{"room_id": 100, "title": "legacy-room"}]}
    )
    assert numeric_rooms.rooms[0].room_id == "100", numeric_rooms

    string_target = LegacyJsonCompatResponse.from_value(
        {
            "target": "legacy-room",
            "ids": ["1", 2, "3"],
            "normalized_ids": ["1", 2, "3"],
        }
    )
    assert string_target.target == "legacy-room", string_target
    assert string_target.normalized_ids == ["1", "2", "3"], string_target

    array_target = LegacyJsonCompatResponse.from_value(
        {
            "target": ["legacy-room", "backup-room"],
            "ids": ["1", 2, "3"],
            "normalized_ids": ["1", 2, "3"],
        }
    )
    assert array_target.target == ["legacy-room", "backup-room"], array_target
    assert array_target.ids == ["1", 2, "3"], array_target
    assert array_target.normalized_ids == ["1", "2", "3"], array_target


async def expect_api_error(action, route_id: str = "api.demo.get.errordemo") -> ApiError:
    try:
        await action()
    except Exception as error:
        if not is_api_error(error):
            raise AssertionError(f"expected ApiError, got {type(error).__name__}: {error}") from error
        assert error.route_id == route_id, error.route_id
        assert error.raw, "ApiError raw payload is empty"
        return error
    raise AssertionError("expected ApiError but request succeeded")


def check_unsupported(action, snippet: str) -> None:
    try:
        action()
    except NotImplementedError as error:
        assert snippet in str(error), error
        return
    raise AssertionError(f"expected NotImplementedError containing {snippet}")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("base URL argument is required")
    selected = scenario_set(
        sys.argv[2]
        if len(sys.argv) > 2
        else "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,binary-response,media,request-options,media-filename-edge,media-error,single-channel,legacy-json"
    )
    async with (
        create_client(sys.argv[1]) as api,
        create_alt_client(sys.argv[1]) as alt_api,
        create_legacy_client(sys.argv[1]) as legacy_api,
    ):
        if "rpc" in selected:
            await check_rpc(api)
        if "raw" in selected:
            await check_raw(sys.argv[1])
        if "xml" in selected:
            await check_xml(sys.argv[1])
        if "static" in selected:
            await check_static(sys.argv[1])
        if "header" in selected:
            await check_header(sys.argv[1])
        if "scalar" in selected:
            await check_scalar(api)
        if "enum" in selected:
            await check_enum(api)
        if "map" in selected:
            await check_map(api)
        if "deprecated" in selected:
            await check_deprecated(api)
        if "form" in selected:
            await check_form(api)
        if "binary" in selected:
            await check_binary(api, sys.argv[1])
        if "binary-br" in selected:
            await check_binary_br(sys.argv[1])
        if "audit-binary" in selected:
            await check_audit_binary(api)
        if "binary-response" in selected:
            await check_binary_response(api)
        if "media" in selected:
            await check_media(api)
        if "request-options" in selected:
            await check_request_options(sys.argv[1])
        if "media-filename-edge" in selected:
            await check_media_filename_edge(api)
        if "media-error" in selected:
            await check_media_error(api)
        if "error" in selected:
            await check_typed_errors(api)
        if "naming" in selected:
            await check_naming(api, alt_api)
        if "legacy-json" in selected:
            await check_legacy_json(legacy_api)
        if "sse" in selected:
            check_unsupported(lambda: api.demo.subscribe_sweep_events(open_data=SweepEventsOpen(run_id="python-sse")), "stream")
        if "websocket" in selected:
            check_unsupported(
                lambda: api.demo.open_assistant_session(open_data=AssistantSessionOpen(session_id="python-ws")),
                "channel",
            )
        if "single-channel" in selected:
            check_unsupported(lambda: api.api.open_hello_channel(), "channel")
    print("python conformance passed")


if __name__ == "__main__":
    asyncio.run(main())
