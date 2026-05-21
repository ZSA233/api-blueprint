from __future__ import annotations

import json

from pathlib import Path

from api_blueprint import __version__

from click.testing import CliRunner

import api_blueprint.cli.apigen as apigen_module

from api_blueprint.cli.apigen import api_gen

def _write_blueprint(tmp_path):
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
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _write_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, Error, Model, Toast
from api_blueprint.engine.model import String

class CommonErr(Model):
    UNKNOWN = Error(
        -1,
        "未知错误",
        toast=Toast(
            key="common.unknown",
            default="未知错误",
            level="error",
        ),
    )

class SubmitBody(Model):
    name = String(description="name")

class SubmitResult(Model):
    message = String(description="message")

bp = Blueprint(root="/api", errors=[CommonErr])
with bp.group("/demo") as views:
    views.POST("/submit").REQ(SubmitBody).RSP(SubmitResult)
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _write_inspect_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang/server"
module = "example.com/generated"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path

def _write_go_safe_inspect_blueprint(tmp_path: Path) -> None:
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

def _write_go_safe_inspect_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang/server"
module = "example.com/generated/server"

[[targets]]
id = "go.client"
kind = "go-client"
out_dir = "golang/client"
module = "example.com/generated/client"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"

[[targets]]
id = "desktop.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
overlay_name = "wailsv3"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path

def _write_binary_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    binary_dir = pkg / "binary"
    binary_dir.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (binary_dir / "demo_packet.md").write_text(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="DEMO" | magic |
| item_num | u32 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | DemoItem | item_num | | items |

## struct DemoItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| value | u32 | 1 | max=100 | value |
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, provider
from api_blueprint.engine.model import String

bp = Blueprint(root="/api", providers=[provider.Req(), provider.Handle(), provider.Rsp()])
with bp.group("/demo") as views:
    views.POST("/binary").ARGS(token=String(description="token")).REQ_BINARY("./binary/demo_packet.md").RSP(ok=String(description="ok"))
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _write_bulk_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, Error, Model, Toast
from api_blueprint.engine.model import String

class CommonErr(Model):
    UNKNOWN = Error(
        -1,
        "未知错误",
        toast=Toast(
            key="common.unknown",
            default="未知错误",
            level="error",
        ),
    )

class SubmitBody(Model):
    name = String(description="name")

class SubmitResult(Model):
    message = String(description="message")

class PingResult(Model):
    message = String(description="message")

bp = Blueprint(root="/api", errors=[CommonErr])
with bp.group("/demo") as views:
    views.POST("/submit").REQ(SubmitBody).RSP(SubmitResult)
    views.GET("/ping").RSP(PingResult)
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _write_connection_inspect_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint, ConnectionDelivery, ConnectionScope, Model
from api_blueprint.engine.model import String

class Open(Model):
    device_id = String(description="device id")

class ClientMessage(Model):
    text = String(description="text")

class ServerMessage(Model):
    text = String(description="text")

class Close(Model):
    reason = String(description="reason")

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.CHANNEL("/ws", scope=ConnectionScope.SESSION, delivery=ConnectionDelivery.UNORDERED, operation_id="Realtime").OPEN(Open).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(ServerMessage).CLOSE(Close)
""".strip()
        + "\n",
        encoding="utf-8",
    )

def _write_duplicate_operation_blueprint(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
    views.PUT("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
""".strip()
        + "\n",
        encoding="utf-8",
    )

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
