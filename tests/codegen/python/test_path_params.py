from __future__ import annotations

from .helpers import *


def test_python_client_expands_path_params(tmp_path: Path):
    class ItemPath(Model):
        item = String(description="item")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/items/{item}", operation_id="GetItem").REQ_PATH(ItemPath).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    package_root = output_dir / "api_blueprint_generated" / "api"
    runtime_text = (package_root / "runtime" / "gen_client.py").read_text(encoding="utf-8")
    route_text = (package_root / "routes" / "api" / "demo" / "gen_client.py").read_text(encoding="utf-8")
    transport_text = (package_root / "transports" / "http" / "gen_client.py").read_text(encoding="utf-8")

    assert "path_params: Mapping[str, Any] | None = None" in runtime_text
    assert "path: GetItemPath" in route_text
    assert "path_params=_api_to_json(path)" in route_text
    assert 'path="/api/demo/items/{item}"' in route_text
    assert 'quote(str(value), safe="")' in transport_text

    client_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_client",
    )
    types_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_types",
    )

    class FakeTransport:
        request_obj = None

        async def request(self, request):
            self.request_obj = request
            return {"status": "ok"}

    transport = FakeTransport()
    client = client_module.DemoClient(transport)
    response = asyncio.run(client.get_item(types_module.GetItemPath(item="hello world")))

    assert response.status == "ok"
    assert transport.request_obj.path == "/api/demo/items/{item}"
    assert transport.request_obj.path_params == {"item": "hello world"}
