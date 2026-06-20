from __future__ import annotations

from .helpers import *


class ItemPath(Model):
    item = String(description="item")
    badge = String(description="badge")


class Result(Model):
    status = String(description="status")


def test_flutter_client_generates_path_request_and_transport_expansion(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    output_dir = tmp_path / "flutter"
    writer = FlutterWriter(output_dir, package="example_client", base_url="http://localhost:2333")
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "lib" / "src" / "api" / "routes" / "api" / "demo" / "gen_demo_api.dart"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "lib" / "src" / "api" / "runtime" / "gen_api_transport.dart").read_text(
        encoding="utf-8"
    )
    transport_text = (
        output_dir / "lib" / "src" / "api" / "transports" / "http" / "gen_http_api_transport.dart"
    ).read_text(encoding="utf-8")

    assert "required ItemPath path," in route_text
    assert 'path: "/api/demo/path-echo/{item}/{badge}",' in route_text
    assert "pathParams: path.toQueryMap()," in route_text
    assert "final Map<String, String?> pathParams;" in runtime_text
    assert "this.pathParams = const {}," in runtime_text
    assert "final url = _buildUrl(request.path, request.query, request.pathParams);" in transport_text
    assert "String _expandPath(String path, Map<String, String?> params)" in transport_text
    assert "return Uri.encodeComponent(value);" in transport_text
