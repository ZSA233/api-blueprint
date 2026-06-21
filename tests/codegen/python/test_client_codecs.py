from __future__ import annotations

from .helpers import *
from api_blueprint.engine import CodeMessageDataEnvelope, NoEnvelope
from api_blueprint.engine.model import Int, Int64, OneOf, LegacyStringID


def _import_generated_modules(output_dir: Path, *module_names: str):
    for name in list(sys.modules):
        if name == "api_blueprint_generated" or name.startswith("api_blueprint_generated."):
            del sys.modules[name]
    sys.path.insert(0, str(output_dir))
    try:
        return tuple(importlib.import_module(module_name) for module_name in module_names)
    finally:
        sys.path.remove(str(output_dir))


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
    assert "from typing import Any, Callable, Generic, Mapping, Protocol, Self, TypeVar" in types_text
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
        first = "first"  # First option
        second = "second"  # Second option

    class StatusEnum(enum.IntEnum):
        ok = 1  # Successful status
        fail = 2  # Failed status

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
    assert "FIRST = \"first\"  # First option" in types_text
    assert "class StatusEnum(IntEnum):" in types_text
    assert "OK = 1  # Successful status" in types_text
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

def test_python_client_decodes_top_level_array_response_when_list_alias_collides(tmp_path: Path):
    class Permission(Model):
        id = Int64(description="id")
        name = String(description="name")
        code = String(description="code")

    bp = Blueprint(root="/api")
    with bp.group("/base/role") as role:
        role.GET("/list").RSP(total=Int64(description="total"))
    with bp.group("/base/perm") as perm:
        perm.GET("/list").RSP(Array[Permission](description="permissions"))

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    route_root = output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "base"
    role_client = (route_root / "role" / "gen_client.py").read_text(encoding="utf-8")
    role_types = (route_root / "role" / "gen_types.py").read_text(encoding="utf-8")
    perm_client = (route_root / "perm" / "gen_client.py").read_text(encoding="utf-8")
    perm_types = (route_root / "perm" / "gen_types.py").read_text(encoding="utf-8")

    assert ") -> list[Permission]:" in perm_client
    assert "response_type: str | None = 'list[Permission]'" in perm_client
    assert "_decode_list(" in perm_client
    assert "Permission.from_value" in perm_client
    assert 'return ListResponse.from_value(payload, "list.response")' not in perm_client
    assert "@dataclass(kw_only=True)\nclass Permission:" in perm_types

    assert ") -> ListResponse:" in role_client
    assert "response_type: str | None = 'ListResponse'" in role_client
    assert 'return ListResponse.from_value(payload, "list.response")' in role_client
    assert "@dataclass(kw_only=True)\nclass ListResponse:" in role_types

def test_python_client_decodes_enveloped_rsp_empty_null_and_object_data(tmp_path: Path):
    class AdminEnvelope(CodeMessageDataEnvelope):
        __success_code__ = 200
        __success_message__ = "success"
        __envelope_fields__ = {
            "code": "code",
            "message": "msg",
            "data": "data",
            "error": "error",
        }

    bp = Blueprint(root="/api", response_envelope=AdminEnvelope)
    with bp.group("/system/agreement") as views:
        views.POST("/update").RSP_EMPTY()

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    route_root = output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "system" / "agreement"
    client_text = (route_root / "gen_client.py").read_text(encoding="utf-8")
    types_text = (route_root / "gen_types.py").read_text(encoding="utf-8")
    assert 'response_envelope={"name": "AdminEnvelope"' in client_text
    assert 'response_envelope={"name": "NoEnvelope"' not in client_text
    assert 'return UpdateResponse.from_empty_response_value(payload, "update.response")' in client_text
    assert "{} if payload is None else payload" not in client_text
    assert "def from_empty_response_value(" in types_text

    transport_module, route_module, types_module = _import_generated_modules(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_types",
    )

    async def call_with_data(data: object) -> object:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"code": 200, "msg": "success", "data": data})

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = transport_module.HttpClientTransport(base_url="https://example.test", client=async_client)
        try:
            client = route_module.SystemAgreementClient(transport)
            return await client.update()
        finally:
            await async_client.aclose()

    null_result = asyncio.run(call_with_data(None))
    object_result = asyncio.run(call_with_data({}))

    assert isinstance(null_result, types_module.UpdateResponse)
    assert isinstance(object_result, types_module.UpdateResponse)

    with pytest.raises(TypeError, match=r"update\.response: expected empty response"):
        asyncio.run(call_with_data({"unexpected": 1}))

def test_python_client_decodes_enveloped_explicit_empty_model_null_data(tmp_path: Path):
    class AdminEnvelope(CodeMessageDataEnvelope):
        __success_code__ = 200
        __success_message__ = "success"
        __envelope_fields__ = {
            "code": "code",
            "message": "msg",
            "data": "data",
            "error": "error",
        }

    class EmptyBody(Model):
        pass

    bp = Blueprint(root="/api", response_envelope=AdminEnvelope)
    with bp.group("/system/agreement") as views:
        views.POST("/update").RSP(EmptyBody)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    transport_module, route_module, types_module = _import_generated_modules(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_types",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 200, "msg": "success", "data": None})

    async def exercise() -> object:
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = transport_module.HttpClientTransport(base_url="https://example.test", client=async_client)
        try:
            client = route_module.SystemAgreementClient(transport)
            return await client.update()
        finally:
            await async_client.aclose()

    result = asyncio.run(exercise())

    assert isinstance(result, types_module.UpdateResponse)

def test_python_client_keeps_empty_response_null_strict_without_envelope(tmp_path: Path):
    bp = Blueprint(root="/api", response_envelope=NoEnvelope)
    with bp.group("/system/agreement") as views:
        views.POST("/update").RSP_EMPTY()

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    route_root = output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "system" / "agreement"
    client_text = (route_root / "gen_client.py").read_text(encoding="utf-8")
    assert 'return UpdateResponse.from_value(payload, "update.response")' in client_text

    transport_module, route_module = _import_generated_modules(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_client",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=None)

    async def exercise() -> None:
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = transport_module.HttpClientTransport(base_url="https://example.test", client=async_client)
        try:
            client = route_module.SystemAgreementClient(transport)
            await client.update()
        finally:
            await async_client.aclose()

    with pytest.raises(TypeError, match=r"update\.response: expected object"):
        asyncio.run(exercise())

def test_python_client_keeps_non_empty_enveloped_null_data_strict(tmp_path: Path):
    class AdminEnvelope(CodeMessageDataEnvelope):
        __success_code__ = 200
        __success_message__ = "success"
        __envelope_fields__ = {
            "code": "code",
            "message": "msg",
            "data": "data",
            "error": "error",
        }

    bp = Blueprint(root="/api", response_envelope=AdminEnvelope)
    with bp.group("/system/agreement") as views:
        views.POST("/update").RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    route_root = output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "system" / "agreement"
    client_text = (route_root / "gen_client.py").read_text(encoding="utf-8")
    assert "{} if payload is None else payload" not in client_text

    transport_module, route_module = _import_generated_modules(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
        "api_blueprint_generated.api.routes.api.system.agreement.gen_client",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 200, "msg": "success", "data": None})

    async def exercise() -> None:
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        transport = transport_module.HttpClientTransport(base_url="https://example.test", client=async_client)
        try:
            client = route_module.SystemAgreementClient(transport)
            await client.update()
        finally:
            await async_client.aclose()

    with pytest.raises(TypeError, match=r"update\.response: expected object"):
        asyncio.run(exercise())


def test_python_client_decodes_legacy_json_compat_fields(tmp_path: Path):
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        ids = Array[OneOf(String(), Int())](description="ids")
        normalized = Array[LegacyStringID](description="normalized")
        room_id = LegacyStringID(alias="roomId", description="room id")

    bp = Blueprint(root="/api")
    with bp.group("/legacy") as views:
        views.GET("/payload").RSP(LegacyPayload)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    types_text = (
        output_dir
        / "api_blueprint_generated"
        / "api"
        / "routes"
        / "api"
        / "legacy"
        / "gen_types.py"
    ).read_text(encoding="utf-8")
    assert "target: str | list[str]" in types_text
    assert "ids: list[str | int]" in types_text
    assert "normalized: list[str]" in types_text
    assert "_decode_coerce_string" in types_text
    assert "_decode_one_of" in types_text

    types_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.legacy.gen_types",
    )
    response = types_module.PayloadResponse.from_value(
        {
            "target": ["a"],
            "ids": ["1", 2],
            "normalized": ["1", 2, "3"],
            "roomId": 100,
        }
    )

    assert response.target == ["a"]
    assert response.ids == ["1", 2]
    assert response.normalized == ["1", "2", "3"]
    assert response.room_id == "100"
    assert response.to_mapping()["roomId"] == "100"

    with pytest.raises(TypeError, match=r"PayloadResponse\.target: expected one of declared JSON shapes"):
        types_module.PayloadResponse.from_value(
            {"target": 1, "ids": [], "normalized": [], "roomId": "room"}
        )

    with pytest.raises(TypeError, match=r"PayloadResponse\.roomId: expected string or integer"):
        types_module.PayloadResponse.from_value(
            {"target": "ok", "ids": [], "normalized": [], "roomId": True}
        )

def test_python_http_transport_performs_async_rpc_requests(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(Payload).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir, base_url="https://api.example.test")
    writer.register(bp)
    writer.gen()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-trace-id"] in {"rpc-123", "stream-123"}
        timeout = request.extensions["timeout"]
        if request.url.path.endswith("/stream"):
            assert request.method == "GET"
            assert timeout["connect"] == 2.5
            return httpx.Response(200, content=b"chunk")
        assert request.method == "POST"
        assert str(request.url) == "https://api.example.test/api/demo/submit?trace=1"
        assert timeout["connect"] == 1.5
        assert request.headers["content-type"].startswith("application/json")
        assert request.read() == b'{"value":"abc"}'
        return httpx.Response(200, json={"status": "ok"})

    transport_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.transports.http.gen_client",
    )
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = transport_module.HttpClientTransport(client=async_client)

    async def exercise_transport() -> dict[str, object]:
        result = await transport.request(
            transport_module.ApiRequest(
                method="POST",
                path="/api/demo/submit",
                query={"trace": "1"},
                json={"value": "abc"},
                headers={"X-Trace-Id": "rpc-123"},
                timeout=1.5,
            )
        )
        stream = await transport.request(
            transport_module.ApiRequest(
                method="GET",
                path="/api/demo/stream",
                response_type="stream",
                headers={"X-Trace-Id": "stream-123"},
                timeout=2.5,
            )
        )
        await stream.aclose()
        return result

    result = asyncio.run(exercise_transport())

    assert result == {"status": "ok"}


def test_python_rpc_methods_forward_request_options_to_transport(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()
    _compile_generated_files(output_dir)

    client_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_client",
    )

    class CaptureTransport:
        def __init__(self) -> None:
            self.captured_request: object | None = None

        async def request(self, request: object) -> dict[str, str]:
            self.captured_request = request
            return {"status": "ok"}

    transport = CaptureTransport()
    client = client_module.DemoClient(transport)

    result = asyncio.run(client.ping(headers={"X-Trace-Id": "rpc-123"}, timeout=1.5))

    assert result.status == "ok"
    assert transport.captured_request is not None
    assert transport.captured_request.headers == {"X-Trace-Id": "rpc-123"}
    assert transport.captured_request.timeout == 1.5
