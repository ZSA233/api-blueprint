from __future__ import annotations

from .helpers import *


class ItemPath(Model):
    item = String(description="item")
    badge = String(description="badge")


class Result(Model):
    status = String(description="status")


def test_kotlin_client_and_server_generate_path_requests(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    client_dir = tmp_path / "client"
    client_writer = KotlinWriter(client_dir, package="com.example.generated", base_url="http://localhost:2333")
    client_writer.register(bp)
    client_writer.gen()

    server_dir = tmp_path / "server"
    server_writer = KotlinServerWriter(server_dir, package="com.example.generated")
    server_writer.register(bp)
    server_writer.gen()

    client_route = (
        client_dir / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoApi.kt"
    ).read_text(encoding="utf-8")
    runtime_text = (
        client_dir / "com" / "example" / "generated" / "api" / "runtime" / "GenApiTransport.kt"
    ).read_text(encoding="utf-8")
    transport_text = (
        client_dir / "com" / "example" / "generated" / "api" / "transports" / "http" / "GenOkHttpApiTransport.kt"
    ).read_text(encoding="utf-8")
    server_route = (
        server_dir
        / "com"
        / "example"
        / "generated"
        / "api"
        / "transports"
        / "ktor"
        / "api"
        / "demo"
        / "GenDemoKtorRoutes.kt"
    ).read_text(encoding="utf-8")
    service_text = (
        server_dir / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoService.kt"
    ).read_text(encoding="utf-8")

    assert "path: ItemPath," in client_route
    assert 'path = "/api/demo/path-echo/{item}/{badge}",' in client_route
    assert "pathParams = path.toQueryMap()," in client_route
    assert "public val pathParams: Map<String, String?> = emptyMap()," in runtime_text
    assert "private fun expandPath(path: String, params: Map<String, String?>): String" in transport_text
    assert 'throw IllegalArgumentException("missing path parameter: $name")' in transport_text
    assert 'get("/api/demo/path-echo/{item}/{badge}")' in server_route
    assert "decodeParameters(call.parameters, ItemPath.serializer())" in server_route
    assert "path: ItemPath" in service_text
