from __future__ import annotations

from click.testing import CliRunner

from api_blueprint import __version__
from api_blueprint.application.entrypoints import load_entrypoints
from api_blueprint.application.project import build_entrypoints
from api_blueprint.cli.apidoc import apidoc_server
from api_blueprint.cli.apigen import api_gen


def test_cli_help_smoke():
    runner = CliRunner()
    for cli in (apidoc_server, api_gen):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0


def test_cli_commands_report_version() -> None:
    runner = CliRunner()

    api_gen_result = runner.invoke(api_gen, ["--version"])
    api_doc_result = runner.invoke(apidoc_server, ["--version"])

    assert api_gen_result.exit_code == 0
    assert api_gen_result.output.strip() == f"api-gen, api-blueprint {__version__}"
    assert api_doc_result.exit_code == 0
    assert api_doc_result.output.strip() == f"api-doc-server, api-blueprint {__version__}"


def test_cli_help_displays_current_version() -> None:
    runner = CliRunner()

    for cli in (apidoc_server, api_gen):
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert f"api-blueprint {__version__}" in result.output


def test_load_entrypoints_uses_temporary_import_path_scope(tmp_path):
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        "from api_blueprint.engine import Blueprint\nbp = Blueprint(root='/tmp')\n",
        encoding="utf-8",
    )

    before = list(__import__("sys").path)
    entrypoints = load_entrypoints(["blueprints.app:bp"], tmp_path)
    after = list(__import__("sys").path)

    assert len(entrypoints) == 1
    assert before == after


def test_load_entrypoints_resets_runtime_state_between_reloads(tmp_path):
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.includes import Array, Float64, KV, Uint

bp = Blueprint(root="/api")

with bp.group("/demo") as views:
    views.PUT("/1put").RSP(
        anon_kv=KV(
            kv1=Uint(description="kv1"),
            kv2=Array[Float64](description="kv2"),
        )
    )
""".strip()
        + "\n",
        encoding="utf-8",
    )

    first = load_entrypoints(["blueprints.app:bp"], tmp_path)
    build_entrypoints(first)

    second = load_entrypoints(["blueprints.app:bp"], tmp_path)
    build_entrypoints(second)

    router = next(router for bp in second for _group, router in bp.iter_router() if router.leaf == "/1put")
    field = router.rsp_model["anon_kv"]

    assert getattr(field.get_obj(), "__name__", None) == "ANON_Func1put_anon_kv"


def test_api_doc_server_accepts_vnext_config_without_legacy_golang_section(tmp_path, monkeypatch):
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/api")

with bp.group("/demo") as views:
    views.GET("/hello").RSP(message="ok")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
    [blueprint]
    docs_server = "0.0.0.0:2332"
    entrypoints = ["blueprints.app:bp"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    calls: list[tuple[str, int, list[object] | None]] = []

    class FakeSocket:
        def __init__(self, host: str, port: int) -> None:
            self._host = host
            self._port = port

        def getsockname(self) -> tuple[str, int]:
            return (self._host, self._port)

    def fake_bind_socket(self) -> FakeSocket:
        return FakeSocket(self.host, self.port)

    def fake_server_run(self, sockets: list[object] | None = None) -> None:
        calls.append((self.config.host, self.config.port, sockets))

    monkeypatch.setattr("api_blueprint.application.docs.uvicorn.Config.bind_socket", fake_bind_socket)
    monkeypatch.setattr("api_blueprint.application.docs.uvicorn.Server.run", fake_server_run)

    runner = CliRunner()
    result = runner.invoke(apidoc_server, ["-c", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "[api-doc-server] Docs: http://localhost:2332/docs" in result.output
    assert len(calls) == 1
    assert calls[0][:2] == ("0.0.0.0", 2332)
    assert len(calls[0][2] or []) == 1


def test_api_doc_server_reports_actual_bound_port_for_zero_port_config(tmp_path, monkeypatch):
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/api")

with bp.group("/demo") as views:
    views.GET("/hello").RSP(message="ok")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
    [blueprint]
    docs_server = "0.0.0.0:0"
    entrypoints = ["blueprints.app:bp"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    class FakeSocket:
        def getsockname(self) -> tuple[str, int]:
            return ("0.0.0.0", 49123)

    def fake_bind_socket(self) -> FakeSocket:
        return FakeSocket()

    def fake_server_run(self, sockets: list[object] | None = None) -> None:
        return None

    monkeypatch.setattr("api_blueprint.application.docs.uvicorn.Config.bind_socket", fake_bind_socket)
    monkeypatch.setattr("api_blueprint.application.docs.uvicorn.Server.run", fake_server_run)

    runner = CliRunner()
    result = runner.invoke(apidoc_server, ["-c", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "[api-doc-server] Docs: http://localhost:49123/docs" in result.output
