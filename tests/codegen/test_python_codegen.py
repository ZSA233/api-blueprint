from __future__ import annotations

import asyncio
import importlib
import py_compile
import sys
from pathlib import Path

import httpx

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Error, Toast
from api_blueprint.engine.model import Model, String
from api_blueprint.writer.python import PythonClientWriter, PythonServerWriter


class Payload(Model):
    value = String(description="value")


class Result(Model):
    status = String(description="status")


def _compile_generated_files(root: Path) -> None:
    for path in root.rglob("*.py"):
        py_compile.compile(str(path), doraise=True)


def _import_generated_module(output_dir: Path, module_name: str):
    for name in list(sys.modules):
        if name == "api_blueprint_generated" or name.startswith("api_blueprint_generated."):
            del sys.modules[name]
    sys.path.insert(0, str(output_dir))
    try:
        return importlib.import_module(module_name)
    finally:
        sys.path.remove(str(output_dir))


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
    assert "class DemoClient:" in route_text
    assert "async def ping(" in route_text
    assert "query: dict[str, Any] | None = None" in route_text
    assert "return await self._transport.request(" in route_text
    assert "class HttpClientTransport(ApiClientTransport):" in transport_text
    assert "async def request(" in transport_text
    assert user_client.read_text(encoding="utf-8") == "# user-owned client extension\n"
    _compile_generated_files(output_dir)


def test_python_client_and_server_generate_error_catalog_runtime(tmp_path: Path):
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    bp = Blueprint(root="/api", errors=[CommonErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(Result)

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    client_errors = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_errors.py"
    ).read_text(encoding="utf-8")
    client_catalog = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_error_catalog.py"
    ).read_text(encoding="utf-8")
    client_public_errors = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "errors.py"
    ).read_text(encoding="utf-8")
    assert "class ApiCodeError(Exception):" in client_errors
    assert "class ApiToastSpec:" in client_errors
    assert "def resolve_api_toast(" in client_errors
    assert "ERROR_CATALOG_BY_ID" not in client_errors
    assert '"CommonErr.UNKNOWN"' not in client_errors
    assert '"CommonErr.UNKNOWN"' in client_catalog
    assert "TOKEN_EXPIRE: ApiErrorCode = 55555" in client_catalog
    assert 'default="登录状态已失效，请重新登录"' in client_catalog
    assert "\\u767b" not in client_catalog
    assert "locales" not in client_catalog
    assert "from .gen_errors import *" in client_public_errors
    assert "from .gen_error_catalog import *" in client_public_errors
    client_errors_module = _import_generated_module(
        client_dir,
        "api_blueprint_generated.api.runtime.gen_errors",
    )
    payload = client_errors_module.ApiToastPayload(
        key="auth.token_expire",
        level="warning",
        default="登录状态已失效，请重新登录",
    )
    assert (
        client_errors_module.resolve_api_toast(
            payload,
            lambda key: "Sign in again" if key == "auth.token_expire" else None,
            "fallback",
        )
        == "Sign in again"
    )
    override = client_errors_module.ApiToastPayload(
        key="auth.token_expire.enterprise",
        level="warning",
        default="登录状态已失效，请重新登录",
        text="企业账号登录已失效，请重新绑定后继续使用",
    )
    assert client_errors_module.resolve_api_toast(override, lambda _key: "Sign in again", "fallback") == override.text
    assert (
        client_errors_module.resolve_api_toast(
            client_errors_module.ApiToastPayload(default="默认提示"),
            None,
            "fallback",
        )
        == "默认提示"
    )
    assert client_errors_module.resolve_api_toast(None, None, "fallback") == "fallback"

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    assert (server_dir / "api_blueprint_generated" / "api" / "runtime" / "errors.py").is_file()
    _compile_generated_files(tmp_path)


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
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        "from ....runtime.client import"
    )
    assert "\n\nclass DemoClient:" in client_text
    assert "async def health(self) -> Any:" in client_text
    assert "\n    async def submit(" in client_text
    assert "async def health(self) -> Any:" in service_text
    assert "class DemoService(Protocol):\n    async def health(self) -> Any:" in service_text
    assert "\n    async def ping(" in service_text
    assert "async def demo_health() -> Any:" in adapter_text
    assert "return await service.health()" in adapter_text
    assert (
        '@router.api_route("/api/demo/health", methods=["GET"])\n'
        "    async def demo_health() -> Any:"
    ) in adapter_text
    assert "StreamingResponse\n\nfrom ...routes.api.demo.service" in adapter_text
    assert "router = APIRouter()\n    demo_service_impl = demo_service or DemoServiceStub()" in adapter_text
    assert (
        "demo_service_impl = demo_service or DemoServiceStub()\n"
        "    meta_service_impl = meta_service or MetaServiceStub()"
    ) in adapter_text
    route_module = _import_generated_module(output_dir, "api_blueprint_generated.api.routes.api.demo.client")
    assert hasattr(route_module, "DemoClient")
    _compile_generated_files(output_dir)


def test_python_http_transport_performs_async_rpc_requests(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(Payload).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir, base_url="https://api.example.test")
    writer.register(bp)
    writer.gen()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.example.test/api/demo/submit?trace=1"
        assert request.headers["content-type"].startswith("application/json")
        assert request.read() == b'{"value":"abc"}'
        return httpx.Response(200, json={"status": "ok"})

    transport_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
    )
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = transport_module.HttpClientTransport(client=async_client)

    result = asyncio.run(
        transport.request(
            "POST",
            "/api/demo/submit",
            query={"trace": "1"},
            json={"value": "abc"},
        )
    )

    assert result == {"status": "ok"}


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


def test_python_server_generates_service_core_and_fastapi_adapter(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(Payload).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir, python_package_root="example.generated")
    writer.register(bp)
    writer.gen()

    package_root = output_dir / "example" / "generated" / "api"
    runtime_text = (package_root / "runtime" / "gen_server.py").read_text(encoding="utf-8")
    service_text = (package_root / "routes" / "api" / "demo" / "gen_service.py").read_text(encoding="utf-8")
    adapter_text = (package_root / "transports" / "http" / "gen_server.py").read_text(encoding="utf-8")

    assert "class ApiServerContext:" in runtime_text
    assert "class DemoService(Protocol):" in service_text
    assert "async def submit(" in service_text
    assert "json: dict[str, Any] | None = None" in service_text
    assert "class DemoServiceStub:" in service_text
    assert "from fastapi import APIRouter" in adapter_text
    assert "def create_router(" in adapter_text
    assert "await service.submit(" in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_generates_connection_adapter_scaffolds(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.WS("/ws").SEND(Event).RECV(Event)
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(Event).SERVER_MESSAGE(Event)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "from fastapi import APIRouter, WebSocket" in adapter_text
    assert "from starlette.responses import StreamingResponse" in adapter_text
    assert "@router.websocket(\"/api/demo/ws\")" in adapter_text
    assert "@router.api_route(\"/api/demo/events\", methods=[\"GET\"])" in adapter_text
    assert "@router.websocket(\"/api/demo/chat\")" in adapter_text
    assert "return StreamingResponse(result)" in adapter_text
    _compile_generated_files(output_dir)


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
    assert "json: dict[str, Any] | None = None" in route_text
    assert "response_type: str | None = 'Result'" in route_text


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


def test_python_client_generates_connection_bridge_methods(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.WS("/ws").SEND(Event).RECV(Event)
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(Event).SERVER_MESSAGE(Event)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_client.py"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_client.py").read_text(
        encoding="utf-8"
    )
    transport_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py"
    ).read_text(encoding="utf-8")

    assert "class ApiSocketBridge(Protocol" in runtime_text
    assert "def connect_socket(" in runtime_text
    assert "def open_stream(" in runtime_text
    assert "def open_channel(" in runtime_text
    assert "def connect_ws(" in route_text
    assert "return self._transport.connect_socket(" in route_text
    assert "def subscribe_events(" in route_text
    assert "return self._transport.open_stream(" in route_text
    assert "def open_chat(" in route_text
    assert "return self._transport.open_channel(" in route_text
    assert "raise NotImplementedError" in transport_text
    assert "default httpx adapter" in transport_text
    _compile_generated_files(output_dir)
