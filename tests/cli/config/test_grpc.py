from __future__ import annotations

from .helpers import *


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
