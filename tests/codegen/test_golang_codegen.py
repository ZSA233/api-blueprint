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
    assert "ctx.Abort(ctx.Req.Error)" in (output_dir / "views" / "providers" / "gen_req.go").read_text(
        encoding="utf-8"
    )


def test_golang_writer_can_generate_core_without_http_adapter(tmp_path):
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

    stale_engine = output_dir / "views" / "engine.go"
    stale_http = output_dir / "views" / "api" / "demo" / "_http"
    stale_http.mkdir(parents=True)
    stale_engine.parent.mkdir(parents=True, exist_ok=True)
    stale_engine.write_text("package views\n", encoding="utf-8")
    (stale_http / "gen_interface.go").write_text("package httptransport\n", encoding="utf-8")

    writer = GolangWriter(output_dir, transport_adapters=())
    writer.register(bp)
    writer.gen()

    assert not (output_dir / "views" / "_http").exists()
    assert not (output_dir / "views" / "api" / "_http").exists()
    assert not (output_dir / "views" / "api" / "demo" / "_http").exists()
    assert not (output_dir / "views" / "engine.go").exists()

    generated_core = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            output_dir / "views" / "api" / "gen_blueprint.go",
            output_dir / "views" / "api" / "demo" / "gen_interface.go",
            output_dir / "views" / "provider" / "gen_context.go",
            output_dir / "views" / "provider" / "gen_req.go",
            output_dir / "views" / "provider" / "gen_rsp.go",
        )
    )
    assert "github.com/gin-gonic/gin" not in generated_core
    assert "RequireHTTP" not in generated_core


def test_golang_writer_treats_wails_adapter_marker_as_core_only(tmp_path):
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

    writer = GolangWriter(output_dir, transport_adapters=("wails",))
    writer.register(bp)
    writer.gen()

    assert (output_dir / "views" / "api" / "demo" / "gen_interface.go").is_file()
    assert not (output_dir / "views" / "_http").exists()
    assert not (output_dir / "views" / "api" / "demo" / "_http").exists()


def test_golang_writer_generates_http_adapter_separately_from_core(tmp_path):
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

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    root_adapter = output_dir / "views" / "api" / "_http" / "gen_blueprint.go"
    route_adapter = output_dir / "views" / "api" / "demo" / "_http" / "gen_interface.go"
    core_route = output_dir / "views" / "api" / "demo" / "gen_interface.go"

    assert root_adapter.is_file()
    assert route_adapter.is_file()
    root_adapter_text = root_adapter.read_text(encoding="utf-8")
    route_adapter_text = route_adapter.read_text(encoding="utf-8")
    assert "package apihttp" in root_adapter_text
    assert "sharedroot" not in root_adapter_text
    assert "Router *sharedroot.Router" not in root_adapter_text
    assert "package demohttp" in route_adapter_text
    assert 'github.com/gin-gonic/gin' in route_adapter_text
    assert "func Mount(eng *gin.Engine, impl *shared.Router) *shared.Router" in route_adapter_text
    assert "func NewRouter(eng *gin.Engine) *shared.Router" in route_adapter_text
    assert "func NewImpl(eng *gin.Engine) *shared.Router" in route_adapter_text
    assert "return NewRouter(eng)" in route_adapter_text
    assert 'httpcore.GET[any, any, shared.RSP_Ping]' in route_adapter_text
    assert 'github.com/gin-gonic/gin' not in core_route.read_text(encoding="utf-8")
    assert "func NewImpl(eng *gin.Engine)" not in core_route.read_text(encoding="utf-8")


def test_golang_http_adapter_respects_already_written_gin_response(tmp_path):
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
        views.POST("/callback")

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    http_runtime = (output_dir / "views" / "_http" / "gen_engine.go").read_text(encoding="utf-8")
    assert "if ginCtx.Writer.Written() {" in http_runtime
    assert "ginCtx.JSON(http.StatusOK, response)" in http_runtime


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
