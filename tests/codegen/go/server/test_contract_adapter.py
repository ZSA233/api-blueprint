from __future__ import annotations

from .helpers import *


def test_golang_writer_can_use_contract_graph_route_adapter(monkeypatch, tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    graph = build_contract_graph([bp])

    def reject_legacy_router_contract(_router):
        raise AssertionError("legacy router route_contract should not be used")

    monkeypatch.setattr(
        "api_blueprint.writer.core.contract_adapters.route_contract_from_router",
        reject_legacy_router_contract,
    )

    writer = GolangWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    interface_text = (output_dir / "routes" / "api" / "demo" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    assert "Ping(ctx *CTX_Ping, req *REQ_Ping)" in interface_text

def test_golang_contract_graph_adapter_owns_request_and_response_models(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.POST("/submit").ARGS(q=String(description="q")).REQ(SubmitJson).RSP(SubmitResponse)

    graph = build_contract_graph([bp])
    router.req_query = None
    router.req_json = None
    router.rsp_model = None

    writer = GolangWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_models = (output_dir / "routes" / "api" / "demo" / "gen_types.go").read_text(
        encoding="utf-8"
    )
    shared_models = (
        output_dir
        / "routes"
        / "api"
        / "_gen_types"
        / "types.go"
    ).read_text(encoding="utf-8")
    assert "type REQ_Submit_QUERY struct" in route_models
    assert "type REQ_Submit_JSON = types.SubmitJson" in route_models
    assert "type RSP_Submit_BODY = types.SubmitResponse" in route_models
    assert "type SubmitJson struct" in shared_models
    assert "type SubmitResponse struct" in shared_models
