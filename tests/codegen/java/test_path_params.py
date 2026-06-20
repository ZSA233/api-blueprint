from __future__ import annotations

from .helpers import *


class ItemPath(Model):
    item = String(description="item")
    badge = String(description="badge")


def test_java_client_and_server_generate_path_requests(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    graph = build_contract_graph([bp])
    client_dir = tmp_path / "client"
    server_dir = tmp_path / "server"

    client_writer = JavaClientWriter(
        client_dir,
        package="com.example.generated",
        base_url="http://localhost:2333",
        contract_graph=graph,
    )
    client_writer.register(bp)
    client_writer.gen()

    server_writer = JavaServerWriter(
        server_dir,
        package="com.example.generated",
        contract_graph=graph,
        spring_public_paths=("/api/**",),
    )
    server_writer.register(bp)
    server_writer.gen()

    client_route = (
        client_dir / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoApi.java"
    ).read_text(encoding="utf-8")
    runtime_text = (
        client_dir / "com" / "example" / "generated" / "api" / "runtime" / "GenApiRequest.java"
    ).read_text(encoding="utf-8")
    transport_text = (
        client_dir
        / "com"
        / "example"
        / "generated"
        / "api"
        / "transports"
        / "http"
        / "GenJdkHttpApiTransport.java"
    ).read_text(encoding="utf-8")
    controller_text = (
        server_dir
        / "com"
        / "example"
        / "generated"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "controllers"
        / "GenDemoController.java"
    ).read_text(encoding="utf-8")
    binder_text = (
        server_dir / "com" / "example" / "generated" / "api" / "spring" / "GenSpringRequestBinder.java"
    ).read_text(encoding="utf-8")

    assert "GenApiTypes.ItemPath path" in client_route
    assert '"/api/demo/path-echo/{item}/{badge}",' in client_route
    assert "Object pathParams," in runtime_text
    assert "pathParams = pathParams == null ? Map.of() : pathParams;" in runtime_text
    assert "String url = url(request.path(), request.query(), request.pathParams());" in transport_text
    assert "private String expandPath(String path, Object pathParams)" in transport_text
    assert 'throw new IllegalArgumentException("missing path parameter: " + name);' in transport_text
    assert '@PathVariable Map<String, String> pathVariables' in controller_text
    assert "GenApiTypes.ItemPath path;" in controller_text
    assert "path = GenSpringRequestBinder.bindPath(pathVariables, GenApiTypes.ItemPath.class);" in controller_text
    assert "return ResponseEntity.badRequest().build();" in controller_text
    assert "public static <T> T bindPath(Map<String, String> values, Class<T> type)" in binder_text
