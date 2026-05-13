from __future__ import annotations

from pathlib import Path

import pytest

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine.binary_schema import parse_binary_schema
from api_blueprint.engine.model import Enum, Model, String
from api_blueprint.engine import Blueprint, ConnectionDelivery, Error, Toast
from api_blueprint.engine.wrapper import GeneralWrapper
from api_blueprint.writer.core.contracts import route_contract
from api_blueprint.writer.typescript import TypeScriptProtoRegistry, to_ts_identifier, to_ts_name
from api_blueprint.writer.typescript.writer import TypeScriptWriter


class Payload(Model):
    value = String(description="value")


def test_typescript_name_helpers_preserve_expected_output():
    assert to_ts_name("REQ_Ws_QUERY") == "ReqWsQuery"
    assert to_ts_identifier("delete$") == '"delete$"'


def test_typescript_registry_builds_wrapper_alias_with_generics():
    registry = TypeScriptProtoRegistry()
    proto = registry.ensure(GeneralWrapper, tag="wrapper")
    assert proto is not None
    assert proto.type_reference(["Payload"]) == "GeneralWrapper<Payload>"


def test_route_contract_assigns_stable_service_and_event_names():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.WS("/ws")
    contract = route_contract(router)

    assert contract.route_id == "api.demo.ws.ws"
    assert contract.service_name == "DemoService"
    assert contract.namespace == "demo"
    assert contract.ws is not None
    assert contract.ws.connect_method == "ConnectWs"
    assert contract.ws.send_method == "SendWs"
    assert contract.ws.close_method == "CloseWs"
    assert contract.ws.event_base == "api_blueprint.ws.api.demo.ws.ws"


def test_typescript_http_generation_uses_transport_bridge_and_raw_ws_escape_hatch(tmp_path: Path):
    bp = Blueprint(root="/api")

    class WSRecv(Model):
        value = String(description="value")

    class WSSend(Model):
        value = String(description="value")

    with bp.group("/demo") as views:
        views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))
        views.WS("/ws").RECV(WSRecv).SEND(WSSend)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir, base_url="http://localhost:2333")
    writer.register(bp)
    writer.gen()

    http_transport = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")
    runtime_client = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    runtime_index = (output_dir / "api" / "runtime" / "gen_index.ts").read_text(encoding="utf-8")
    http_factory = (output_dir / "api" / "transports" / "http" / "api" / "gen_factory.ts").read_text(encoding="utf-8")
    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "export class DefaultTransport implements ApiTransport" in http_transport
    assert "export interface ApiClientConfig {\n  transport?: ApiTransport;\n}" in runtime_client
    assert "export interface ApiHttpTransportConfig extends ApiClientConfig" in http_transport
    assert "baseUrl?: string;" in http_transport
    assert "fetcher?: typeof fetch;" in http_transport
    assert not (output_dir / "api" / "runtime" / "gen_factory.ts").exists()
    assert 'demoClient: new DemoClientImpl(sharedConfig),' in http_factory
    assert 'new DefaultTransport(config, "http://localhost:2333")' in http_factory
    assert 'export * from "./factory";' not in runtime_index
    assert "http://localhost:2333" not in client_text
    assert "super(config);" in client_text
    assert "super(config," not in client_text
    assert "connectBridge<Shared.WSSend, Shared.WSRecv>" in client_text
    assert "connectWsRaw(" in client_text


def test_typescript_writer_can_use_contract_graph_route_adapter(monkeypatch, tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])

    def reject_legacy_router_contract(_router):
        raise AssertionError("legacy router route_contract should not be used")

    monkeypatch.setattr(
        "api_blueprint.writer.core.contract_adapters.route_contract_from_router",
        reject_legacy_router_contract,
    )

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "async ping(" in client_text


def test_typescript_writer_generates_error_catalog_runtime(tmp_path: Path):
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    bp = Blueprint(root="/api", errors=[CommonErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    errors_text = (output_dir / "api" / "runtime" / "gen_errors.ts").read_text(encoding="utf-8")
    catalog_text = (output_dir / "api" / "runtime" / "gen_error_catalog.ts").read_text(encoding="utf-8")
    public_errors = (output_dir / "api" / "runtime" / "errors.ts").read_text(encoding="utf-8")
    runtime_index = (output_dir / "api" / "runtime" / "gen_index.ts").read_text(encoding="utf-8")
    assert "export class ApiCodeError extends Error" in errors_text
    assert "export interface ApiToastSpec" in errors_text
    assert "export function resolveApiToast(" in errors_text
    assert "ErrorCatalogByID" not in errors_text
    assert '"CommonErr.UNKNOWN"' not in errors_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "TOKEN_EXPIRE: 55555" in catalog_text
    assert 'default: "登录状态已失效，请重新登录"' in catalog_text
    assert "\\u767b" not in catalog_text
    assert "locales" not in catalog_text
    assert 'export * from "./gen_errors";' in public_errors
    assert 'export * from "./gen_error_catalog";' in public_errors
    assert 'export * from "./errors";' in runtime_index


def test_typescript_contract_graph_adapter_owns_request_and_response_models(tmp_path: Path):
    bp = Blueprint(root="/api")

    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    with bp.group("/demo") as views:
        router = views.POST("/submit").ARGS(q=String(description="q")).REQ(SubmitJson).RSP(SubmitResponse)

    graph = build_contract_graph([bp])
    router.req_query = None
    router.req_json = None
    router.rsp_model = None

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    models_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_models.ts").read_text(encoding="utf-8")
    assert "query?: Models.ReqSubmitQuery;" in client_text
    assert "json?: Shared.SubmitJson;" in client_text
    assert "Promise<Models.RspSubmit>" in client_text
    assert "export type RspSubmit = SubmitResponse;" in models_text


def test_typescript_generates_stream_and_channel_contracts(tmp_path: Path):
    bp = Blueprint(root="/api")

    class Open(Model):
        run_id = String(description="run id")

    class TaskState(Model):
        status = String(description="status")

    class TaskProgress(Model):
        value = String(description="value")

    class ClientInput(Model):
        text = String(description="text")

    class CloseInfo(Model):
        reason = String(description="reason")

    with bp.group("/runs") as views:
        views.STREAM("/events").OPEN(Open).SERVER_MESSAGE(
            "TaskStreamMessage",
            state=TaskState,
            progress=TaskProgress,
        ).CLOSE(CloseInfo)
        views.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED).OPEN(Open).CLIENT_MESSAGE(ClientInput).SERVER_MESSAGE(TaskState).CLOSE(CloseInfo)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    runtime_client = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    models_text = (output_dir / "api" / "routes" / "api" / "runs" / "gen_models.ts").read_text(encoding="utf-8")
    client_text = (output_dir / "api" / "routes" / "api" / "runs" / "gen_client.ts").read_text(encoding="utf-8")
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "export interface ApiStreamBridge<Recv, Close = SocketCloseInfo>" in runtime_client
    assert "export interface ApiChannelBridge<Recv, Send, Close = SocketCloseInfo> extends ApiStreamBridge<Recv, Close>" in runtime_client
    assert 'delivery?: "ordered" | "unordered";' in runtime_client
    assert (
        "export type TaskStreamMessage =\n"
        '  | { type: "state"; data: TaskState }\n'
        '  | { type: "progress"; data: TaskProgress };'
        in models_text
    )
    assert "subscribeEvents(" in client_text
    assert "openChat(" in client_text
    assert "ApiStreamBridge<Models.TaskStreamMessage, Shared.CloseInfo>" in client_text
    assert "ApiChannelBridge<Shared.TaskState, Shared.ClientInput, Shared.CloseInfo>" in client_text
    assert "openStream<Models.TaskStreamMessage, Shared.CloseInfo>" in client_text
    assert "openChannel<Shared.TaskState, Shared.ClientInput, Shared.CloseInfo>" in client_text
    assert 'connectionKind: "stream"' in client_text
    assert 'connectionKind: "channel"' in client_text
    assert 'scope: "session"' in client_text
    assert 'delivery: "ordered"' in client_text
    assert 'delivery: "unordered"' in client_text
    assert "class HttpEventStreamBridge<Recv, Close = SocketCloseInfo> implements ApiStreamBridge<Recv, Close>" in transport_text
    assert 'envelope.type === "close"' in transport_text


def test_typescript_channel_operation_id_changes_generated_method_name(tmp_path: Path):
    bp = Blueprint(root="/api")

    class Open(Model):
        device_id = String(description="device id")

    class ServerMessage(Model):
        text = String(description="text")

    class ClientMessage(Model):
        text = String(description="text")

    class CloseInfo(Model):
        reason = String(description="reason")

    with bp.group("/demo") as views:
        views.CHANNEL("/ws", operation_id="Realtime").OPEN(Open).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(
            ServerMessage
        ).CLOSE(CloseInfo)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "openRealtime(" in client_text
    assert 'routeId: "api.demo.channel.ws"' in client_text
    assert 'connectMethod: "OpenRealtime"' in client_text
    assert 'sendMethod: "SendRealtime"' in client_text
    assert 'closeMethod: "CloseRealtime"' in client_text


def test_typescript_writer_disambiguates_same_path_http_methods_with_contract_graph(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/settings") as views:
        views.GET("/current").RSP(message=String(description="message"))
        views.PUT("/current").RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "settings" / "gen_client.ts").read_text(encoding="utf-8")
    assert "async currentGet(" in client_text
    assert 'method: "GET"' in client_text
    assert 'operation: "CurrentGet"' in client_text
    assert "async currentPut(" in client_text
    assert 'method: "PUT"' in client_text
    assert 'operation: "CurrentPut"' in client_text


def test_typescript_generation_allows_real_shared_group_without_alias_rewrite(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/shared") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "api" / "routes" / "api" / "shared" / "gen_client.ts").is_file()
    assert (output_dir / "api" / "runtime" / "gen_client.ts").is_file()


def test_typescript_root_routes_use_root_client_file_without_reserved_slug(tmp_path: Path):
    bp = Blueprint(root="/api")
    bp.GET("/status").RSP(message=String(description="message"))
    with bp.group("/root") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "api" / "routes" / "api" / "client.ts").is_file()
    assert (output_dir / "api" / "routes" / "api" / "root" / "client.ts").is_file()
    assert not (output_dir / "api" / "routes" / "_root").exists()
    assert not (output_dir / "api" / "transports" / "http" / "api" / "_root").exists()


def test_typescript_client_generates_binary_overloads_runtime_and_transport(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| flags | DemoFlags | 1 | min=0 | flags |
| pad0 | padding | 1 | | pad |
| code | u24 | 1 | min=1,max=16777215 | code |
| delta | i24 | 1 | min=-8,max=8 | delta |
| payload_len | u16 | 1 | max=16,sizeof=payload | payload length |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | | payload |

## bitflags DemoFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Reserved | 1..31 | const=0 | reserved |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_wrapper=GeneralWrapper)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "api" / "routes" / "api" / "binary" / "gen_client.ts").read_text(
        encoding="utf-8"
    )
    schema_text = (
        output_dir / "api" / "routes" / "api" / "binary" / "binary" / "gen_binary.ts"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "api" / "runtime" / "binary" / "gen_runtime.ts").read_text(encoding="utf-8")
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "binary: Binary.DemoPacket;" in route_text
    assert "binary: ApiBinaryBody;" in route_text
    assert "binary: Binary.DemoPacket | ApiBinaryBody;" in route_text
    assert "DemoPacketWire.toBinaryBody(request.binary)" in route_text
    assert "export const DemoFlagsValues" in schema_text
    assert "HasPayload: 1" in schema_text
    assert "reserved bits must be zero" in schema_text
    assert "writer.writeU24" in schema_text
    assert "writer.writeI24" in schema_text
    assert "writer.writeZeroes" in schema_text
    assert "class RawBinaryBody" in runtime_text
    assert "private writeScratch" in runtime_text
    assert "this.writeScratch(8);" in runtime_text
    assert "binaryBodyToUint8Array" in transport_text


def test_typescript_writer_blocks_legacy_group_cleanup_when_user_client_exists(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    legacy_client = output_dir / "api" / "demo" / "client.ts"
    legacy_client.parent.mkdir(parents=True)
    legacy_client.write_text("// user custom client shim\n", encoding="utf-8")

    writer = TypeScriptWriter(output_dir)
    writer.register(bp)

    with pytest.raises(ValueError, match="legacy generated layout contains user-owned or unknown files"):
        writer.gen()

    assert legacy_client.exists()


def test_typescript_writer_removes_safe_legacy_shared_dir(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    legacy_shared = output_dir / "api" / "shared"
    legacy_shared.mkdir(parents=True)
    (legacy_shared / "gen_client.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "client.ts").write_text("export * from './gen_client';\n", encoding="utf-8")
    (legacy_shared / "gen_models.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "models.ts").write_text("export * from './gen_models';\n", encoding="utf-8")
    (legacy_shared / "gen_index.ts").write_text("// generated\n", encoding="utf-8")
    (legacy_shared / "index.ts").write_text('export * from "./gen_index";\n', encoding="utf-8")

    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert not legacy_shared.exists()
