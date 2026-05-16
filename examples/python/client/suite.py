from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_blueprint_example_client.api.client import create_client
from api_blueprint_example_client.api.routes.api.binary.gen_types import (
    DemoFlags,
    DemoPacket,
    DemoPacketBody,
    DemoPacketHeader,
    DemoPacketItem,
    DemoPacketWire,
    PacketQuery,
    write_demopacket,
)
from api_blueprint_example_client.api.routes.api.demo.gen_types import ErrorDemoQuery
from api_blueprint_example_client.api.runtime.binary import RawBinaryBody
from api_blueprint_example_client.api.runtime.errors import (
    ApiError,
    ApiErrors,
    is_api_error,
    resolve_api_toast,
)


def build_packet() -> DemoPacket:
    return DemoPacket(
        header=DemoPacketHeader(
            flags=DemoFlags.HasPayload | DemoFlags.HasScores,
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


async def call_binary(client, trace: str, binary: object) -> None:
    data = await client.packet(query=PacketQuery(trace=trace), binary=binary)
    expected = {
        "trace": trace,
        "version": 1,
        "item_count": 2,
        "payload": "payload-ok",
        "score_sum": 8,
        "first_label": "alpha",
        "item_ids": [11, 22],
        "checksum": 12,
    }
    actual = data.__dict__ if hasattr(data, "__dict__") else data
    if actual != expected:
        raise AssertionError(f"binary {trace} response={data!r}")


async def call_typed_errors(client) -> None:
    ok = await client.error_demo(query=ErrorDemoQuery(mode="ok"))
    if ok.status != "ok":
        raise AssertionError(f"error-demo ok response={ok!r}")

    token = await expect_api_error(lambda: client.error_demo(query=ErrorDemoQuery(mode="token")))
    if not is_api_error(token, ApiErrors.CommonErr.TOKEN_EXPIRE):
        raise AssertionError(f"token ApiError id={token.id!r} code={token.code!r}")
    token_toast = resolve_api_toast(
        token.toast,
        lambda key: "translated token expired" if key == "auth.token_expire" else None,
        str(token),
    )
    if token_toast != "translated token expired":
        raise AssertionError(f"token toast={token_toast!r}")

    rate_limited = await expect_api_error(lambda: client.error_demo(query=ErrorDemoQuery(mode="rate_limit")))
    if not is_api_error(rate_limited, ApiErrors.DemoErr.RATE_LIMITED):
        raise AssertionError(f"rate limit ApiError id={rate_limited.id!r} code={rate_limited.code!r}")
    rate_toast = resolve_api_toast(rate_limited.toast, fallback_message=str(rate_limited))
    if rate_toast != "请等待 30 秒后重试":
        raise AssertionError(f"rate limit toast={rate_toast!r}")

    unknown = await expect_api_error(lambda: client.error_demo(query=ErrorDemoQuery(mode="unknown")))
    if unknown.id or unknown.code != 70001 or str(unknown) != "example undefined business error":
        raise AssertionError(
            f"unknown ApiError id={unknown.id!r} code={unknown.code!r} message={str(unknown)!r}"
        )


async def expect_api_error(action) -> ApiError:
    try:
        await action()
    except Exception as error:
        if not is_api_error(error):
            raise AssertionError(f"expected ApiError, got {type(error).__name__}: {error}") from error
        if error.route_id != "api.demo.get.errordemo":
            raise AssertionError(f"ApiError route_id={error.route_id!r}")
        if not error.raw:
            raise AssertionError("ApiError raw payload is empty")
        return error
    raise AssertionError("expected ApiError but request succeeded")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("base URL argument is required")
    packet = build_packet()
    async with create_client(sys.argv[1]) as api:
        await call_binary(api.binary, "py-typed", packet)
        await call_binary(api.binary, "py-raw", RawBinaryBody(DemoPacketWire.to_binary_body(packet).to_bytes()))
        await call_binary(api.binary, "py-stream", DemoPacketWire.body(lambda writer: write_demopacket(packet, writer)))
        await call_typed_errors(api.demo)


if __name__ == "__main__":
    asyncio.run(main())
