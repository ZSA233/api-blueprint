from __future__ import annotations

from .helpers import *


class ItemPath(Model):
    item = String(description="item")
    badge = String(description="badge")


class Result(Model):
    status = String(description="status")


def test_swift_client_generates_path_request_and_transport_expansion(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    output_dir = tmp_path / "swift"
    writer = SwiftWriter(
        output_dir,
        package="ExampleClient",
        module="ExampleClient",
        base_url="http://localhost:2333",
    )
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir
        / "Sources"
        / "ExampleClientAPIRoutes"
        / "API"
        / "Routes"
        / "API"
        / "Demo"
        / "GenDemoAPI.swift"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "Sources" / "ExampleClientRuntime" / "GenAPITransport.swift").read_text(
        encoding="utf-8"
    )
    transport_text = (
        output_dir
        / "Sources"
        / "ExampleClientRuntime"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")

    assert "path: ItemPath," in route_text
    assert 'path: "/api/demo/path-echo/{item}/{badge}",' in route_text
    assert "pathParams: path.toQueryItems()," in route_text
    assert "public var pathParams: [URLQueryItem]" in runtime_text
    assert "pathParams: [URLQueryItem] = []," in runtime_text
    assert "let url = try buildURL(path: request.path, query: request.query, pathParams: request.pathParams)" in transport_text
    assert "private func expandPath(_ path: String, pathParams: [URLQueryItem]) throws -> String" in transport_text
    assert 'throw APITransportError.invalidURL("missing path parameter: \\(name)")' in transport_text
