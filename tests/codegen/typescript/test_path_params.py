from __future__ import annotations

from .helpers import *


class ItemPath(Model):
    item = String(description="item")
    badge = String(description="badge")


class Result(Model):
    status = String(description="status")


def test_typescript_client_generates_path_request_and_transport_expansion(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    runtime_text = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "path: Shared.ItemPath;" in route_text
    assert 'path: "/api/demo/path-echo/{item}/{badge}",' in route_text
    assert "pathParams: request.path as unknown as Record<string, unknown>," in route_text
    assert "pathParams?: Record<string, unknown>;" in runtime_text
    assert "function expandPath(path: string, params?: Record<string, unknown>): string" in transport_text
    assert "throw new Error(`missing path parameter: ${key}`);" in transport_text
    assert "return encodeURIComponent(String(value));" in transport_text
    assert "const url = this.buildUrl(path, query, pathParams);" in transport_text
