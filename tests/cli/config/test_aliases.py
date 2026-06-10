from __future__ import annotations

from .helpers import *


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

def test_alias_target_tables_normalize_to_vnext_targets(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[contract]]
id = "contract"
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

[[kotlin.server]]
id = "kotlin.server"
out_dir = "kotlin/server"
module = "com.example.generated"

[[java.server]]
id = "java.server"
out_dir = "java/server"
module = "com.example.generated"
spring_public_paths = ["/api/**"]

[[java.client]]
id = "java.client"
out_dir = "java/client"
module = "com.example.generated"
base_url = "http://localhost:2333"

[[flutter.client]]
id = "flutter.client"
out_dir = "flutter"
package = "api_blueprint_example"
base_url = "http://localhost:2333"

[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
base_url = "http://localhost:2333"
runtime_profile = "ios14-compat"

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

[[grpc.proto.proto_files]]
file = "api/demo.proto"
package = "example.api.demo"
go_package = "example.com/project/grpc/go/api/demo;demo"
route_paths = ["/api/demo/**"]
service = "DemoService"

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
        "kotlin.server",
        "java.server",
        "java.client",
        "flutter.client",
        "swift.client",
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
        "kotlin-server",
        "java-server",
        "java-client",
        "flutter-client",
        "swift-client",
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
    assert config.targets[5].package == "com.example.generated"
    assert config.targets[6].module is None
    assert config.targets[6].package == "com.example.generated"
    assert config.targets[7].module is None
    assert config.targets[7].package == "com.example.generated"
    assert config.targets[8].module is None
    assert config.targets[8].package == "api_blueprint_example"
    assert config.targets[9].module == "ABClient"
    assert config.targets[9].package == "ApiBlueprintExampleClient"
    assert config.targets[9].runtime_profile == "ios14-compat"
    assert config.targets[10].python_package_root == "server_app"
    assert config.targets[11].python_package_root == "client_app"
    assert len(config.targets[14].proto_files) == 1
    assert config.targets[14].proto_files[0].file == "api/demo.proto"
    assert config.targets[14].proto_files[0].service == "DemoService"
    assert config.targets[16].python_package_root == "pb"

def test_contract_alias_table_normalizes_to_contract_target(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[contract]]
id = "contract"
out_dir = "."
formats = ["index"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)

    assert len(config.targets) == 1
    assert config.targets[0].id == "contract"
    assert config.targets[0].kind == "contract"
    assert config.targets[0].formats == ["index"]

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

@pytest.mark.parametrize("alias", ["kotlin.client", "kotlin.server"])
def test_kotlin_alias_rejects_conflicting_module_and_package(tmp_path, alias: str) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        f"""
[[{alias}]]
id = "{alias}"
out_dir = "kotlin"
module = "com.example.generated"
package = "com.example.other"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"\[\[{alias}\]\].*module and package must match"):
        Config.load(config_path)

@pytest.mark.parametrize("alias", ["java.client", "java.server"])
def test_java_alias_rejects_conflicting_module_and_package(tmp_path, alias: str) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        f"""
[[{alias}]]
id = "{alias}"
out_dir = "java"
module = "com.example.generated"
package = "com.example.other"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"\[\[{alias}\]\].*module and package must match"):
        Config.load(config_path)

def test_swift_alias_allows_distinct_module_and_package(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)

    assert config.targets[0].package == "ApiBlueprintExampleClient"
    assert config.targets[0].module == "ABClient"

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
