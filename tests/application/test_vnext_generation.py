from __future__ import annotations

import json
from pathlib import Path

from api_blueprint.application import vnext


def _write_package(tmp_path: Path, source: str) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(source.strip() + "\n", encoding="utf-8")


def test_vnext_application_generate_writes_contract_and_grpc_proto(tmp_path: Path) -> None:
    _write_package(
        tmp_path,
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))
""",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json", "markdown"]

[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    vnext.generate(config_path, target_ids=("contract", "grpc.proto"))

    manifest = json.loads((tmp_path / "api-blueprint.contract.json").read_text(encoding="utf-8"))
    assert manifest["routes"][0]["id"] == "api.demo.get.ping"
    proto = tmp_path / "grpc" / "protos" / "api" / "demo.proto"
    assert proto.is_file()
    assert "rpc Ping (PingRequest) returns (PingResponse);" in proto.read_text(encoding="utf-8")


def test_vnext_application_check_honors_kotlin_target_exclude(tmp_path: Path) -> None:
    _write_package(
        tmp_path,
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String, Model

class Event(Model):
    value = String(description="value")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.STREAM("/events").SERVER_MESSAGE(Event)
""",
    )
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
exclude = ["path:/api/demo/events"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    vnext.check(config_path)


def test_vnext_application_generate_only_checks_selected_target_plan(tmp_path: Path) -> None:
    _write_package(
        tmp_path,
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String, Model

class Event(Model):
    value = String(description="value")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))
    views.STREAM("/events").SERVER_MESSAGE(Event)
""",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json"]

[[targets]]
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    vnext.generate(config_path, target_ids=("contract",))

    assert (tmp_path / "api-blueprint.contract.json").is_file()
