from __future__ import annotations

from .helpers import *


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
    models_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_types.ts").read_text(encoding="utf-8")
    assert "query?: Types.SubmitQuery;" in client_text
    assert "json?: Shared.SubmitJson;" in client_text
    assert "Promise<Shared.SubmitResponse>" in client_text
    assert "export type SubmitResponse = SubmitResponse;" not in models_text

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
