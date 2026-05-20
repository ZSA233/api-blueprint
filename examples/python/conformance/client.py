from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))

from api_blueprint_example_client.alt.client import create_client as create_alt_client
from api_blueprint_example_client.alt.routes.alt.conflict.gen_types import DefaultQuery as AltDefaultQuery
from api_blueprint_example_client.api.client import create_client
from api_blueprint_example_client.api.routes.api.binary.gen_types import (
    AuditPacket,
    AuditPacketBody,
    AuditPacketFlags,
    AuditPacketHeader,
    AuditPacketItem,
    AuditPacketQuery,
    DemoPacket,
    DemoPacketBody,
    DemoPacketFlags,
    DemoPacketHeader,
    DemoPacketItem,
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
    SweepEventsOpen,
    TestPostJSON,
)
from api_blueprint_example_client.api.routes.api.gen_types import HelloChannelMsgTypeEnum
from api_blueprint_example_client.api.routes.api.hello.gen_types import AbcQuery as HelloAbcQuery
from api_blueprint_example_client.api.routes.api.hello.gen_types import MapEnum
from api_blueprint_example_client.api.runtime.errors import (
    ApiError,
    ApiErrors,
    is_api_error,
    resolve_api_toast,
)
from api_blueprint_example_client.static.client import create_client as create_static_client


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


async def check_binary(api) -> None:
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


async def check_audit_binary(api) -> None:
    response = await api.binary.audit_packet(query=AuditPacketQuery(trace="python-audit"), binary=build_audit_packet())
    assert response.trace == "python-audit", response
    assert response.item_count == 2, response
    assert response.checksum == 2, response


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


async def expect_api_error(action) -> ApiError:
    try:
        await action()
    except Exception as error:
        if not is_api_error(error):
            raise AssertionError(f"expected ApiError, got {type(error).__name__}: {error}") from error
        assert error.route_id == "api.demo.get.errordemo", error.route_id
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
        else "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,single-channel"
    )
    async with create_client(sys.argv[1]) as api, create_alt_client(sys.argv[1]) as alt_api:
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
            await check_binary(api)
        if "audit-binary" in selected:
            await check_audit_binary(api)
        if "error" in selected:
            await check_typed_errors(api)
        if "naming" in selected:
            await check_naming(api, alt_api)
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
