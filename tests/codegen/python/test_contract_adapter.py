from __future__ import annotations

from .helpers import *


def test_python_client_generation_uses_shared_route_selection(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/included").RSP(Result)
        views.GET("/excluded").RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir, include=("path:/api/demo/included",))
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_client.py"
    ).read_text(encoding="utf-8")
    assert "async def included(" in route_text
    assert "async def excluded(" not in route_text

def test_python_client_uses_contract_graph_route_protocol_models(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.POST("/submit").REQ(Payload).RSP(Result)

    graph = build_contract_graph([bp])
    router.req_json = None
    router.rsp_model = None

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_client.py"
    ).read_text(encoding="utf-8")
    assert "json: SubmitJSON" in route_text
    assert "response_type: str | None = 'SubmitResponse'" in route_text
    assert 'return SubmitResponse.from_value(payload, "submit.response")' in route_text
    assert "json: SubmitJSON | None" not in route_text

def test_python_client_writer_disambiguates_same_path_http_methods_with_contract_graph(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/settings") as views:
        views.GET("/current").RSP(Result)
        views.PUT("/current").RSP(Result)

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "settings" / "gen_client.py"
    ).read_text(encoding="utf-8")
    assert "async def current_get(" in route_text
    assert '        "GET",' in route_text
    assert "async def current_put(" in route_text
    assert '        "PUT",' in route_text
    _compile_generated_files(output_dir)
