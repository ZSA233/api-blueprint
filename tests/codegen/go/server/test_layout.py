from __future__ import annotations

from .helpers import *


def test_golang_writer_uses_go_safe_route_package_segments(tmp_path):
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

    bp = Blueprint(root="/api-v1")
    with bp.group("/admin/v1") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    root_blueprint = (output_dir / "routes" / "api_v1" / "gen_blueprint.go").read_text(encoding="utf-8")
    group_interface = (output_dir / "routes" / "api_v1" / "admin_v1" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    http_blueprint = (output_dir / "transports" / "http" / "api_v1" / "gen_blueprint.go").read_text(
        encoding="utf-8"
    )

    assert "package api_v1" in root_blueprint
    assert '"example.com/generated/golang/routes/api_v1/admin_v1"' in root_blueprint
    assert "AdminV1Router *admin_v1.Router" in root_blueprint
    assert "package admin_v1" in group_interface
    assert 'sharedAdminV1 "example.com/generated/golang/routes/api_v1/admin_v1"' in http_blueprint

def test_golang_writer_cleans_legacy_views_and_sibling_errors_when_out_dir_is_package_root(tmp_path):
    package_root = tmp_path / "golang" / "server" / "views"
    package_root.mkdir(parents=True)
    (package_root.parent / "go.mod").write_text(
        """
module example.com/generated/golang/server

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    legacy_double_views = package_root / "views" / "routes"
    legacy_double_views.mkdir(parents=True)
    (legacy_double_views / "gen_interface.go").write_text("package stale\n", encoding="utf-8")
    legacy_errors = package_root.parent / "errors" / "common_err"
    legacy_errors.mkdir(parents=True)
    (legacy_errors / "gen_errors.go").write_text("package common_err\n", encoding="utf-8")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(package_root, module="example.com/generated/golang/server")
    writer.register(bp)
    writer.gen()

    assert not (package_root / "views").exists()
    assert not (package_root.parent / "errors").exists()
    assert (package_root / "routes" / "api" / "demo" / "gen_interface.go").is_file()

def test_golang_writer_blocks_legacy_cleanup_when_user_impl_exists(tmp_path):
    package_root = (tmp_path / "golang" / "server" / "views").resolve()
    package_root.mkdir(parents=True)
    (package_root.parent / "go.mod").write_text(
        """
module example.com/generated/golang/server

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    legacy_providers = package_root / "views" / "providers"
    legacy_providers.mkdir(parents=True)
    user_impl = legacy_providers / "impl_provider.go"
    user_impl.write_text("// user-owned implementation\n", encoding="utf-8")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(package_root, module="example.com/generated/golang/server")
    writer.register(bp)

    with pytest.raises(ValueError, match="legacy generated layout contains user-owned or unknown files"):
        writer.gen()

    assert user_impl.exists()
    assert not (package_root / "routes").exists()
