from __future__ import annotations

import asyncio
import enum
import importlib
import py_compile
import sys
from pathlib import Path

import httpx
import pytest

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Error, Toast
from api_blueprint.engine.binary_schema import parse_binary_schema
from api_blueprint.engine.model import Array, Enum, FileField, Map, Model, String
from api_blueprint.writer.python import PythonClientWriter, PythonServerWriter


class Payload(Model):
    value = String(description="value")


class Result(Model):
    status = String(description="status")


class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")


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


def test_python_codegen_emits_multipart_and_raw_response_contracts(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    _compile_generated_files(client_dir)

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    _compile_generated_files(server_dir)

    client_types = (client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_types.py").read_text(encoding="utf-8")
    client_route = (client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_client.py").read_text(encoding="utf-8")
    client_transport = (client_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py").read_text(encoding="utf-8")
    server_service = (server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_service.py").read_text(encoding="utf-8")
    server_transport = (server_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py").read_text(encoding="utf-8")

    assert "image: ApiUploadFile" in client_types
    assert "multipart=_api_to_transport(multipart)" in client_route
    assert "response_type: str | None = 'bytes'" in client_route
    assert "ApiRawResponse[bytes]" in client_route
    assert "_split_multipart" in client_transport
    assert "return _raw_response(response)" in client_transport
    assert "bytes | ApiRawResponse[bytes]" in server_service
    assert "str | Path | ApiRawResponse[bytes]" in server_service
    assert "_multipart_body" in server_transport
    assert "filename=None" in server_transport
    assert "FileResponse(" in server_transport
    assert "StreamingResponse(" in server_transport


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


def test_python_client_generates_recursive_nested_dto_codecs(tmp_path: Path):
    class NestedItem(Model):
        value = String(description="value")

    class NestedResponse(Model):
        item = NestedItem(description="item")
        items = Array[NestedItem](description="items")
        item_map = Map[String, NestedItem](description="item map")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/nested").RSP(NestedResponse)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    package_root = output_dir / "api_blueprint_generated" / "api"
    types_text = (package_root / "routes" / "api" / "demo" / "gen_types.py").read_text(encoding="utf-8")
    assert "from typing import Any, Callable, Generic, Mapping, Self, TypeVar" in types_text
    assert "@dataclass(kw_only=True)\nclass NestedItem:" in types_text
    assert "class NestedResponse:" in types_text
    assert "item: NestedItem" in types_text
    assert "items: list[NestedItem]" in types_text
    assert "item_map: dict[str, NestedItem]" in types_text
    assert "def from_mapping(cls, value: Mapping[str, Any]) -> Self:" in types_text
    assert 'def from_value(cls, value: object, path: str = "NestedResponse") -> Self:' in types_text
    assert "def _from_mapping(cls, value: Mapping[str, Any], path: str) -> Self:" in types_text
    assert "-> NestedResponse:" not in types_text
    assert "def to_mapping(self) -> dict[str, Any]:" in types_text
    client_text = (package_root / "routes" / "api" / "demo" / "gen_client.py").read_text(encoding="utf-8")
    assert "_decode_map," in client_text
    assert "_decode_list," in client_text

    client_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_client",
    )
    response = client_module.NestedResponse.from_value(
        {
            "item": {"value": "one"},
            "items": [{"value": "two"}],
            "item_map": {"three": {"value": "three"}},
        }
    )

    assert isinstance(response, client_module.NestedResponse)
    assert isinstance(response.item, client_module.NestedItem)
    assert isinstance(response.items[0], client_module.NestedItem)
    assert isinstance(response.item_map["three"], client_module.NestedItem)
    assert response.to_mapping() == {
        "item": {"value": "one"},
        "items": [{"value": "two"}],
        "item_map": {"three": {"value": "three"}},
    }

    with pytest.raises(ValueError, match=r"NestedResponse\.item: missing required field"):
        client_module.NestedResponse.from_value({"items": [], "item_map": {}})

    with pytest.raises(TypeError, match=r"NestedResponse\.items: expected list"):
        client_module.NestedResponse.from_value({"item": {"value": "one"}, "items": {}, "item_map": {}})


def test_python_client_generates_enum_and_wire_name_codecs(tmp_path: Path):
    class WireEnum(enum.StrEnum):
        first = "first"
        second = "second"

    class StatusEnum(enum.IntEnum):
        ok = 1
        fail = 2

    class EnumPayload(Model):
        class_ = String(alias="class", description="reserved field")
        kind = Enum[WireEnum](description="kind")
        statuses = Array[Enum[StatusEnum]](description="statuses")
        status_map = Map[Enum[StatusEnum], Enum[WireEnum]](description="status map")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/enum").REQ(EnumPayload).RSP(EnumPayload)
        views.GET("/enum-list").RSP(Array[Enum[StatusEnum]](description="enum list"))

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    package_root = output_dir / "api_blueprint_generated" / "api"
    types_text = (package_root / "routes" / "api" / "demo" / "gen_types.py").read_text(encoding="utf-8")
    client_text = (package_root / "routes" / "api" / "demo" / "gen_client.py").read_text(encoding="utf-8")
    assert "class WireEnum(StrEnum):" in types_text
    assert "FIRST = \"first\"" in types_text
    assert "class StatusEnum(IntEnum):" in types_text
    assert "OK = 1" in types_text
    assert "class_: str" in types_text
    assert "kind: WireEnum" in types_text
    assert "statuses: list[StatusEnum]" in types_text
    assert "status_map: dict[StatusEnum, WireEnum]" in types_text
    assert 'value.get("class", _MISSING)' in types_text
    assert 'result["class"] = _api_to_json(self.class_)' in types_text
    assert "return lambda item, path:" not in client_text
    assert "return (lambda item, path: _decode_list" in client_text

    client_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_types",
    )
    payload = client_module.EnumJSON.from_value(
        {
            "class": "reserved",
            "kind": "first",
            "statuses": [1, "2"],
            "status_map": {"1": "second"},
        }
    )
    assert payload.kind is client_module.WireEnum.FIRST
    assert payload.statuses == [client_module.StatusEnum.OK, client_module.StatusEnum.FAIL]
    assert payload.status_map[client_module.StatusEnum.OK] is client_module.WireEnum.SECOND
    assert payload.to_mapping() == {
        "class": "reserved",
        "kind": "first",
        "statuses": [1, 2],
        "status_map": {"1": "second"},
    }


def test_python_server_json_encoder_handles_enum_map_keys_and_nested_dtos(tmp_path: Path):
    class StatusEnum(enum.IntEnum):
        ok = 1
        fail = 2

    class MapItem(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/map").RSP(Map[Enum[StatusEnum], MapItem](description="map"))

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    types_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_types",
    )
    adapter_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_server",
    )

    assert adapter_module._jsonable(
        {types_module.StatusEnum.OK: types_module.MapItem(value="ok")}
    ) == {"1": {"value": "ok"}}


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
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_error_lookup.py"
    ).read_text(encoding="utf-8")
    client_public_errors = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "errors.py"
    ).read_text(encoding="utf-8")
    assert "class ApiError(Exception):" in client_errors
    assert "class ApiErrorPayload:" in client_errors
    assert "def is_api_error(" in client_errors
    assert "class ApiToastSpec:" in client_errors
    assert "def resolve_api_toast(" in client_errors
    assert "ERROR_CATALOG_BY_ID" not in client_errors
    assert '"CommonErr.UNKNOWN"' not in client_errors
    assert '"CommonErr.UNKNOWN"' in client_catalog
    assert "API_ERRORS_BY_ID" in client_catalog
    assert "ROUTE_API_ERRORS_BY_CODE" in client_catalog
    assert "def lookup_api_error(" in client_catalog
    assert "TOKEN_EXPIRE: ApiErrorEntry = API_ERRORS_BY_ID[\"CommonErr.TOKEN_EXPIRE\"]" in client_catalog
    assert "class ApiErrors:" in client_catalog
    assert 'default="登录状态已失效，请重新登录"' in client_catalog
    assert "\\u767b" not in client_catalog
    assert "locales" not in client_catalog
    assert "from .gen_errors import *" in client_public_errors
    assert "from .gen_error_lookup import *" in client_public_errors
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
    assert "from .gen_types import (\n    SubmitJSON,\n    SubmitResponse,\n)" in service_text
    assert "json: SubmitJSON" in service_text
    assert "json: SubmitJSON | None" not in service_text
    assert ") -> SubmitResponse:" in service_text
    assert "class DemoServiceStub:" in service_text
    assert "from fastapi import APIRouter, WebSocket, Request, HTTPException, WebSocketDisconnect" in adapter_text
    assert "def create_router(" in adapter_text
    assert "await service.submit(" in adapter_text
    assert "await request.form()" in adapter_text
    assert "except (UnicodeDecodeError, json.JSONDecodeError) as err:" in adapter_text
    assert 'raise HTTPException(status_code=400, detail="invalid JSON body") from err' in adapter_text
    assert "parse_qs" not in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_binary_schema_service_contract_uses_raw_bytes(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    service_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_service.py"
    ).read_text(encoding="utf-8")
    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "binary: bytes | None" in service_text
    assert "binary: bytes | None = None" not in service_text
    assert "binary: dict[str, Any] | None = None" not in service_text
    assert "binary = await request.body()" in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_query_decoder_treats_empty_query_as_empty_object(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").ARGS(trace=String(description="trace", omitempty=True)).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "def _query_params(request: Request) -> dict[str, Any]:" in adapter_text
    assert "return values or None" not in adapter_text
    assert "return values" in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_adapter_qualifies_group_type_imports(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/abc").ARGS(arg1=String(description="arg1")).RSP(Result)
    with bp.group("/hello") as views:
        views.GET("/abc").ARGS(kind=String(description="kind")).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "from ...routes.api.demo import gen_types as api_demo_types" in adapter_text
    assert "from ...routes.api.hello import gen_types as api_hello_types" in adapter_text
    assert "from ...routes.api.demo.gen_types import" not in adapter_text
    assert "query = api_demo_types.AbcQuery.from_value(query_raw, \"query\")" in adapter_text
    assert "query = api_hello_types.AbcQuery.from_value(query_raw, \"query\")" in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_generates_connection_adapter_scaffolds(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
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
    assert "@router.api_route(\"/api/demo/events\", methods=[\"GET\"])" in adapter_text
    assert "@router.websocket(\"/api/demo/chat\")" in adapter_text
    assert "stream = _SseStream()" in adapter_text
    assert "async for chunk in stream:" in adapter_text
    assert "channel = _WebSocketChannel(websocket, api_demo_types.Event.from_value)" in adapter_text
    assert "except _WebSocketClosed:" in adapter_text
    assert "except (UnicodeDecodeError, json.JSONDecodeError) as err:" in adapter_text
    assert 'await self.abort(1003, "invalid WebSocket message")' in adapter_text
    assert "await service.chat(" in adapter_text
    assert "media_type=\"text/event-stream\"" in adapter_text
    service_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_service.py"
    ).read_text(encoding="utf-8")
    assert "stream: ApiServerStream[Event, EventsClose] | None = None" in service_text
    assert "channel: ApiServerChannel[Event, Event, ChatClose] | None = None" in service_text
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


def test_python_client_generates_connection_bridge_methods(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
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

    assert "class ApiSocketBridge(Protocol" not in runtime_text
    assert "def connect_socket(" not in runtime_text
    assert "def open_stream(" in runtime_text
    assert "def open_channel(" in runtime_text
    assert "def connect_ws(" not in route_text
    assert "return self._transport.connect_socket(" not in route_text
    assert "def subscribe_events(" in route_text
    assert "return self._transport.open_stream(" in route_text
    assert "def open_chat(" in route_text
    assert "return self._transport.open_channel(" in route_text
    assert "raise NotImplementedError" in transport_text
    assert "default httpx adapter" in transport_text
    _compile_generated_files(output_dir)


def test_python_client_and_server_generate_named_message_helpers(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class AssistantInput(Model):
        text = String(description="text")

    class AssistantCancel(Model):
        reason = String(description="reason")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    class AssistantDone(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )
        views.STREAM("/single-events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantSingleMessage",
            delta=AssistantDelta,
        )
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=AssistantInput,
            cancel=AssistantCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    client_types = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_types.py"
    ).read_text(encoding="utf-8")
    client_public = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "client.py"
    ).read_text(encoding="utf-8")

    assert "@dataclass(kw_only=True)\nclass AssistantClientMessage:" in client_types
    assert "data: Any = None" in client_types
    assert "@dataclass(kw_only=True)\nclass AssistantSingleMessage:" in client_types
    assert "class AssistantSingleMessageVariants:" in client_types
    assert "class AssistantClientMessageVariants:" in client_types
    assert "def cancel(data: AssistantCancel) -> AssistantClientMessage:" in client_types
    assert "@dataclass(kw_only=True)\nclass AssistantServerMessageHandlers(Generic[R]):" in client_types
    assert "def dispatch_assistant_server_message(" in client_types
    assert "class AssistantServerMessageDispatchError(Exception):" in client_types
    assert "kind: str = \"unknown_type\"" in client_types
    assert "from .gen_types import *" in client_public

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    server_types = (
        server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_types.py"
    ).read_text(encoding="utf-8")
    server_public = (
        server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "service.py"
    ).read_text(encoding="utf-8")

    assert "class AssistantClientMessageVariants:" in server_types
    assert "def dispatch_assistant_single_message(" in server_types
    assert "def dispatch_assistant_client_message(" in server_types
    assert "class AssistantClientMessageDispatchError(Exception):" in server_types
    assert "from .gen_types import *" in server_public
    _compile_generated_files(tmp_path)


def test_python_client_generates_binary_body_union_runtime_and_transport(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | Kind | 1 | const=1 | kind |
| flags | Flags | 1 | min=0 | flags |
| pad0 | padding | 1 | | pad |
| code | u24 | 1 | min=1,max=16777215 | code |
| delta | i24 | 1 | min=-8,max=8 | delta |
| payload_len | u16 | 1 | max=16,sizeof=payload | payload length |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | | payload |

## enum Kind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Reserved | 1..31 | const=0 | reserved |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "binary" / "gen_client.py"
    ).read_text(encoding="utf-8")
    schema_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.py"
    ).read_text(encoding="utf-8")
    types_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_types.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        output_dir / "api_blueprint_generated" / "api" / "runtime" / "binary" / "gen_runtime.py"
    ).read_text(encoding="utf-8")
    transport_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py"
    ).read_text(encoding="utf-8")

    assert "binary: DemoPacket | ApiBinaryBody" in route_text
    assert "binary=DemoPacketWire.to_binary_body(binary)" in route_text
    assert "from .gen_types import (" in route_text
    assert "from .gen_binary import *" in types_text
    assert "class DemoPacketKind:" in schema_text
    assert "class DemoPacketFlags:" in schema_text
    assert "reserved bits must be zero" in schema_text
    assert "writer.write_u24" in schema_text
    assert "writer.write_i24" in schema_text
    assert "writer.write_zeroes" in schema_text
    assert "class RawBinaryBody" in runtime_text
    assert "binary.to_bytes()" in transport_text
    assert not (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "wire.py"
    ).exists()
    _compile_generated_files(output_dir)


def test_python_binary_writer_uses_local_paths_and_wraps_boundaries_without_success_path_allocations(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | const=1,max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    schema_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        output_dir / "api_blueprint_generated" / "api" / "runtime" / "binary" / "gen_runtime.py"
    ).read_text(encoding="utf-8")

    assert 'raise wrap_binary_field("DemoPacket.header", err) from err' in schema_text
    assert 'raise wrap_binary_field("DemoPacket.body", err) from err' in schema_text
    assert 'write_demopacket_item(item, writer, state, path="")' in schema_text
    assert 'raise wrap_binary_index("items", index, err) from err' in schema_text
    assert 'path: str = "Item",' in schema_text
    assert 'require_range("id", int(value.id), 1, 2**63 - 1)' in schema_text
    assert "Item.id" not in schema_text
    assert "join_binary_path(" not in schema_text
    assert "index_binary_path(" not in schema_text
    assert "def join_binary_path(" in runtime_text
    assert "def index_binary_path(" in runtime_text
    assert "def wrap_binary_field(" in runtime_text
    assert "def wrap_binary_index(" in runtime_text
    _compile_generated_files(output_dir)


def test_python_binary_writer_reports_nested_schema_path(tmp_path: Path):
    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | const=1,max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api")
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    binary_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.binary.gen_binary",
    )
    runtime_module = importlib.import_module("api_blueprint_generated.api.runtime.binary")
    packet = binary_module.DemoPacket(
        header=binary_module.DemoPacketHeader(),
        body=binary_module.DemoPacketBody(items=[binary_module.DemoPacketItem(id=0)]),
    )

    with pytest.raises(runtime_module.BinaryEncodeError) as caught:
        binary_module.DemoPacketWire.to_binary_body(packet).to_bytes()

    assert caught.value.path == "DemoPacket.body.items[0].id"
    assert caught.value.message == "value 0 outside range 1..9223372036854775807"
    assert caught.value.detail == str(caught.value)
