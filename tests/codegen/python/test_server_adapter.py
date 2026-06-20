from __future__ import annotations

from .helpers import *


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
    assert "class ApiServerConfig:" in runtime_text
    assert "class DemoService(Protocol):" in service_text
    assert "async def submit(" in service_text
    assert "from .gen_types import (\n    SubmitJSON,\n    SubmitResponse,\n)" in service_text
    assert "json: SubmitJSON" in service_text
    assert "json: SubmitJSON | None" not in service_text
    assert ") -> SubmitResponse:" in service_text
    assert "class DemoServiceStub:" in service_text
    assert "from fastapi import APIRouter, WebSocket, Request, HTTPException, WebSocketDisconnect" in adapter_text
    assert "def create_router(" in adapter_text
    assert "def create_demo_router(" in adapter_text
    assert "config: ApiServerConfig | None = None" in adapter_text
    assert "await service.submit(" in adapter_text
    assert "await request.form(max_part_size=config.multipart_part_max_bytes)" in adapter_text
    assert "PayloadTooLargeError" in adapter_text
    assert "asyncio.Queue(maxsize=max(1, queue_capacity))" in adapter_text
    assert "except (UnicodeDecodeError, json.JSONDecodeError) as err:" in adapter_text
    assert 'raise HTTPException(status_code=400, detail="invalid JSON body") from err' in adapter_text
    assert "parse_qs" not in adapter_text
    _compile_generated_files(output_dir)


def test_python_server_decodes_path_params_into_service_argument(tmp_path: Path):
    class ItemPath(Model):
        item = String(description="item")
        badge = String(description="badge")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/path-echo/{item}/{badge}", operation_id="PathEcho").REQ_PATH(ItemPath).RSP(Result)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    service_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_service.py"
    ).read_text(encoding="utf-8")
    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "path: PathEchoPath" in service_text
    assert 'path_raw = dict(request.path_params)' in adapter_text
    assert 'path = api_demo_types.PathEchoPath.from_value(path_raw, "path")' in adapter_text
    assert "path=path," in adapter_text
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
