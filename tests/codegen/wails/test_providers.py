from __future__ import annotations

from .helpers import *


def test_wails_codegen_uses_fixed_providers_package_and_binding_hook(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()

    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    provider_file = shared_go / "providers" / "gen_provider.go"
    route_file = shared_go / "routes" / "api" / "demo" / "gen_types.go"
    overlay_service = shared_go / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go"
    runtime_file = shared_go / "transports" / "wailsv3" / "gen_runtime.go"
    binding_impl = shared_go / "transports" / "wailsv3" / "api" / "demo" / "impl_service.go"
    expected_provider_import = f'providers "example.com/generated/{shared_go.name}/providers"'
    expected_shared_provider_import = f'sharedprovider "example.com/generated/{shared_go.name}/providers"'

    assert provider_file.is_file()
    assert binding_impl.is_file()
    assert 'package providers' in provider_file.read_text(encoding="utf-8")
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert expected_shared_provider_import in overlay_service.read_text(encoding="utf-8")
    assert expected_shared_provider_import in runtime_file.read_text(encoding="utf-8")
    assert "func newGeneratedDemoService" in overlay_service.read_text(encoding="utf-8")
    assert "func NewService(" not in overlay_service.read_text(encoding="utf-8")
    assert "func NewService(dispatcher wailstransport.EventDispatcher)" in binding_impl.read_text(encoding="utf-8")
    assert "return newGeneratedDemoService(shared.NewRouter(), dispatcher)" in binding_impl.read_text(encoding="utf-8")

def test_wails_binding_impl_service_is_preserved_on_regeneration(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()

    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    impl_service = shared_go / "transports" / "wailsv3" / "api" / "demo" / "impl_service.go"
    custom_impl = """
package demo

import wailstransport "example.com/generated/golang/transports/wailsv3"

func NewService(dispatcher wailstransport.EventDispatcher) *DemoService {
	return newGeneratedDemoService(nil, dispatcher)
}

// custom binding hook
    """.strip() + "\n"
    impl_service.write_text(custom_impl, encoding="utf-8")

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    assert "custom binding hook" in impl_service.read_text(encoding="utf-8")

def test_golang_provider_impl_files_are_preserved_on_regeneration(tmp_path: Path):
    from api_blueprint.writer.golang import GolangWriter
    from api_blueprint.engine import Blueprint

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

    impl_auth = output_dir / "providers" / "impl_auth.go"
    impl_auth.write_text("package providers\n\n// custom auth hook\n", encoding="utf-8")

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert impl_auth.read_text(encoding="utf-8") == "package providers\n\n// custom auth hook\n"

def test_wails_codegen_allows_business_root_named_providers(tmp_path: Path):
    config = tmp_path / "api-blueprint.toml"
    shared_go = tmp_path / "golang"
    shared_ts = tmp_path / "typescript"
    for path in (shared_go, shared_ts):
        path.mkdir()

    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/providers")
with bp.group("/demo") as views:
    views.GET("/ping").RSP()
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output
    assert (shared_go / "providers" / "gen_provider.go").is_file()
    assert (shared_go / "routes" / "providers" / "demo" / "gen_interface.go").is_file()
