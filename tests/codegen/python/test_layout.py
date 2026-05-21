from __future__ import annotations

from .helpers import *


def test_python_routes_mirror_full_route_path_and_migrate_legacy_passthroughs(tmp_path: Path):
    bp = Blueprint(root="/api")
    bp.GET("/status").RSP(Result)
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(Result)

    client_dir = tmp_path / "client"
    client_package = client_dir / "api_blueprint_generated" / "api"
    legacy_demo_client = client_package / "routes" / "demo" / "client.py"
    legacy_root_client = client_package / "routes" / "root" / "client.py"
    legacy_demo_client.parent.mkdir(parents=True)
    legacy_root_client.parent.mkdir(parents=True)
    legacy_demo_client.write_text("# custom legacy demo client\n", encoding="utf-8")
    legacy_root_client.write_text("# custom legacy root client\n", encoding="utf-8")

    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()

    assert (client_package / "routes" / "api" / "demo" / "gen_client.py").is_file()
    assert (client_package / "routes" / "api" / "demo" / "client.py").read_text(encoding="utf-8") == (
        "# custom legacy demo client\n"
    )
    assert (client_package / "routes" / "api" / "gen_client.py").is_file()
    assert (client_package / "routes" / "api" / "client.py").read_text(encoding="utf-8") == (
        "# custom legacy root client\n"
    )
    assert not (client_package / "routes" / "root" / "gen_client.py").exists()

    server_dir = tmp_path / "server"
    server_package = server_dir / "api_blueprint_generated" / "api"
    legacy_demo_service = server_package / "routes" / "demo" / "service.py"
    legacy_root_service = server_package / "routes" / "root" / "service.py"
    legacy_demo_service.parent.mkdir(parents=True)
    legacy_root_service.parent.mkdir(parents=True)
    legacy_demo_service.write_text("# custom legacy demo service\n", encoding="utf-8")
    legacy_root_service.write_text("# custom legacy root service\n", encoding="utf-8")

    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()

    assert (server_package / "routes" / "api" / "demo" / "gen_service.py").is_file()
    assert (server_package / "routes" / "api" / "demo" / "service.py").read_text(encoding="utf-8") == (
        "# custom legacy demo service\n"
    )
    assert (server_package / "routes" / "api" / "gen_service.py").is_file()
    assert (server_package / "routes" / "api" / "service.py").read_text(encoding="utf-8") == (
        "# custom legacy root service\n"
    )
    assert not (server_package / "routes" / "root" / "gen_service.py").exists()
    _compile_generated_files(tmp_path)

def test_python_client_generates_package_root_layout_and_preserves_user_files(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").ARGS(q=String(description="q")).RSP(Result)

    output_dir = tmp_path / "python"
    user_client = output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "client.py"
    user_client.parent.mkdir(parents=True)
    user_client.write_text("# user-owned client extension\n", encoding="utf-8")

    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    package_root = output_dir / "api_blueprint_generated" / "api"
    runtime_text = (package_root / "runtime" / "gen_client.py").read_text(encoding="utf-8")
    route_text = (package_root / "routes" / "api" / "demo" / "gen_client.py").read_text(encoding="utf-8")
    transport_text = (package_root / "transports" / "http" / "gen_client.py").read_text(encoding="utf-8")

    assert "class ApiClientTransport(Protocol):" in runtime_text
    assert "async def request(" in runtime_text
    assert "class ApiStreamBridge(Protocol" in runtime_text
    assert "class ApiChannelBridge(ApiStreamBridge" in runtime_text
    assert "ApiClientTransport" in route_text
    types_text = (package_root / "routes" / "api" / "demo" / "gen_types.py").read_text(encoding="utf-8")
    codec_text = (package_root / "runtime" / "gen_codecs.py").read_text(encoding="utf-8")

    assert "class DemoClient:" in route_text
    assert "from .gen_types import (" in route_text
    assert "class PingQuery:" in types_text
    assert "from ....runtime.gen_codecs import (" in types_text
    assert "def _decode_str(" not in types_text
    assert "def _api_to_json(" not in types_text
    assert "def _decode_str(" in codec_text
    assert "def _api_to_json(" in codec_text
    assert "async def ping(" in route_text
    assert "query: PingQuery" in route_text
    assert "query: PingQuery | None" not in route_text
    assert "query=_api_to_json(query)" in route_text
    assert 'return PingResponse.from_value(payload, "ping.response")' in route_text
    assert "class HttpClientTransport(ApiClientTransport):" in transport_text
    assert "async def request(" in transport_text
    assert (package_root / "client.py").read_text(encoding="utf-8") == "from .gen_client import *\n"
    assert "def create_client(" in (package_root / "gen_client.py").read_text(encoding="utf-8")
    assert user_client.read_text(encoding="utf-8") == "# user-owned client extension\n"
    _compile_generated_files(output_dir)

def test_python_generated_files_use_pep8_blank_line_spacing(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/health").RSP(Result)
        views.GET("/ping").ARGS(q=String(description="q")).RSP(Result)
        views.POST("/submit").REQ(Payload).RSP(Result)
    with bp.group("/meta") as views:
        views.GET("/status").RSP(Result)

    output_dir = tmp_path / "python"
    client_writer = PythonClientWriter(output_dir)
    client_writer.register(bp)
    client_writer.gen()
    server_writer = PythonServerWriter(output_dir / "server")
    server_writer.register(bp)
    server_writer.gen()

    generated_files = tuple(output_dir.rglob("*.py"))
    assert generated_files
    for path in generated_files:
        text = path.read_text(encoding="utf-8")
        assert "\n\n\n\n" not in text, path
        assert "\n\n\n    " not in text, path
        assert "(\n\n" not in text, path
        assert ",\n\n" not in text, path
        assert ":\n\n    " not in text, path

    client_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_client.py"
    ).read_text(encoding="utf-8")
    service_text = (
        output_dir
        / "server"
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_service.py"
    ).read_text(encoding="utf-8")
    adapter_text = (
        output_dir
        / "server"
        / "api_blueprint_generated"
        / "api"
        / "transports"
        / "http"
        / "gen_server.py"
    ).read_text(encoding="utf-8")
    assert client_text.startswith(
        "# Code generated by api-blueprint (Python client); DO NOT EDIT.\n"
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        "from ....runtime.client import"
    )
    assert service_text.startswith("# Code generated by api-blueprint (Python server); DO NOT EDIT.\n")
    assert adapter_text.startswith("# Code generated by api-blueprint (Python server); DO NOT EDIT.\n")
    assert "\n\nclass DemoClient:" in client_text
    assert "async def health(self) -> HealthResponse:" in client_text
    assert "\n    async def submit(" in client_text
    assert "async def health(self) -> HealthResponse:" in service_text
    assert "class DemoService(Protocol):\n    async def health(self) -> HealthResponse:" in service_text
    assert "\n    async def ping(" in service_text
    assert "async def demo_health(request: Request) -> Any:" in adapter_text
    assert "result = await service.health(" in adapter_text
    assert "return _wrap_response(" in adapter_text
    assert (
        '@router.api_route("/api/demo/health", methods=["GET"])\n'
        "    async def demo_health(request: Request) -> Any:"
    ) in adapter_text
    assert "from starlette.responses import StreamingResponse, JSONResponse" in adapter_text
    assert "from ...routes.api.demo.service" in adapter_text
    assert "router = APIRouter()\n    demo_service_impl = demo_service or DemoServiceStub()" in adapter_text
    assert (
        "demo_service_impl = demo_service or DemoServiceStub()\n"
        "    meta_service_impl = meta_service or MetaServiceStub()"
    ) in adapter_text
    route_module = _import_generated_module(output_dir, "api_blueprint_generated.api.routes.api.demo.client")
    assert hasattr(route_module, "DemoClient")
    _compile_generated_files(output_dir)
