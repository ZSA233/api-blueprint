from __future__ import annotations

from .helpers import *


def test_wails_go_writer_contract_graph_adapter_owns_request_and_response_models(tmp_path: Path):
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

    writer = WailsGoWriter(output_dir, version="v3", overlay_name="wailsv3", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    service_text = (
        output_dir / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go"
    ).read_text(encoding="utf-8")
    overlay_text = (
        output_dir / "transports" / "wailsv3" / "api" / "demo" / "gen_overlay.go"
    ).read_text(encoding="utf-8")
    assert "submitExecutor *sharedprovider.RouteExecutor[any, REQ_Submit_QUERY, REQ_Submit_JSON, RSP_Submit]" in service_text
    assert "BindJSON:  true" in service_text
    assert "type REQ_Submit_QUERY = sharedroutes.REQ_Submit_QUERY" in overlay_text
    assert "type REQ_Submit_JSON = sharedroutes.REQ_Submit_JSON" in overlay_text
