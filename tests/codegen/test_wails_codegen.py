from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from api_blueprint.cli.apigen import gen_wails


def test_wails_codegen_generates_transport_specific_typescript_and_go(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    output_go = tmp_path / "wails-go"
    output_ts = tmp_path / "wails-ts"
    output_go.mkdir()
    output_ts.mkdir()
    (output_go / "go.mod").write_text(
        """
module example.com/wailsdemo

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[wails.targets]]
id = "desktop.v3"
version = "v3"
go_out_dir = "{output_go.name}"
typescript_out_dir = "{output_ts.name}"
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model, String

class WSRecv(Model):
    message = String(description="message")

class WSSend(Model):
    message = String(description="message")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))
    views.WS("/ws").RECV(WSRecv).SEND(WSSend)
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    go_service = (output_go / "api" / "demo" / "gen_service.go").read_text(encoding="utf-8")
    ts_transport = (output_ts / "api" / "shared" / "gen_transport.ts").read_text(encoding="utf-8")
    ts_client = (output_ts / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")

    assert "func (svc *DemoService) ConnectWs" in go_service
    assert "func (svc *DemoService) SendWs" in go_service
    assert "func (svc *DemoService) CloseWs" in go_service
    assert "window.wails?.Call" in ts_transport
    assert "ApiSocketBridge<Shared.WSSend, Shared.WSRecv>" in ts_client
