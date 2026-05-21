from __future__ import annotations

import re

from pathlib import Path

from click.testing import CliRunner, Result

from api_blueprint.cli.apigen import api_gen

from api_blueprint.contract import build_contract_graph

from api_blueprint.engine import Blueprint

from api_blueprint.engine.model import Model, String

from api_blueprint.writer.wails.golang import WailsGoWriter

def _write_wails_vnext_config(
    config: Path,
    *,
    entrypoints: str = '"blueprints.app:bp"',
    go_out: str = "golang",
    ts_out: str = "typescript",
    target_id: str = "desktop.v3",
    version: str = "v3",
    frontend_mode: str = "external",
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    with_http_transport: bool = False,
) -> None:
    include_line = f"include = {list(include)!r}\n" if include else ""
    exclude_line = f"exclude = {list(exclude)!r}\n" if exclude else ""
    http_transport = (
        """
[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client"]
""".strip()
        + "\n\n"
        if with_http_transport
        else ""
    )
    config.write_text(
        f"""
[blueprint]
entrypoints = [{entrypoints}]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "{go_out}"
module = "example.com/generated"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "{ts_out}"
base_url = "http://localhost:2333"

{http_transport}\
[[targets]]
id = "{target_id}"
kind = "wails-transport"
version = "{version}"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "{frontend_mode}"
{include_line}{exclude_line}
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _invoke_wails_generate(config: Path, target_id: str = "desktop.v3") -> Result:
    return CliRunner().invoke(api_gen, ["generate", "-c", str(config), "--target", target_id])

def _write_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, ConnectionDelivery, provider
from api_blueprint.engine.model import Model, String
from api_blueprint.engine.envelope import CodeMessageDataEnvelope

class OpenInfo(Model):
    token = String(description="token")

class StreamMessage(Model):
    message = String(description="message")

class ClientMessage(Model):
    message = String(description="message")

class CloseInfo(Model):
    reason = String(description="reason")

bp = Blueprint(
    root="/api",
    response_envelope=CodeMessageDataEnvelope,
    providers=[
        provider.Req(),
        provider.Auth(),
        provider.Handle(),
        provider.Rsp(),
    ],
)
with bp.group("/demo") as views:
    views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))
    views.STREAM("/events").OPEN(OpenInfo).SERVER_MESSAGE("DemoStreamMessage", event=StreamMessage).CLOSE(CloseInfo)
    views.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED).OPEN(OpenInfo).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(StreamMessage).CLOSE(CloseInfo)
        """.strip()
        + "\n",
        encoding="utf-8",
    )

def _write_multi_group_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))

with bp.group("/hello") as views:
    views.GET("/pong").RSP(message=String(description="message"))
        """.strip()
        + "\n",
        encoding="utf-8",
    )

def _write_multi_root_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

api_bp = Blueprint(root="/api")
with api_bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))

third_bp = Blueprint(root="/third")
with third_bp.group("/proxy") as views:
    views.GET("/ping").RSP(message=String(description="message"))
        """.strip()
        + "\n",
        encoding="utf-8",
    )

def _write_same_path_method_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/settings") as views:
    views.GET("/current").RSP(message=String(description="message"))
    views.PUT("/current").RSP(message=String(description="message"))
        """.strip()
        + "\n",
        encoding="utf-8",
    )

def _write_go_safe_route_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api-v1")
with bp.group("/admin/v1") as views:
    views.GET("/ping").RSP(message=String(description="message"))
        """.strip()
        + "\n",
        encoding="utf-8",
    )

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
