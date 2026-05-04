from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

from api_blueprint.cli.apigen import gen_wails


def _write_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model, String
from api_blueprint.engine.wrapper import GeneralWrapper

class WSRecv(Model):
    message = String(description="message")

class WSSend(Model):
    message = String(description="message")

bp = Blueprint(root="/api", response_wrapper=GeneralWrapper)
with bp.group("/demo") as views:
    views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))
    views.WS("/ws").RECV(WSRecv).SEND(WSSend)
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def _write_multi_group_blueprint_package(tmp_path: Path) -> None:
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import String

bp = Blueprint(root="/api")
with bp.group("/demo") as views:
    views.GET("/ping").RSP(message=String(description="message"))

with bp.group("/hello") as views:
    views.GET("/pong").RSP(message=String(description="message"))
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def test_wails_codegen_generates_shared_contracts_and_overlays(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
frontend_mode = "external"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    shared_go_client = shared_go / "views" / "api" / "demo" / "gen_interface.go"
    shared_ts_client = shared_ts / "api" / "demo" / "gen_client.ts"
    assert shared_go_client.is_file()
    assert shared_ts_client.is_file()

    go_overlay_service = (shared_go / "views" / "api" / "demo" / "_wailsv3" / "gen_service.go").read_text(encoding="utf-8")
    go_overlay_types = (shared_go / "views" / "api" / "demo" / "_wailsv3" / "gen_overlay.go").read_text(encoding="utf-8")
    go_binding_service = (shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "gen_service.go").read_text(encoding="utf-8")
    go_runtime = (shared_go / "views" / "_wailsv3" / "runtime" / "gen_runtime.go").read_text(encoding="utf-8")
    go_http_engine = (shared_go / "views" / "_http" / "gen_engine.go").read_text(encoding="utf-8")
    go_provider_context = (shared_go / "views" / "provider" / "gen_context.go").read_text(encoding="utf-8")
    go_provider_executor = (shared_go / "views" / "provider" / "gen_executor.go").read_text(encoding="utf-8")
    ts_overlay_transport = (shared_ts / "api" / "(shared)" / "(wailsv3)" / "gen_transport.ts").read_text(encoding="utf-8")
    ts_overlay_client = (shared_ts / "api" / "demo" / "(wailsv3)" / "gen_client.ts").read_text(encoding="utf-8")
    ts_overlay_index = (shared_ts / "api" / "(wailsv3)" / "gen_index.ts").read_text(encoding="utf-8")
    ts_overlay_factory = (shared_ts / "api" / "(wailsv3)" / "gen_factory.ts").read_text(encoding="utf-8")

    assert "WrapRSP_JSON_GeneralWrapper" in go_overlay_service
    assert "func (svc *DemoService) ConnectWs" in go_overlay_service
    assert re.search(r"\bpingExecutor\s+\*sharedprovider.RouteExecutor\[REQ_Ping_QUERY, any, RSP_Ping\]", go_overlay_service)
    assert re.search(r"\bwsExecutor\s+\*sharedprovider.RouteExecutor\[any, any, RSP_Ws\]", go_overlay_service)
    assert re.search(r"\bpingExecutor:\s+sharedprovider.NewRouteExecutor\[REQ_Ping_QUERY, any, RSP_Ping\]", go_overlay_service)
    assert re.search(r"\bwsExecutor:\s+sharedprovider.NewRouteExecutor\[any, any, RSP_Ws\]", go_overlay_service)
    assert not re.search(r"Executor \*sharedprovider[^\n]*\n\n\s*\w+Executor", go_overlay_service)
    assert not re.search(r"NewRouteExecutor[^\n]*\n\n\s*\w+Executor:", go_overlay_service)
    assert not re.search(r"return [^\n]+\n\n}", go_overlay_service)
    assert "executor := sharedprovider.NewRouteExecutor" not in go_overlay_service
    assert "svc.pingExecutor.Run(ctx)" in go_overlay_service
    assert "svc.wsExecutor.RunWSPreflight(ctx)" in go_overlay_service
    assert "svc.wsExecutor.RunWSHandler(ctx)" in go_overlay_service
    assert "response, invokeErr := svc.impl" not in go_overlay_service
    assert "type RouterInterface = sharedroutes.RouterInterface" in go_overlay_types
    assert "package demo" in go_binding_service
    assert "type DemoService struct" in go_binding_service
    assert "generated.NewDemoService(shared.NewRouter(), dispatcher)" in go_binding_service
    assert 'package wailsv3' in go_overlay_types
    assert 'package runtime' in go_runtime
    assert "provider.NewRouteExecutor" in go_http_engine
    assert not (shared_go / "views" / "engine.go").exists()
    assert "type RouteExecutor[Q, B, P any] struct" in go_provider_executor
    assert "func (executor *RouteExecutor[Q, B, P]) RunWSPreflight" in go_provider_executor
    assert "ctx.Gin.Next()" not in go_provider_context
    assert "type ReqEnvelopeOptions struct" in go_runtime
    assert "if options.BindQuery" in go_runtime
    assert 'return nil, fmt.Errorf("[WailsReq] json body is required")' in go_runtime
    assert "runtime.ReqEnvelopeOptions{" in go_overlay_service
    assert "BindQuery: true" in go_overlay_service
    assert "export class WailsV3Transport implements ApiTransport" in ts_overlay_transport
    assert "export async function ensureWailsRuntime(): Promise<void>" in ts_overlay_transport
    assert "Call.ByName" in ts_overlay_transport
    assert "callByName(bindingName, payload)" in ts_overlay_transport
    assert "window.wails.Call is not available" not in ts_overlay_transport
    assert "(event as { data?: unknown }).data" in ts_overlay_transport
    assert (
        '"demo.DemoService.Ping": '
        '"example.com/generated/golang/views/api/demo/_wailsv3/bindings.DemoService.Ping"'
        in ts_overlay_transport
    )
    assert (
        '"demo.DemoService.ConnectWs": '
        '"example.com/generated/golang/views/api/demo/_wailsv3/bindings.DemoService.ConnectWs"'
        in ts_overlay_transport
    )
    assert (
        '"demo.DemoService.SendWs": '
        '"example.com/generated/golang/views/api/demo/_wailsv3/bindings.DemoService.SendWs"'
        in ts_overlay_transport
    )
    assert (
        '"demo.DemoService.CloseWs": '
        '"example.com/generated/golang/views/api/demo/_wailsv3/bindings.DemoService.CloseWs"'
        in ts_overlay_transport
    )
    assert "export class DemoClient" not in ts_overlay_client
    assert "export type DemoClient = Omit<SharedDemoClient, HiddenRawWebSocketMethods>;" in ts_overlay_client
    assert "export function createClient(config: ApiClientConfig = {}): DemoClient" in ts_overlay_client
    assert "transport: config.transport ?? new WailsV3Transport(config)" in ts_overlay_client
    assert "connectWsRaw(" not in ts_overlay_client
    assert 'import { createClient as createDemoClient } from "../demo/(wailsv3)/client";' in ts_overlay_factory
    assert "demoClient: createDemoClient(config)," in ts_overlay_factory
    assert 'import { WailsV3Transport } from "../../(shared)/(wailsv3)/transport";' in ts_overlay_client
    assert 'export * as Shared from "../(shared)/(wailsv3)";' in ts_overlay_index
    assert 'export * from "./factory";' in ts_overlay_index
    assert not (shared_ts / "api" / "demo" / "(wailsv3)" / "gen_models.ts").exists()


def test_wails_codegen_filters_only_overlay_outputs(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
include = ["group:demo"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_multi_group_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    assert (shared_go / "views" / "api" / "demo" / "_wailsv3" / "gen_service.go").is_file()
    assert (shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "gen_service.go").is_file()
    assert not (shared_go / "views" / "_wailsv3" / "bindings").exists()
    assert not (shared_go / "views" / "api" / "hello" / "_wailsv3").exists()
    assert (shared_go / "views" / "api" / "hello" / "gen_interface.go").is_file()

    assert (shared_ts / "api" / "demo" / "(wailsv3)" / "gen_client.ts").is_file()
    assert not (shared_ts / "api" / "hello" / "(wailsv3)").exists()
    assert (shared_ts / "api" / "hello" / "gen_client.ts").is_file()


def test_wails_v2_transport_keeps_runtime_contract(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v2"
version = "v2"
frontend_mode = "external"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    ts_overlay_transport = (shared_ts / "api" / "(shared)" / "(wailsv2)" / "gen_transport.ts").read_text(
        encoding="utf-8"
    )

    assert "export async function ensureWailsRuntime(): Promise<void>" in ts_overlay_transport
    assert 'await loadWailsScript("/wails/ipc.js")' in ts_overlay_transport
    assert 'await loadWailsScript("/wails/runtime.js")' in ts_overlay_transport
    assert "const namespaceObject = window.go?.[namespace]" in ts_overlay_transport
    assert "return await fn(payload) as R" in ts_overlay_transport
    assert "off(name);" in ts_overlay_transport
    assert "off(name, handler)" not in ts_overlay_transport
    assert "Call.ByName" not in ts_overlay_transport
    assert "WailsV3Runtime" not in ts_overlay_transport
    assert "window.wails" not in ts_overlay_transport


def test_wails_codegen_frontend_mode_none_skips_typescript_overlay(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
frontend_mode = "none"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    assert (shared_go / "views" / "api" / "demo" / "_wailsv3" / "gen_service.go").is_file()
    assert (shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "gen_service.go").is_file()
    assert not (shared_ts / "api" / "(shared)" / "(wailsv3)").exists()
    assert not (shared_ts / "api" / "demo" / "(wailsv3)").exists()
    assert (shared_ts / "api" / "demo" / "gen_client.ts").is_file()


def test_wails_codegen_uses_custom_provider_package_and_binding_hook(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"
provider_package = "providers"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    provider_file = shared_go / "views" / "providers" / "gen_provider.go"
    route_file = shared_go / "views" / "api" / "demo" / "gen_protos.go"
    overlay_service = shared_go / "views" / "api" / "demo" / "_wailsv3" / "gen_service.go"
    runtime_file = shared_go / "views" / "_wailsv3" / "runtime" / "gen_runtime.go"
    binding_gen = shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "gen_service.go"
    binding_impl = shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "impl_service.go"
    expected_provider_import = f'providers "example.com/generated/{shared_go.name}/views/providers"'
    expected_shared_provider_import = f'sharedprovider "example.com/generated/{shared_go.name}/views/providers"'

    assert provider_file.is_file()
    assert binding_impl.is_file()
    assert 'package providers' in provider_file.read_text(encoding="utf-8")
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert expected_shared_provider_import in overlay_service.read_text(encoding="utf-8")
    assert expected_shared_provider_import in runtime_file.read_text(encoding="utf-8")
    assert "func newGeneratedDemoService" in binding_gen.read_text(encoding="utf-8")
    assert "func NewService(" not in binding_gen.read_text(encoding="utf-8")
    assert "func NewService(dispatcher runtime.EventDispatcher)" in binding_impl.read_text(encoding="utf-8")
    assert "return newGeneratedDemoService(dispatcher)" in binding_impl.read_text(encoding="utf-8")


def test_wails_codegen_errors_when_filters_remove_all_routes(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
include = ["group:missing"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "没有可生成的 route" in str(result.exception)


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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    _write_blueprint_package(tmp_path)

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    impl_service = shared_go / "views" / "api" / "demo" / "_wailsv3" / "bindings" / "impl_service.go"
    custom_impl = """
package demo

import runtime "example.com/generated/views/_wailsv3/runtime"

func NewService(dispatcher runtime.EventDispatcher) *DemoService {
	return newGeneratedDemoService(dispatcher)
}

// custom binding hook
    """.strip() + "\n"
    impl_service.write_text(custom_impl, encoding="utf-8")

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code == 0, result.output

    assert "custom binding hook" in impl_service.read_text(encoding="utf-8")


def test_golang_provider_impl_files_are_preserved_on_regeneration(tmp_path: Path):
    from api_blueprint.writer.golang.writer import GolangWriter
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

    impl_auth = output_dir / "views" / "provider" / "impl_auth.go"
    impl_auth.write_text("package provider\n\n// custom auth hook\n", encoding="utf-8")

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert impl_auth.read_text(encoding="utf-8") == "package provider\n\n// custom auth hook\n"


def test_wails_codegen_rejects_provider_package_conflicting_with_blueprint_root(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"
provider_package = "provider"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/provider")
with bp.group("/demo") as views:
    views.GET("/ping").RSP()
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "provider_package[provider]" in str(result.exception)
    assert "blueprint root[provider]" in str(result.exception)


def test_wails_codegen_rejects_go_reserved_namespace_segments(tmp_path: Path):
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
    config.write_text(
        f"""
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "{shared_go.name}"

[typescript]
codegen_output = "{shared_ts.name}"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    pkg = tmp_path / "blueprints"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        """
from api_blueprint.engine import Blueprint

bp = Blueprint(root="/api")
with bp.group("/_demo") as views:
    views.GET("/ping").RSP()
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(gen_wails, ["-c", str(config)])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "保留目录段[_demo]" in str(result.exception)
