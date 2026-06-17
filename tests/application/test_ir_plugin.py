from __future__ import annotations

import json
from pathlib import Path

from api_blueprint.application import generator
from api_blueprint.config import Config, resolve_config


def _write_ir_plugin_fixture(tmp_path: Path) -> Path:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, Model, message_variant
from api_blueprint.engine.model import String

class ServerMessage(Model):
    value = String(description="value")

class ClientMessage(Model):
    value = String(description="value")

class ExportedPayload(Model):
    value = String(description="value")

bp = Blueprint(root="/api")
bp.EXPORT_MODELS(ExportedPayload, domain="support")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))
    views.CHANNEL("/chat").SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(
        "ClientUnion",
        input=message_variant(ClientMessage, op=3001, domain="message"),
    )
""".strip()
        + "\n",
        encoding="utf-8",
    )
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "__init__.py").write_text("", encoding="utf-8")
    (plugins / "summary.py").write_text(
        """
def generate(context):
    context.write_json(
        "summary.json",
        {
            "target": context.target.id,
            "options": dict(context.options),
            "routes": [
                {
                    "id": route["id"],
                    "kind": route["kind"],
                    "client_metadata": [
                        variant.get("metadata", {})
                        for variant in ((route.get("connection") or {}).get("client_message") or {}).get("variants", [])
                    ],
                }
                for route in context.selected_routes
            ],
            "exported_models": context.contract_graph.to_manifest().get("exported_models", []),
            "has_exported_schema": "ExportedPayload" in context.contract_graph.to_manifest().get("schemas", {}),
        },
    )
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "demo.plugin"
kind = "ir-plugin"
plugin = "plugins.summary"
out_dir = "generated/plugin"
include = ["kind:channel"]

[targets.options]
package = "demo"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def test_ir_plugin_target_loads_resolves_and_generates(tmp_path: Path) -> None:
    config_path = _write_ir_plugin_fixture(tmp_path)

    config = Config.load(config_path)
    assert config.targets[0].kind == "ir-plugin"
    assert config.targets[0].plugin == "plugins.summary"
    assert config.targets[0].options == {"package": "demo"}

    resolved = resolve_config(config_path).targets[0]
    assert resolved.out_dir == (tmp_path / "generated" / "plugin").resolve()
    assert resolved.plugin == "plugins.summary"
    assert resolved.options == {"package": "demo"}

    generator.check(config_path)
    generator.generate(config_path, target_ids=("demo.plugin",))

    summary = json.loads((tmp_path / "generated" / "plugin" / "summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "options": {"package": "demo"},
        "exported_models": [{"metadata": {"domain": "support"}, "model": "ExportedPayload"}],
        "has_exported_schema": True,
        "routes": [
            {
                "client_metadata": [{"domain": "message", "op": 3001}],
                "id": "api.demo.channel.chat",
                "kind": "channel",
            }
        ],
        "target": "demo.plugin",
    }
