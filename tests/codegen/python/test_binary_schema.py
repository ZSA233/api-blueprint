from __future__ import annotations

from .helpers import *


def test_python_server_binary_schema_service_contract_uses_typed_packet(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-encoding: identity,gzip,br

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    service_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_service.py"
    ).read_text(encoding="utf-8")
    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        output_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "binary: DemoPacket" in service_text
    assert "binary: bytes | None = None" not in service_text
    assert "binary: dict[str, Any] | None = None" not in service_text
    assert "binary_body = await _binary_body(" in adapter_text
    assert "binary = api_binary_types.DemoPacketWire.from_bytes(binary_body)" in adapter_text
    assert "allowed_content_encodings=('identity', 'gzip', 'br')" in adapter_text
    assert "_gzip_decode(encoded, config.decompressed_binary_max_bytes)" in adapter_text
    assert "_read_limited_binary_stream(source, max_bytes" in adapter_text
    assert "UnsupportedContentEncodingError" in adapter_text
    assert "decompressed_binary_max_bytes: int = 16 * 1024 * 1024" in runtime_text
    assert "binary_content_decoders: Mapping[str, Callable[[bytes], bytes]]" in runtime_text
    _compile_generated_files(output_dir)
    asyncio.run(_assert_python_server_br_stub_decoder(output_dir))


async def _assert_python_server_br_stub_decoder(output_dir: Path) -> None:
    module_prefix = "api_blueprint_generated"
    for name in list(sys.modules):
        if name == module_prefix or name.startswith(module_prefix + "."):
            del sys.modules[name]
    sys.path.insert(0, str(output_dir))
    try:
        from fastapi import FastAPI

        gen_server = importlib.import_module("api_blueprint_generated.api.transports.http.gen_server")
        runtime_server = importlib.import_module("api_blueprint_generated.api.runtime.server")
        gen_types = importlib.import_module("api_blueprint_generated.api.routes.api.binary.gen_types")

        class BinaryService:
            async def packet(self, binary):
                assert isinstance(binary, gen_types.DemoPacket)
                return gen_types.PacketResponse(status="decoded")

        default_app = FastAPI()
        default_app.include_router(gen_server.create_router(binary_service=BinaryService()))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=default_app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/binary/packet",
                content=b"BRSTUB\x00ABP1",
                headers={"Content-Encoding": "br"},
            )
            assert response.status_code == 415, response.text

        def decode_br_stub(body: bytes) -> bytes:
            prefix = b"BRSTUB\x00"
            if not body.startswith(prefix):
                raise ValueError("invalid br stub payload")
            return body[len(prefix):]

        registered_app = FastAPI()
        registered_app.include_router(
            gen_server.create_router(
                binary_service=BinaryService(),
                config=runtime_server.ApiServerConfig(binary_content_decoders={"br": decode_br_stub}),
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=registered_app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/binary/packet",
                content=b"BRSTUB\x00ABP1",
                headers={"Content-Encoding": "br"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["status"] == "decoded"

            response = await client.post(
                "/api/binary/packet",
                content=b"ABP1",
                headers={"Content-Encoding": "br"},
            )
            assert response.status_code == 400, response.text
    finally:
        sys.path.remove(str(output_dir))
        for name in list(sys.modules):
            if name == module_prefix or name.startswith(module_prefix + "."):
                del sys.modules[name]


def test_python_codegen_generates_binary_schema_response_encoder_and_decoder(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet AuditPacket

endian: little
content-type: application/vnd.audit-packet

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | u8 | 1 | const=2 | kind |
| item_count | u16 | 1 | min=1,max=4,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | AuditItem | item_count | | items |
| checksum | u16 | 1 | assert=item_count | checksum |

## struct AuditItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
        """.strip(),
        source_path="audit_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.GET("/audit").RSP_BINARY_SCHEMA(schema)

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()

    client_route = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_client.py"
    ).read_text(encoding="utf-8")
    client_transport = (
        client_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py"
    ).read_text(encoding="utf-8")
    server_service = (
        server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_service.py"
    ).read_text(encoding="utf-8")
    server_adapter = (
        server_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")
    binary_types = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_binary.py"
    ).read_text(encoding="utf-8")

    assert (
        "async def audit(\n"
        "        self,\n"
        "        *,\n"
        "        headers: Mapping[str, str] | None = None,\n"
        "        timeout: float | None = None,\n"
        "    ) -> AuditPacket:"
    ) in client_route
    assert "response_type: str | None = 'binary_schema'" in client_route
    assert "return AuditPacketWire.from_bytes(payload)" in client_route
    assert 'endian="little"' in binary_types
    assert 'endian="\'little\'"' not in binary_types
    assert 'if request.response_type == "binary_schema":' in client_transport
    assert "return response.content" in client_transport
    assert "async def audit(self) -> AuditPacket:" in server_service
    assert "_binary_schema_response(" in server_adapter
    assert "encoder=api_binary_types.AuditPacketWire.to_binary_body" in server_adapter
    _compile_generated_files(client_dir)
    _compile_generated_files(server_dir)

def test_python_client_generates_binary_body_union_runtime_and_transport(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | Kind | 1 | const=1 | kind |
| flags | Flags | 1 | min=0 | flags |
| pad0 | padding | 1 | | pad |
| code | u24 | 1 | min=1,max=16777215 | code |
| delta | i24 | 1 | min=-8,max=8 | delta |
| payload_len | u16 | 1 | max=16,sizeof=payload | payload length |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | | payload |

## enum Kind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Reserved | 1..31 | const=0 | reserved |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_client.py"
    ).read_text(encoding="utf-8")
    schema_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.py"
    ).read_text(encoding="utf-8")
    types_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_types.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        output_dir / "api_blueprint_generated" / "api" / "runtime" / "binary" / "gen_runtime.py"
    ).read_text(encoding="utf-8")
    transport_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py"
    ).read_text(encoding="utf-8")

    assert "binary: DemoPacket | ApiBinaryBody" in route_text
    assert "binary=DemoPacketWire.to_binary_body(binary)" in route_text
    assert "from .gen_types import (" in route_text
    assert "from .gen_binary import *" in types_text
    assert "class DemoPacketKind:" in schema_text
    assert "class DemoPacketFlags:" in schema_text
    assert "reserved bits must be zero" in schema_text
    assert "writer.write_u24" in schema_text
    assert "writer.write_i24" in schema_text
    assert "writer.write_zeroes" in schema_text
    assert "class RawBinaryBody" in runtime_text
    assert "binary.to_bytes()" in transport_text
    assert not (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "wire.py"
    ).exists()
    _compile_generated_files(output_dir)

def test_python_binary_writer_uses_local_paths_and_wraps_boundaries_without_success_path_allocations(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | const=1,max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    schema_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        output_dir / "api_blueprint_generated" / "api" / "runtime" / "binary" / "gen_runtime.py"
    ).read_text(encoding="utf-8")

    assert 'raise wrap_binary_field("DemoPacket.header", err) from err' in schema_text
    assert 'raise wrap_binary_field("DemoPacket.body", err) from err' in schema_text
    assert 'write_demopacket_item(item, writer, state, path="")' in schema_text
    assert 'raise wrap_binary_index("items", index, err) from err' in schema_text
    assert 'path: str = "Item",' in schema_text
    assert 'require_range("id", int(value.id), 1, 2**63 - 1)' in schema_text
    assert "Item.id" not in schema_text
    assert "join_binary_path(" not in schema_text
    assert "index_binary_path(" not in schema_text
    assert "def join_binary_path(" in runtime_text
    assert "def index_binary_path(" in runtime_text
    assert "def wrap_binary_field(" in runtime_text
    assert "def wrap_binary_index(" in runtime_text
    _compile_generated_files(output_dir)

def test_python_binary_writer_reports_nested_schema_path(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | const=1,max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    binary_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.binary.gen_binary",
    )
    runtime_module = importlib.import_module("api_blueprint_generated.api.runtime.binary")
    packet = binary_module.DemoPacket(
        header=binary_module.DemoPacketHeader(),
        body=binary_module.DemoPacketBody(items=[binary_module.DemoPacketItem(id=0)]),
    )

    with pytest.raises(runtime_module.BinaryEncodeError) as caught:
        binary_module.DemoPacketWire.to_binary_body(packet).to_bytes()

    assert caught.value.path == "DemoPacket.body.items[0].id"
    assert caught.value.message == "value 0 outside range 1..9223372036854775807"
    assert caught.value.detail == str(caught.value)
