from __future__ import annotations

from .helpers import *


def test_example_config_loads_vnext_targets() -> None:
    config = Config.load(EXAMPLE_CONFIG)

    assert config.blueprint is not None
    assert config.blueprint.entrypoints == ["blueprints.app:*"]
    assert config.blueprint.docs_server == "0.0.0.0:2332"
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
        "http.kotlin",
        "http.python",
        "wails.v3",
        "wails.v2",
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
        "http-transport",
        "http-transport",
        "wails-transport",
        "wails-transport",
        "grpc-proto",
        "grpc-go",
        "grpc-python",
    ]

def test_target_manifest_keeps_sibling_go_output_portable(tmp_path) -> None:
    service_root = tmp_path / "services" / "agent"
    scripts_dir = service_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (service_root / "go.mod").write_text("module example.com/agent\n\ngo 1.23\n", encoding="utf-8")
    config_path = scripts_dir / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "../internal/views"
module = "example.com/agent"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    target = resolve_config(config_path).targets[0]
    manifest = target_manifest(target, scripts_dir)

    assert manifest["out_dir"] == "../internal/views"
    assert manifest["go_import_root"] == "example.com/agent/internal/views"

def test_resolve_config_converts_vnext_target_outputs_to_absolute_paths() -> None:
    resolved = resolve_config(EXAMPLE_CONFIG)
    targets = {target.id: target for target in resolved.targets}

    assert targets["contract"].out_dir == EXAMPLE_CONFIG.parent.resolve()
    assert targets["go.server"].out_dir == (EXAMPLE_CONFIG.parent / "golang" / "server" / "views").resolve()
    assert targets["typescript.client"].out_dir == (EXAMPLE_CONFIG.parent / "typescript").resolve()
    assert targets["kotlin.client"].out_dir == (EXAMPLE_CONFIG.parent / "kotlin" / "client").resolve()
    assert targets["kotlin.client"].package == "com.example.apiblueprint"
    assert targets["kotlin.client"].base_url == "http://localhost:2333"
    assert targets["kotlin.client"].include == ("tag:api",)
    assert "path:/api/demo/ws" in targets["kotlin.client"].exclude
    assert targets["kotlin.server"].out_dir == (EXAMPLE_CONFIG.parent / "kotlin" / "server").resolve()
    assert targets["kotlin.server"].package == "com.example.apiblueprint"
    assert targets["java.server"].out_dir == (EXAMPLE_CONFIG.parent / "java" / "server").resolve()
    assert targets["java.server"].package == "com.example.apiblueprint"
    assert targets["java.client"].out_dir == (EXAMPLE_CONFIG.parent / "java" / "client").resolve()
    assert targets["java.client"].package == "com.example.apiblueprint"
    assert targets["java.client"].base_url == "http://localhost:2333"
    assert targets["swift.client"].out_dir == (EXAMPLE_CONFIG.parent / "swift").resolve()
    assert targets["swift.client"].package == "ApiBlueprintExampleClient"
    assert targets["swift.client"].module == "ABClient"
    assert targets["swift.client"].base_url == "http://localhost:2333"
    assert targets["swift.client"].runtime_profile == "modern"
    assert targets["swift.client"].include == ("tag:api",)
    assert targets["swift.client"].exclude == ()
    assert targets["wails.v3"].overlay_name == "wailsv3"
    assert targets["wails.v2"].overlay_name == "wailsv2"
    assert targets["grpc.proto"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "protos").resolve()
    assert targets["grpc.proto"].package == "example.api"
    assert targets["grpc.proto"].go_package_prefix == "example.com/project/grpc/go"
    assert targets["grpc.go"].proto == "grpc.proto"
    assert targets["grpc.go"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "go").resolve()
    assert targets["grpc.go"].module == "example.com/project/grpc/go"
    assert targets["grpc.go"].files == ("api/*.proto", "legacy/*.proto", "static/*.proto")
    assert targets["grpc.python"].proto == "grpc.proto"
    assert targets["grpc.python"].out_dir == (EXAMPLE_CONFIG.parent / "grpc" / "python").resolve()
    assert targets["grpc.python"].files == ("api/*.proto", "legacy/*.proto", "static/*.proto")
    assert targets["grpc.python"].python_package_root == "pb"

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

def test_java_server_spring_contract_config_loads_resolves_and_manifests(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "java.server"
kind = "java-server"
out_dir = "generated/java-server"
package = "com.example.shop.contract"
spring_contract_mode = "strict-boundary"
spring_public_paths = ["/api/**"]
spring_exclude_server_paths = ["/api/internal/**"]
include = ["tag:public"]

[[targets.spring_policies]]
id = "signed"
annotation = "com.example.shop.security.SignatureRequired"

[[targets.spring_policies]]
id = "authenticated-user"
annotation = "com.example.shop.security.AuthenticatedUser"

[[targets.spring_route_bindings]]
operation_id = "api.account.post.login"
annotation = "GenAccountLogin"
policies = ["signed", "authenticated-user"]
request_binding = "generated"
response_binding = "generated"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    target = config.targets[0]
    assert target.spring_contract_mode == "strict-boundary"
    assert [policy.id for policy in target.spring_policies] == ["signed", "authenticated-user"]
    assert target.spring_route_bindings[0].annotation == "GenAccountLogin"

    resolved = resolve_config(config_path).targets[0]
    manifest = target_manifest(resolved, tmp_path)

    assert resolved.spring_public_paths == ("/api/**",)
    assert resolved.spring_exclude_server_paths == ("/api/internal/**",)
    assert resolved.spring_policies[0].annotation == "com.example.shop.security.SignatureRequired"
    assert resolved.spring_route_bindings[0].policies == ("signed", "authenticated-user")
    assert manifest["spring_contract_mode"] == "strict-boundary"
    assert manifest["spring_policies"][0]["id"] == "signed"
    assert manifest["spring_route_bindings"][0]["annotation"] == "GenAccountLogin"

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

def test_swift_client_requires_package(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "swift.client"
kind = "swift-client"
out_dir = "swift"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="swift-client requires package"):
        Config.load(config_path)

    module_only_config_path = tmp_path / "module-only-api-blueprint.toml"
    module_only_config_path.write_text(
        """
[[swift.client]]
id = "swift.client"
out_dir = "swift"
module = "ABClient"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="swift-client requires package"):
        Config.load(module_only_config_path)

def test_swift_client_runtime_profile_defaults_and_rejects_invalid_values(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "swift.client"
kind = "swift-client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    resolved = resolve_config(config_path)

    assert config.targets[0].runtime_profile == "modern"
    assert config.targets[0].module == "ApiBlueprintExampleClient"
    assert resolved.targets[0].runtime_profile == "modern"
    assert resolved.targets[0].module == "ApiBlueprintExampleClient"
    assert target_manifest(resolved.targets[0], tmp_path)["module"] == "ApiBlueprintExampleClient"
    assert target_manifest(resolved.targets[0], tmp_path)["runtime_profile"] == "modern"

    bad_config_path = tmp_path / "bad-api-blueprint.toml"
    bad_config_path.write_text(
        """
[[targets]]
id = "swift.client"
kind = "swift-client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
runtime_profile = "legacy"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime_profile"):
        Config.load(bad_config_path)

def test_swift_client_module_can_differ_from_package(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "swift.client"
kind = "swift-client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = Config.load(config_path)
    resolved = resolve_config(config_path)
    manifest = target_manifest(resolved.targets[0], tmp_path)

    assert config.targets[0].package == "ApiBlueprintExampleClient"
    assert config.targets[0].module == "ABClient"
    assert resolved.targets[0].package == "ApiBlueprintExampleClient"
    assert resolved.targets[0].module == "ABClient"
    assert manifest["package"] == "ApiBlueprintExampleClient"
    assert manifest["module"] == "ABClient"

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

def test_http_transport_accepts_swift_client_target(tmp_path) -> None:
    config_path = tmp_path / "api-blueprint.toml"
    config_path.write_text(
        """
[[targets]]
id = "kotlin.server"
kind = "kotlin-server"
out_dir = "kotlin/server"
package = "com.example.generated"

[[targets]]
id = "swift.client"
kind = "swift-client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"

[[transport.http]]
id = "http"
server = "kotlin.server"
clients = ["swift.client"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    resolved = resolve_config(config_path)

    assert resolved.targets[2].clients == ("swift.client",)

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
