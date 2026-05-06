from __future__ import annotations

from pathlib import Path

import pytest

from api_blueprint.application import vnext


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
    raise AssertionError("vNext generation must pass ContractGraph to writer")


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
    monkeypatch.setattr("api_blueprint.writer.golang.blueprint.route_protocol_from_router", _reject_router_fallback)

    vnext.generate(config_path, target_ids=("go.server",))

    assert (tmp_path / "golang" / "views" / "routes" / "api" / "demo" / "gen_protos.go").is_file()


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

    vnext.generate(config_path, target_ids=("typescript.client",))

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

    vnext.generate(config_path, target_ids=("kotlin.client",))

    assert (tmp_path / "kotlin" / "com" / "example" / "generated" / "endpoints" / "DemoApi.kt").is_file()


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
    monkeypatch.setattr("api_blueprint.writer.golang.blueprint.route_protocol_from_router", _reject_router_fallback)
    monkeypatch.setattr("api_blueprint.writer.typescript.blueprint.route_protocol_from_router", _reject_router_fallback)
    monkeypatch.setattr("api_blueprint.writer.wails.golang.route_protocol_from_router", _reject_router_fallback)

    vnext.generate(config_path, target_ids=("desktop.v3",))

    assert (tmp_path / "golang" / "views" / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go").is_file()
