from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_blueprint_example_client.api.routes.api.binary.client import BinaryClient
from api_blueprint_example_client.api.routes.api.binary.gen_binary import (
    DemoFlags,
    DemoPacket,
    DemoPacketBody,
    DemoPacketHeader,
    DemoPacketItem,
    DemoPacketWire,
    write_demopacket,
)
from api_blueprint_example_client.api.runtime.binary import RawBinaryBody
from api_blueprint_example_client.api.transports.http.client import HttpClientTransport


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


async def call_binary(client: BinaryClient, trace: str, binary: object) -> None:
    envelope = await client.packet(query={"trace": trace}, binary=binary)
    if envelope.get("code") != 0:
        raise AssertionError(f"binary {trace} failed: {envelope}")
    data = envelope.get("data") or {}
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
    if data != expected:
        raise AssertionError(f"binary {trace} response={data!r}")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("base URL argument is required")
    transport = HttpClientTransport(sys.argv[1])
    client = BinaryClient(transport)
    packet = build_packet()
    try:
        await call_binary(client, "py-typed", packet)
        await call_binary(client, "py-raw", RawBinaryBody(DemoPacketWire.to_binary_body(packet).to_bytes()))
        await call_binary(client, "py-stream", DemoPacketWire.body(lambda writer: write_demopacket(packet, writer)))
    finally:
        await transport.aclose()


if __name__ == "__main__":
    asyncio.run(main())
