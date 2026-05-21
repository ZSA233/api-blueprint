from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from api_blueprint.application import generator


def _write_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "blueprints"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model, String

class SubmitJson(Model):
    value = String(description="value")

class SubmitResponse(Model):
    status = String(description="status")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.POST("/submit").ARGS(q=String(description="q")).REQ(SubmitJson).RSP(SubmitResponse)
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_go_mod(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _reject_router_fallback(_router: object) -> object:
    raise AssertionError("1.0 generation must pass ContractGraph to writer")


def test_vnext_generate_go_uses_contract_graph_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_package(tmp_path)
    _write_go_mod(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("api_blueprint.writer.golang.route_view.route_protocol_from_router", _reject_router_fallback)

    generator.generate(config_path, target_ids=("go.server",))

    assert (tmp_path / "golang" / "routes" / "api" / "demo" / "gen_types.go").is_file()


def test_vnext_generate_typescript_uses_contract_graph_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("api_blueprint.writer.typescript.blueprint.route_protocol_from_router", _reject_router_fallback)

    generator.generate(config_path, target_ids=("typescript.client",))

    assert (tmp_path / "typescript" / "api" / "routes" / "api" / "demo" / "gen_client.ts").is_file()


def test_vnext_generate_kotlin_uses_contract_graph_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.generated"
base_url = "http://localhost:2333"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("api_blueprint.writer.kotlin.blueprint.route_protocol_from_router", _reject_router_fallback)

    generator.generate(config_path, target_ids=("kotlin.client",))

    assert (
        tmp_path / "kotlin" / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoApi.kt"
    ).is_file()


def test_vnext_generate_flutter_uses_contract_graph_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "flutter.client"
kind = "flutter-client"
out_dir = "flutter"
package = "api_blueprint_example"
base_url = "http://localhost:2333"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("api_blueprint.writer.flutter.blueprint.route_protocol_from_router", _reject_router_fallback)

    generator.generate(config_path, target_ids=("flutter.client",))

    assert (tmp_path / "flutter" / "lib" / "src" / "api" / "routes" / "api" / "demo" / "gen_demo_api.dart").is_file()


def test_vnext_generate_python_client_target(tmp_path: Path) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "python.client"
kind = "python-client"
out_dir = "python"
python_package_root = "example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    generator.generate(config_path, target_ids=("python.client",))

    generated = tmp_path / "python" / "example" / "generated" / "api"
    assert (generated / "runtime" / "gen_client.py").is_file()
    assert (generated / "routes" / "api" / "demo" / "gen_client.py").is_file()
    assert (generated / "transports" / "http" / "gen_client.py").is_file()
    py_compile.compile(str(generated / "routes" / "api" / "demo" / "gen_client.py"), doraise=True)


def test_vnext_generate_python_server_target(tmp_path: Path) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "python.server"
kind = "python-server"
out_dir = "python"
python_package_root = "example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    generator.generate(config_path, target_ids=("python.server",))

    generated = tmp_path / "python" / "example" / "generated" / "api"
    assert (generated / "runtime" / "gen_server.py").is_file()
    assert (generated / "routes" / "api" / "demo" / "gen_service.py").is_file()
    assert (generated / "transports" / "http" / "gen_server.py").is_file()
    py_compile.compile(str(generated / "routes" / "api" / "demo" / "gen_service.py"), doraise=True)


def test_vnext_generate_wails_uses_contract_graph_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_package(tmp_path)
    _write_go_mod(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/generated"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "desktop.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("api_blueprint.writer.golang.route_view.route_protocol_from_router", _reject_router_fallback)
    monkeypatch.setattr("api_blueprint.writer.typescript.blueprint.route_protocol_from_router", _reject_router_fallback)
    monkeypatch.setattr("api_blueprint.writer.wails.golang.route_protocol_from_router", _reject_router_fallback)

    generator.generate(config_path, target_ids=("desktop.v3",))

    assert (tmp_path / "golang" / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go").is_file()


def test_vnext_generate_grpc_stub_target_generates_proto_dependency_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_package(tmp_path)
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"

[[targets]]
id = "grpc.go"
kind = "grpc-go"
proto = "grpc.proto"
out_dir = "grpc/go"
files = ["api/**/*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_generate_go_stubs(proto_root: Path, target: object) -> None:
        captured["proto_root"] = proto_root
        captured["target"] = target
        captured["proto_exists"] = (proto_root / "api" / "demo.proto").is_file()

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.generate_go_stubs", fake_generate_go_stubs)

    generator.generate(config_path, target_ids=("grpc.go",))

    assert captured["proto_root"] == (tmp_path / "grpc" / "protos").resolve()
    assert captured["proto_exists"] is True
