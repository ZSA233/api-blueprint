from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from api_blueprint.application.project import build_entrypoints
from api_blueprint.application.entrypoints import load_entrypoints
from api_blueprint.cli.apidoc import apidoc_server
from api_blueprint.cli.apigen import gen_golang, gen_grpc, gen_typescript


def test_cli_help_smoke():
    runner = CliRunner()
    for cli in (apidoc_server, gen_golang, gen_grpc, gen_typescript):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0


def test_gen_typescript_requires_typescript_config(tmp_path):
    config = tmp_path / "api-blueprint.toml"
    config.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:*"]

[golang]
codegen_output = "golang"
    """.strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "blueprints" / "app.py").write_text(
        "from api_blueprint.engine import Blueprint\napp = Blueprint(root='/x')\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_typescript, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


def test_gen_golang_requires_blueprint_config(tmp_path):
    config = tmp_path / "api-blueprint.toml"
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    config.write_text(
        f"""
[golang]
codegen_output = "{output_dir.name}"
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_golang, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "blueprint" in str(result.exception)


def test_gen_grpc_requires_grpc_config(tmp_path):
    config = tmp_path / "api-blueprint.toml"
    config.write_text(
        """
[blueprint]
entrypoints = ["blueprints.app:*"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_grpc, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "grpc" in str(result.exception)


def test_gen_grpc_list_jobs_outputs_deterministic_listing(tmp_path):
    config = tmp_path / "api-blueprint.toml"
    config.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "python.greeter"
preset = "python"
output = "generated/python"
protos = ["**/*.proto"]

[[grpc.jobs]]
name = "go.greeter"
preset = "go"
output = "generated/go"
protos = ["greeter.proto"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_grpc, ["-c", str(config), "--list-jobs"])

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert lines == [
        f"python.greeter\tpython\t{(tmp_path / 'generated' / 'python').resolve()}",
        f"go.greeter\tgo\t{(tmp_path / 'generated' / 'go').resolve()}",
    ]


def test_gen_grpc_rejects_unknown_job_filter(tmp_path):
    config = tmp_path / "api-blueprint.toml"
    config.write_text(
        """
[grpc]
proto_root = "protos"

[[grpc.jobs]]
name = "python.greeter"
preset = "python"
output = "generated/python"
protos = ["**/*.proto"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_grpc, ["-c", str(config), "--list-jobs", "--job", "missing*"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "未匹配到任何job" in str(result.exception)


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
