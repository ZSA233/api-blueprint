from __future__ import annotations

import json
import logging
from pathlib import Path

from api_blueprint import __version__
from api_blueprint.application import generator


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

    generator.generate(config_path, target_ids=("contract", "grpc.proto"))

    manifest = json.loads((tmp_path / "api-blueprint.contract.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.0"
    assert manifest["generator"]["version"] == __version__
    assert manifest["routes"][0]["id"] == "api.demo.get.ping"
    proto = tmp_path / "grpc" / "protos" / "api" / "demo.proto"
    assert proto.is_file()
    assert "rpc Ping (PingRequest) returns (PingResponse);" in proto.read_text(encoding="utf-8")


def test_vnext_application_generate_logs_grpc_target_lifecycle(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
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

    def fake_generate_go_stubs(proto_root: Path, target: object) -> None:
        return None

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.generate_go_stubs", fake_generate_go_stubs)
    caplog.set_level(logging.INFO)

    generator.generate(config_path, target_ids=("grpc.go",))

    messages = [record.getMessage().replace("\\", "/") for record in caplog.records]
    assert any("[*] Generating target: grpc.proto (grpc-proto)" in message for message in messages)
    assert any("[*] Generating target: grpc.go (grpc-go)" in message for message in messages)
    assert any("[.] Skipped target: grpc.proto (already generated)" in message for message in messages)
    assert any("[+] Written:" in message and "grpc/protos/api/demo.proto" in message for message in messages)


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

    generator.check(config_path)


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

    generator.generate(config_path, target_ids=("contract",))

    assert (tmp_path / "api-blueprint.contract.json").is_file()


def test_generator_contract_target_defaults_to_index_only(tmp_path: Path) -> None:
    _write_package(
        tmp_path,
        """
from api_blueprint.engine import Blueprint, Model
from api_blueprint.engine.model import String

class PingResult(Model):
    message = String(description="message")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(PingResult)
""",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[contract]]
id = "contract"
out_dir = "."
""".strip()
        + "\n",
        encoding="utf-8",
    )

    generator.generate(config_path, target_ids=("contract",))

    assert (tmp_path / "api-blueprint.index.json").is_file()
    assert not (tmp_path / "api-blueprint.contract.json").exists()
    index = json.loads((tmp_path / "api-blueprint.index.json").read_text(encoding="utf-8"))
    assert index["kind"] == "api-blueprint.index"
    assert index["read_order"][0]["path"] == "api-gen inspect"
    assert index["routes"][0] == {
        "id": "api.demo.get.ping",
        "service_id": "api.demo",
        "kind": "rpc",
        "operation": "Ping",
        "methods": ["GET"],
        "url": "/api/demo/ping",
    }
    assert "schemas" not in index
    assert "errors" not in index
    assert "connections" not in index
    assert "schemas" not in index["routes"][0]
    assert "errors" not in index["routes"][0]
    assert "targets" not in index["routes"][0]
    assert "artifacts" not in index["routes"][0]
    assert index["queries"]["route"] == "api-gen inspect route <route-id> [<route-id> ...] -c api-blueprint.toml"


def test_generator_contract_target_can_write_index_full_contract_and_shards(tmp_path: Path) -> None:
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

[[contract]]
id = "contract"
out_dir = "."
formats = ["index", "json", "shards"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    generator.generate(config_path, target_ids=("contract",))

    index = json.loads((tmp_path / "api-blueprint.index.json").read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "api-blueprint.contract.json").read_text(encoding="utf-8"))
    assert index["kind"] == "api-blueprint.index"
    assert contract["routes"][0]["id"] == "api.demo.get.ping"
    assert (tmp_path / "api-blueprint.contract.d" / "index.json").is_file()


def test_generator_contract_target_writes_agent_outputs_and_shards(tmp_path: Path) -> None:
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
formats = ["json", "markdown", "agent-json", "agent-markdown", "shards"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    generator.generate(config_path, target_ids=("contract",))

    assert (tmp_path / "api-blueprint.contract.json").is_file()
    assert (tmp_path / "api-blueprint.contract.md").is_file()
    agent = json.loads((tmp_path / "api-blueprint.agent.json").read_text(encoding="utf-8"))
    assert agent["kind"] == "api-blueprint.agent"
    assert agent["read_order"][0]["path"] == "api-gen inspect"
    assert "优先使用 `api-gen inspect` 按需查询 route/schema/files/errors" in (
        tmp_path / "api-blueprint.agent.md"
    ).read_text(encoding="utf-8")
    assert (tmp_path / "api-blueprint.contract.d" / "index.json").is_file()
    assert (tmp_path / "api-blueprint.contract.d" / "routes" / "api.demo.get.ping.json").is_file()


def test_generator_contract_target_removes_stale_shards(tmp_path: Path) -> None:
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
formats = ["shards"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    stale_shard = tmp_path / "api-blueprint.contract.d" / "routes" / "stale.json"
    stale_shard.parent.mkdir(parents=True)
    stale_shard.write_text("{}", encoding="utf-8")

    generator.generate(config_path, target_ids=("contract",))

    assert not stale_shard.exists()
    assert (tmp_path / "api-blueprint.contract.d" / "routes" / "api.demo.get.ping.json").is_file()


def test_generator_raw_grpc_stub_target_does_not_require_blueprint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "protocols" / "grpc"
    source_root.mkdir(parents=True)
    (source_root / "demo.proto").write_text(
        'syntax = "proto3";\npackage demo;\nservice Demo { rpc Ping (PingRequest) returns (PingResponse); }\nmessage PingRequest {}\nmessage PingResponse {}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.go"
kind = "grpc-go"
source_root = "protocols/grpc"
out_dir = "grpc/go"
files = ["*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_generate_go_stubs(proto_root: Path, target: object) -> None:
        captured["proto_root"] = proto_root
        captured["target"] = target

    monkeypatch.setattr("api_blueprint.writer.grpc.toolchain.generate_go_stubs", fake_generate_go_stubs)

    generator.generate(config_path, target_ids=("grpc.go",))

    assert captured["proto_root"] == source_root.resolve()
