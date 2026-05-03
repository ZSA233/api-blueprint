from __future__ import annotations

import pytest

from api_blueprint.engine import Blueprint, Error, Model
from api_blueprint.engine.wrapper import GeneralWrapper
from api_blueprint.writer.golang import GolangResponseWrapper
from api_blueprint.writer.golang.writer import GolangWriter


def test_golang_response_wrapper_preserves_generic_type_parameters():
    wrapper = GolangResponseWrapper("RSP_JSON", GeneralWrapper)
    assert wrapper.proto_def_name == "RSP_JSON_GeneralWrapper[T any]"
    assert wrapper.generic_types(True) == "[T any]"


def test_golang_writer_uses_custom_provider_package(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir, provider_package="providers")
    writer.register(bp)
    writer.gen()

    provider_file = output_dir / "views" / "providers" / "gen_provider.go"
    provider_context = output_dir / "views" / "providers" / "gen_context.go"
    provider_executor = output_dir / "views" / "providers" / "gen_executor.go"
    route_file = output_dir / "views" / "api" / "demo" / "gen_protos.go"
    expected_provider_import = f'providers "example.com/generated/{output_dir.name}/views/providers"'

    assert provider_file.is_file()
    assert provider_context.is_file()
    assert provider_executor.is_file()
    assert 'package providers' in provider_file.read_text(encoding="utf-8")
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert "func (ctx *Context[Q, B, P]) Next()" in provider_context.read_text(encoding="utf-8")
    assert "ctx.Gin.Next()" not in provider_context.read_text(encoding="utf-8")
    assert "NewRouteExecutor" in provider_executor.read_text(encoding="utf-8")


def test_golang_writer_rejects_provider_package_conflicting_with_blueprint_root(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/provider")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir, provider_package="provider")
    writer.register(bp)

    with pytest.raises(ValueError, match="provider_package\\[provider\\].*blueprint root\\[provider\\]"):
        writer.gen()


def test_golang_writer_generates_only_declared_error_models(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class UsedErr(Model):
        BOOM = Error(1001, "boom")

    class UnusedErr(Model):
        NOISE = Error(1002, "noise")

    bp = Blueprint(root="/api", errors=[UsedErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "errors" / "used_err" / "gen_errors.go").is_file()
    assert not (output_dir / "errors" / "unused_err").exists()
