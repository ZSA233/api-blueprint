from __future__ import annotations

from .helpers import *


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
            "POST",
            "/api/demo/submit",
            query={"trace": "1"},
            json={"value": "abc"},
            headers={"X-Trace-Id": "rpc-123"},
            timeout=1.5,
        )
        stream = await transport.request(
            "GET",
            "/api/demo/stream",
            response_type="stream",
            headers={"X-Trace-Id": "stream-123"},
            timeout=2.5,
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
            self.kwargs: dict[str, object] | None = None

        async def request(self, method: str, path: str, **kwargs: object) -> dict[str, str]:
            self.kwargs = kwargs
            return {"status": "ok"}

    transport = CaptureTransport()
    client = client_module.DemoClient(transport)

    result = asyncio.run(client.ping(headers={"X-Trace-Id": "rpc-123"}, timeout=1.5))

    assert result.status == "ok"
    assert transport.kwargs is not None
    assert transport.kwargs["headers"] == {"X-Trace-Id": "rpc-123"}
    assert transport.kwargs["timeout"] == 1.5
