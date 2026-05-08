from __future__ import annotations

import pytest

from api_blueprint.config import Config, resolve_config
from api_blueprint.application.generator import target_manifest
from tests.support import EXAMPLE_CONFIG


@pytest.mark.parametrize(
    "legacy_config",
    [
        "[golang]\ncodegen_output = 'golang'\n",
        "[typescript]\ncodegen_output = 'typescript'\n",
        "[kotlin]\ncodegen_output = 'kotlin'\npackage = 'com.example.generated'\n",
        "[grpc]\nsource_root = 'grpc/protos'\n",
        "[[transport.targets]]\nid = 'http'\nkind = 'http'\n",
        "[[wails.targets]]\nid = 'desktop.v3'\nversion = 'v3'\n",
    ],
)
def test_legacy_config_sections_are_rejected(tmp_path, legacy_config: str) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(legacy_config, encoding="utf-8")

    with pytest.raises(ValueError, match="Extra inputs are not permitted|unsupported config alias table"):
        Config.load(config_path)


def test_example_config_loads_vnext_targets() -> None:
    config = Config.load(EXAMPLE_CONFIG)

    assert config.blueprint is not None
    assert config.blueprint.entrypoints == ["blueprints.app:*"]
    assert config.blueprint.docs_server == "0.0.0.0:2332"
    assert [target.id for target in config.targets] == [
        "contract",
        "grpc.proto",
        "grpc.go",
        "grpc.python",
        "go.server",
        "go.client",
        "typescript.client",
        "kotlin.client",
        "python.server",
        "python.client",
        "http",
        "http.python",
        "wails.v3",
        "wails.v2",
    ]
    assert [target.kind for target in config.targets] == [
        "contract",
        "grpc-proto",
        "grpc-go",
        "grpc-python",
        "go-server",
        "go-client",
        "typescript-client",
        "kotlin-client",
        "python-server",
        "python-client",
        "http-transport",
        "http-transport",
        "wails-transport",
        "wails-transport",
    ]


def test_alias_target_tables_normalize_to_vnext_targets(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "contract"
kind = "contract"
out_dir = "."

[[go.server]]
id = "go.server"
out_dir = "golang"
module = "example.com/project/golang"

[[go.client]]
id = "go.client"
out_dir = "go-client"
module = "example.com/project/go-client"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[kotlin.client]]
id = "kotlin.client"
out_dir = "kotlin"
module = "com.example.generated"

[[python.server]]
id = "python.server"
out_dir = "python/server"
module = "server_app"

[[python.client]]
id = "python.client"
out_dir = "python/client"
python_package_root = "client_app"

[[transport.http]]
id = "http"
server = "python.server"
clients = ["python.client"]

[[transport.wails]]
id = "wails.v3"
version = "v3"
server = "go.server"
clients = ["typescript.client"]

[[grpc.proto]]
id = "grpc.proto"
out_dir = "grpc/protos"
package = "example.api"

[[grpc.go]]
id = "grpc.go"
proto = "grpc.proto"
out_dir = "grpc/go"
files = ["api/*.proto"]

[[grpc.python]]
id = "grpc.python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/*.proto"]
module = "pb"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)

    assert [target.id for target in config.targets] == [
        "contract",
        "go.server",
        "go.client",
        "typescript.client",
        "kotlin.client",
        "python.server",
        "python.client",
        "http",
        "wails.v3",
        "grpc.proto",
        "grpc.go",
        "grpc.python",
    ]
    assert [target.kind for target in config.targets] == [
        "contract",
        "go-server",
        "go-client",
        "typescript-client",
        "kotlin-client",
        "python-server",
        "python-client",
        "http-transport",
        "wails-transport",
        "grpc-proto",
        "grpc-go",
        "grpc-python",
    ]
    assert config.targets[1].module == "example.com/project/golang"
    assert config.targets[4].module is None
    assert config.targets[4].package == "com.example.generated"
    assert config.targets[5].module is None
    assert config.targets[5].python_package_root == "server_app"
    assert config.targets[6].python_package_root == "client_app"
    assert config.targets[11].python_package_root == "pb"


def test_alias_target_tables_reject_explicit_kind(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[go.server]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\[\[go.server\]\].*must not include kind"):
        Config.load(config_path)


def test_python_alias_rejects_conflicting_module_and_package_root(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[python.client]]
id = "python.client"
out_dir = "python/client"
module = "client_app"
python_package_root = "generated_client"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\[\[python.client\]\].*module and python_package_root must match"):
        Config.load(config_path)


def test_kotlin_alias_rejects_conflicting_module_and_package(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[kotlin.client]]
id = "kotlin.client"
out_dir = "kotlin"
module = "com.example.generated"
package = "com.example.other"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\[\[kotlin.client\]\].*module and package must match"):
        Config.load(config_path)


def test_alias_target_tables_reject_unknown_alias_table(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[go.mobile]]
id = "go.mobile"
out_dir = "mobile"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"unsupported config alias table \[\[go.mobile\]\]"):
        Config.load(config_path)


def test_alias_target_tables_preserve_duplicate_id_validation(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "client"
kind = "typescript-client"
out_dir = "typescript"

[[python.client]]
id = "client"
out_dir = "python/client"
module = "client_app"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate ids"):
        Config.load(config_path)


def test_resolve_config_converts_vnext_target_outputs_to_absolute_paths() -> None:
    resolved = resolve_config(EXAMPLE_CONFIG)
    targets = {target.id: target for target in resolved.targets}

    assert targets["contract"].out_dir == EXAMPLE_CONFIG.parent.resolve()
    assert targets["go.server"].out_dir == (EXAMPLE_CONFIG.parent / "golang" / "server").resolve()
    assert targets["typescript.client"].out_dir == (EXAMPLE_CONFIG.parent / "typescript").resolve()
    assert targets["kotlin.client"].out_dir == (EXAMPLE_CONFIG.parent / "kotlin").resolve()
    assert targets["kotlin.client"].package == "com.example.apiblueprint"
    assert targets["kotlin.client"].base_url == "http://localhost:2333"
    assert targets["kotlin.client"].include == ("tag:api",)
    assert "path:/api/demo/ws" in targets["kotlin.client"].exclude
    assert targets["wails.v3"].overlay_name == "wailsv3"
    assert targets["wails.v2"].overlay_name == "wailsv2"
    assert targets["grpc.proto"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert targets["grpc.proto"].package == "example.api"
    assert targets["grpc.proto"].go_package_prefix == "example.com/project/grpc/go"
    assert targets["grpc.go"].proto == "grpc.proto"
    assert targets["grpc.go"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "go").resolve()
    assert targets["grpc.go"].module == "example.com/project/grpc/go"
    assert targets["grpc.go"].files == ("api/*.proto", "static/*.proto")
    assert targets["grpc.python"].proto == "grpc.proto"
    assert targets["grpc.python"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "python").resolve()
    assert targets["grpc.python"].files == ("api/*.proto", "static/*.proto")
    assert targets["grpc.python"].python_package_root == "pb"


def test_grpc_stub_targets_load_and_resolve_proto_dependency(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[targets]]
id = "grpc.go"
kind = "grpc-go"
proto = "grpc.proto"
out_dir = "grpc/go"
source_root = "."
files = ["api/**/*.proto"]
import_roots = ["grpc/protos"]

[[targets]]
id = "grpc.python"
kind = "grpc-python"
proto = "grpc.proto"
out_dir = "grpc/python"
source_root = "."
files = ["api/**/*.proto"]
import_roots = ["grpc/protos"]
python_package_root = "pb"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert [target.kind for target in config.targets] == ["grpc-proto", "grpc-go", "grpc-python"]
    assert config.targets[1].proto == "grpc.proto"
    assert config.targets[1].files == ["api/**/*.proto"]
    assert config.targets[2].python_package_root == "pb"

    resolved = resolve_config(config_path)
    targets = {target.id: target for target in resolved.targets}
    assert targets["grpc.go"].proto == "grpc.proto"
    assert targets["grpc.go"].out_dir == (tmp_path / "grpc" / "go").resolve()
    assert targets["grpc.go"].source_root == tmp_path.resolve()
    assert targets["grpc.go"].files == ("api/**/*.proto",)
    assert targets["grpc.go"].import_roots == ((tmp_path / "grpc" / "protos").resolve(),)
    assert targets["grpc.python"].python_package_root == "pb"


def test_grpc_proto_target_loads_and_resolves_proto_file_layout(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[targets.proto_files]]
file = "shared/browseragent/browser/v1/browser.proto"
package = "browseragent.browser.v1"
go_package = "appkit/browseragent/pb/browser/v1;browserpb"
schema_modules = ["blueprints.shared.browseragent.browser"]
schema_names = ["Browser*"]
route_paths = ["/shared/browseragent/browser/v1/**"]
route_ids = ["shared.browseragent_browser.*"]
service_ids = ["shared.browseragent_browser"]
service = "BrowserService"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.targets[0].proto_files[0].file == "shared/browseragent/browser/v1/browser.proto"
    assert config.targets[0].proto_files[0].schema_modules == ["blueprints.shared.browseragent.browser"]

    resolved = resolve_config(config_path)
    target = resolved.targets[0]
    assert target.proto_files[0].file == "shared/browseragent/browser/v1/browser.proto"
    assert target.proto_files[0].package == "browseragent.browser.v1"
    assert target.proto_files[0].go_package == "appkit/browseragent/pb/browser/v1;browserpb"
    assert target.proto_files[0].service == "BrowserService"
    assert target_manifest(target, tmp_path)["proto_files"][0]["file"] == "shared/browseragent/browser/v1/browser.proto"


def test_grpc_proto_file_layout_is_only_allowed_on_grpc_proto_targets(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"

[[targets.proto_files]]
file = "api/demo.proto"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="proto_files"):
        Config.load(config_path)


def test_grpc_stub_target_requires_grpc_proto_dependency(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "contract"
kind = "contract"
out_dir = "."

[[targets]]
id = "grpc.go"
kind = "grpc-go"
proto = "contract"
out_dir = "grpc/go"
files = ["api/**/*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must reference a grpc-proto target"):
        resolve_config(config_path)


def test_grpc_stub_target_can_compile_raw_proto_without_proto_dependency(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.go"
kind = "grpc-go"
source_root = "protocols/grpc"
out_dir = "grpc/go"
files = ["**/*.proto"]
import_roots = ["third_party/protos"]

[[targets]]
id = "grpc.python"
kind = "grpc-python"
source_root = "protocols/grpc"
out_dir = "grpc/python"
files = ["**/*.proto"]
python_package_root = "pb"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.targets[0].proto is None
    assert config.targets[0].source_root == "protocols/grpc"

    resolved = resolve_config(config_path)
    targets = {target.id: target for target in resolved.targets}
    assert targets["grpc.go"].proto is None
    assert targets["grpc.go"].source_root == (tmp_path / "protocols" / "grpc").resolve()
    assert targets["grpc.go"].import_roots == ((tmp_path / "third_party" / "protos").resolve(),)
    assert targets["grpc.python"].python_package_root == "pb"


def test_grpc_stub_target_without_proto_requires_source_root(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "grpc.go"
kind = "grpc-go"
out_dir = "grpc/go"
files = ["**/*.proto"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires proto or source_root"):
        Config.load(config_path)


def test_target_base_url_expr_loads_and_resolves(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url_expr = "import.meta.env.VITE_API_BASE_URL"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert config.targets[0].base_url is None
    assert config.targets[0].base_url_expr == "import.meta.env.VITE_API_BASE_URL"

    resolved = resolve_config(config_path)
    assert resolved.targets[0].base_url is None
    assert resolved.targets[0].base_url_expr == "import.meta.env.VITE_API_BASE_URL"


def test_target_base_url_and_expr_are_mutually_exclusive(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"
base_url_expr = "import.meta.env.VITE_API_BASE_URL"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="mutually exclusive"):
        Config.load(config_path)


def test_targets_require_unique_ids(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "client"
kind = "typescript-client"
out_dir = "typescript"

[[targets]]
id = "client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate ids"):
        Config.load(config_path)


def test_transport_targets_validate_dependency_kind(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"

[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "typescript.client"
clients = ["typescript.client"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="server must reference a go-server target"):
        resolve_config(config_path)


def test_wails_target_validates_overlay_name_and_filter_rules(tmp_path) -> None:
    bad_overlay = tmp_path / "bad-overlay.toml"
    bad_overlay.write_text(
        """
[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"

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
overlay_name = "DesktopOverlay"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="overlay_name must be Go package-safe"):
        Config.load(bad_overlay)

    bad_rule = tmp_path / "bad-rule.toml"
    bad_rule.write_text(
        """
[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"

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
include = ["invalid:desktop"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="不支持的 include/exclude 规则"):
        Config.load(bad_rule)
