from __future__ import annotations

from pathlib import Path

from api_blueprint.engine.model import Enum, Model, String
from api_blueprint.engine import Blueprint
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
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    shared_transport = (output_dir / "api" / "(shared)" / "gen_transport.ts").read_text(encoding="utf-8")
    shared_factory = (output_dir / "api" / "(shared)" / "gen_factory.ts").read_text(encoding="utf-8")
    shared_index = (output_dir / "api" / "(shared)" / "gen_index.ts").read_text(encoding="utf-8")
    client_text = (output_dir / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "export class DefaultTransport implements ApiTransport" in shared_transport
    assert "export interface GeneratedClients" in shared_factory
    assert "export function createClients(config: ApiClientConfig = {}): GeneratedClients" in shared_factory
    assert 'demoClient: new DemoClient(config),' in shared_factory
    assert 'export * from "./factory";' in shared_index
    assert "connectBridge<Shared.WSSend, Shared.WSRecv>" in client_text
    assert "connectWsRaw(" in client_text


def test_typescript_generation_allows_real_shared_group_without_alias_rewrite(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/shared") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "api" / "shared" / "gen_client.ts").is_file()
    assert (output_dir / "api" / "(shared)" / "gen_client.ts").is_file()
