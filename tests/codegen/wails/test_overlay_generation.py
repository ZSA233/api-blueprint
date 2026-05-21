from __future__ import annotations

from .helpers import *


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
    _write_wails_vnext_config(config, go_out=shared_go.name, ts_out=shared_ts.name)
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    shared_go_client = shared_go / "routes" / "api" / "demo" / "gen_interface.go"
    shared_ts_client_path = shared_ts / "api" / "routes" / "api" / "demo" / "gen_client.ts"
    assert shared_go_client.is_file()
    assert shared_ts_client_path.is_file()
    shared_ts_client = shared_ts_client_path.read_text(encoding="utf-8")

    go_overlay_service = (shared_go / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go").read_text(encoding="utf-8")
    go_overlay_types = (shared_go / "transports" / "wailsv3" / "api" / "demo" / "gen_overlay.go").read_text(encoding="utf-8")
    go_impl_service = (shared_go / "transports" / "wailsv3" / "api" / "demo" / "impl_service.go").read_text(encoding="utf-8")
    go_runtime = (shared_go / "transports" / "wailsv3" / "gen_runtime.go").read_text(encoding="utf-8")
    go_provider_context = (shared_go / "providers" / "gen_context.go").read_text(encoding="utf-8")
    go_provider_executor = (shared_go / "providers" / "gen_executor.go").read_text(encoding="utf-8")
    ts_overlay_transport = (shared_ts / "api" / "transports" / "wailsv3" / "gen_transport.ts").read_text(encoding="utf-8")
    ts_overlay_runtime = (shared_ts / "api" / "transports" / "wailsv3" / "gen_runtime.ts").read_text(encoding="utf-8")
    ts_overlay_connection = (shared_ts / "api" / "transports" / "wailsv3" / "gen_connection.ts").read_text(encoding="utf-8")
    ts_overlay_response = (shared_ts / "api" / "transports" / "wailsv3" / "gen_response.ts").read_text(encoding="utf-8")
    ts_overlay_bindings = (shared_ts / "api" / "transports" / "wailsv3" / "gen_bindings.ts").read_text(encoding="utf-8")
    ts_overlay_client = (shared_ts / "api" / "transports" / "wailsv3" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    ts_overlay_index = (shared_ts / "api" / "transports" / "wailsv3" / "api" / "gen_index.ts").read_text(encoding="utf-8")
    ts_overlay_factory = (shared_ts / "api" / "transports" / "wailsv3" / "api" / "gen_factory.ts").read_text(encoding="utf-8")

    assert "WrapRSP_JSON_CodeMessageDataEnvelope" in go_overlay_service
    assert "WrapRSP_JSON_CodeMessageDataEnvelope[" not in go_overlay_service
    assert "func (svc *DemoService) ConnectWs" not in go_overlay_service
    assert "func (svc *DemoService) SubscribeEvents" in go_overlay_service
    assert "func (svc *DemoService) OpenChat" in go_overlay_service
    assert 'RouteID:            "api.demo.stream.events"' in go_overlay_service
    assert 'EventBase:          "api_blueprint.stream.api.demo.stream.events"' in go_overlay_service
    assert 'RouteID:            "api.demo.channel.chat"' in go_overlay_service
    assert 'EventBase:          "api_blueprint.channel.api.demo.channel.chat"' in go_overlay_service
    assert "sharedprovider.NewStreamSession[OPEN_Events, DemoStreamMessage, CLOSE_Events]" in go_overlay_service
    assert (
        "sharedprovider.NewChannelSession[OPEN_Chat, SERVER_Chat_MESSAGE, CLIENT_Chat_MESSAGE, CLOSE_Chat]"
        in go_overlay_service
    )
    assert "SetConnectionHub(hub wailstransport.ConnectionHub)" in go_overlay_service
    assert re.search(r"\bpingExecutor\s+\*sharedprovider.RouteExecutor\[REQ_Ping_QUERY, any, RSP_Ping\]", go_overlay_service)
    assert not re.search(r"\bwsExecutor\s+\*sharedprovider.RouteExecutor", go_overlay_service)
    assert "sharedprovider.NewRouteExecutor(" in go_overlay_service
    assert "NewRouteExecutorWithInfo" not in go_overlay_service
    assert 'Root:      "api"' in go_overlay_service
    assert 'Group:     "demo"' in go_overlay_service
    assert 'Namespace: "demo"' in go_overlay_service
    assert 'Service:   "DemoService"' in go_overlay_service
    assert 'RouteID:   "api.demo.get.ping"' in go_overlay_service
    assert 'RouteID:   "api.demo.stream.events"' in go_overlay_service
    assert 'RouteID:   "api.demo.channel.chat"' in go_overlay_service
    assert 'Methods:   []string{"GET"}' in go_overlay_service
    assert 'Methods:   []string{"WS"}' not in go_overlay_service
    assert 'Methods:   []string{"STREAM"}' in go_overlay_service
    assert 'Methods:   []string{"CHANNEL"}' in go_overlay_service
    assert "Transport: sharedprovider.TransportWails" in go_overlay_service
    assert 'Scope:     sharedprovider.ConnectionScope("session")' in go_overlay_service
    assert '"req=Q|auth|handle|rsp=json@CodeMessageDataEnvelope"' in go_overlay_service
    assert '"req|auth|ws_handle|rsp=json@CodeMessageDataEnvelope"' not in go_overlay_service
    assert "ResolveProvider[" not in go_overlay_service
    assert not re.search(r"Executor \*sharedprovider[^\n]*\n\n\s*\w+Executor", go_overlay_service)
    assert not re.search(r"NewRouteExecutor[^\n]*\n\n\s*\w+Executor:", go_overlay_service)
    assert not re.search(r"return [^\n]+\n\n}", go_overlay_service)
    assert "executor := sharedprovider.NewRouteExecutor" not in go_overlay_service
    assert "svc.pingExecutor.Run(ctx)" in go_overlay_service
    assert "RunWSPreflight" not in go_overlay_service
    assert "RunWSHandler" not in go_overlay_service
    assert go_overlay_service.count("WrapConnectionSession(session, true)") == 2
    assert go_overlay_service.count("WrapConnectionSession(session, false)") == 2
    assert "response, invokeErr := svc.impl" not in go_overlay_service
    assert "type RouterInterface = sharedroutes.RouterInterface" in go_overlay_types
    assert "func NewService(dispatcher wailstransport.EventDispatcher)" in go_impl_service
    assert "return newGeneratedDemoService(shared.NewRouter(), dispatcher)" in go_impl_service
    assert 'package demo' in go_overlay_types
    assert 'package wailstransport' in go_runtime
    assert not (shared_go / "transports" / "wailsv3" / "api" / "demo" / "bindings").exists()
    assert not (shared_go / "transports" / "wailsv3" / "runtime").exists()
    assert not (shared_go / "transports" / "http").exists()
    assert not (shared_ts / "api" / "transports" / "http").exists()
    assert not (shared_go / "engine.go").exists()
    assert "type RouteExecutor[Q, B, P any] struct" in go_provider_executor
    assert "func (executor *RouteExecutor[Q, B, P]) RunWSPreflight" not in go_provider_executor
    assert "ctx.Route = &executor.Route" in go_provider_executor
    assert "type RouteInfo struct" in go_provider_context
    assert "Scope     ConnectionScope" in go_provider_context
    assert "Route    *RouteInfo" in go_provider_context
    assert "ctx.Gin.Next()" not in go_provider_context
    assert "type ReqEnvelopeOptions struct" in go_runtime
    assert "type ConnectionHub interface" in go_runtime
    assert "type ConnectionOpenEnvelope[Q any] struct" in go_runtime
    assert "type ConnectionOpenSpec struct" in go_runtime
    assert "Open(spec ConnectionOpenSpec) (ConnectionSession, error)" in go_runtime
    assert "type OrderedConnectionEnvelope struct" in go_runtime
    assert "var orderedConnectionStates sync.Map" in go_runtime
    assert "func WrapConnectionSession(session ConnectionSession, ordered bool) ConnectionSession" in go_runtime
    assert "func ConnectionOpenEnvelopeToReq[Q any]" in go_runtime
    assert "func ConnectionOpenHeaders[Q any]" in go_runtime
    assert "func ConnectionOpenEnvelopeSessionID[Q any](envelope *ConnectionOpenEnvelope[Q]) string" in go_runtime
    assert "func BuildConnectionDescriptor(spec ConnectionOpenSpec, sessionID string) SocketSessionDescriptor" in go_runtime
    assert "CloseJSON(ctx context.Context, payload any) error" in go_runtime
    assert "connection scope[%s] is not supported by the default SocketHub" in go_runtime
    assert "if options.BindQuery" in go_runtime
    assert 'return nil, fmt.Errorf("[WailsReq] json body is required")' in go_runtime
    assert "wailstransport.ReqEnvelopeOptions{" in go_overlay_service
    assert "wailstransport.EnvelopeToReq[" not in go_overlay_service
    assert "openSpec := wailstransport.ConnectionOpenSpec{" in go_overlay_service
    assert "wailstransport.ConnectionOpenEnvelopeToReq(" in go_overlay_service
    assert "wailstransport.ConnectionOpenHeaders(envelope)" in go_overlay_service
    assert "wailstransport.ConnectionOpenEnvelopeSessionID(envelope)" in go_overlay_service
    assert "envelope.SessionID" not in go_overlay_service
    assert "BindQuery: true" in go_overlay_service
    assert "type CONNECTION_CONNECT_Events = wailstransport.ConnectionOpenEnvelope[OPEN_Events]" in go_overlay_types
    assert "type CONNECTION_CONNECT_Chat = wailstransport.ConnectionOpenEnvelope[OPEN_Chat]" in go_overlay_types
    assert "export class WailsV3Transport implements ApiTransport" in ts_overlay_transport
    assert 'export { ensureWailsRuntime } from "./gen_runtime";' in ts_overlay_transport
    assert 'import { WailsStreamBridge, WailsSocketBridge } from "./gen_connection";' in ts_overlay_transport
    assert 'import type { WailsConnectionOpenEnvelope, WailsRuntimeAdapter } from "./gen_connection";' in ts_overlay_transport
    assert 'import { unwrapResponseEnvelope } from "./gen_response";' in ts_overlay_transport
    assert "export async function ensureWailsRuntime(): Promise<void>" in ts_overlay_runtime
    assert "type WailsConnectionOpenEnvelope<Query> = {" not in ts_overlay_transport
    assert "function generateWailsConnectionSessionId(routeId: string): string {" not in ts_overlay_transport
    assert "export type WailsConnectionOpenEnvelope<Query> = {" in ts_overlay_connection
    assert "function generateWailsConnectionSessionId(routeId: string): string {" in ts_overlay_connection
    assert "function buildWailsConnectionEventName(eventBase: string, kind: \"message\" | \"closed\", sessionId: string): string {" in ts_overlay_connection
    assert "type WailsOrderedEnvelope<Payload> = {" in ts_overlay_connection
    assert "const WAILS_ORDERED_DELIVERY_GAP_TIMEOUT_MS =" in ts_overlay_connection
    assert "const WAILS_ORDERED_DELIVERY_MAX_PENDING_MESSAGES =" in ts_overlay_connection
    assert "private readonly pendingMessages = new Map<number, Recv>();" in ts_overlay_connection
    assert "private gapTimeoutHandle: ReturnType<typeof setTimeout> | null = null;" in ts_overlay_connection
    assert "private subscribedSession: WailsSocketSession | null = null;" in ts_overlay_connection
    assert "const provisionalSession: WailsSocketSession = {" in ts_overlay_connection
    assert "this.subscribedSession = provisionalSession;" in ts_overlay_connection
    assert "export type WailsRuntimeAdapter = {" in ts_overlay_connection
    assert "protected readonly runtime: WailsRuntimeAdapter" in ts_overlay_connection
    assert "this.runtime.buildConnectionEnvelope(" in ts_overlay_connection
    assert "export function unwrapResponseEnvelope" in ts_overlay_response
    assert "protected buildEnvelope(" in ts_overlay_transport
    assert "protected buildConnectionEnvelope(" in ts_overlay_transport
    assert "private createRuntimeAdapter(): WailsRuntimeAdapter" in ts_overlay_transport
    assert "buildWailsEnvelope(" not in ts_overlay_transport
    assert "buildWailsConnectionEnvelope(" not in ts_overlay_transport
    assert "this.runtime.invokeOperation" not in ts_overlay_transport
    assert "this.runtime.subscribeEvent" not in ts_overlay_transport
    assert "this.runtime.unsubscribeEvent" not in ts_overlay_transport
    ensure_index = ts_overlay_connection.index("await ensureWailsRuntime();")
    subscribe_index = ts_overlay_connection.index("this.runtime.subscribe(messageEvent, this.messageHandler);")
    invoke_index = ts_overlay_connection.index("const session = await this.runtime.invoke<WailsSocketSession>(")
    assert ensure_index < subscribe_index
    assert subscribe_index < invoke_index
    assert 'error: "ordered_delivery_gap"' in ts_overlay_connection
    assert 'error: "ordered_delivery_protocol_error"' in ts_overlay_connection
    assert 'error: "ordered_delivery_buffer_overflow"' in ts_overlay_connection
    assert "this.startOrderedGapTimer();" in ts_overlay_connection
    assert "this.clearOrderedGapTimer();" in ts_overlay_connection
    assert "this.failOrderedDelivery(" in ts_overlay_connection
    assert "ByName?: (name: string, ...args: unknown[]) => Promise<unknown>;" in ts_overlay_runtime
    assert "callByName(bindingName, payload)" in ts_overlay_transport
    assert 'import { WAILS_V3_BINDINGS } from "./gen_bindings";' in ts_overlay_runtime
    assert "const WAILS_V3_BINDINGS" not in ts_overlay_transport
    assert "export const WAILS_V3_BINDINGS" in ts_overlay_bindings
    assert "window.wails.Call is not available" not in ts_overlay_transport
    assert "(event as { data?: unknown }).data" in ts_overlay_runtime
    assert (
        '"demo.DemoService.Ping": '
        '"example.com/generated/golang/transports/wailsv3/api/demo.DemoService.Ping"'
        in ts_overlay_bindings
    )
    assert "DemoService.ConnectWs" not in ts_overlay_bindings
    assert "DemoService.SendWs" not in ts_overlay_bindings
    assert "DemoService.CloseWs" not in ts_overlay_bindings
    assert (
        '"demo.DemoService.SubscribeEvents": '
        '"example.com/generated/golang/transports/wailsv3/api/demo.DemoService.SubscribeEvents"'
        in ts_overlay_bindings
    )
    assert (
        '"demo.DemoService.OpenChat": '
        '"example.com/generated/golang/transports/wailsv3/api/demo.DemoService.OpenChat"'
        in ts_overlay_bindings
    )
    assert "export class DemoClient" not in ts_overlay_client
    assert "export type DemoClient = SharedDemoClient;" in ts_overlay_client
    assert "export function createClient(config: ApiClientConfig = {}): DemoClient" in ts_overlay_client
    assert "transport: config.transport ?? new WailsV3Transport(config)" in ts_overlay_client
    assert 'delivery: "ordered"' in shared_ts_client
    assert 'delivery: "unordered"' in shared_ts_client
    assert "connectWsRaw(" not in ts_overlay_client
    assert 'import { createClient as createDemoClient } from "./demo/client";' in ts_overlay_factory
    assert "demoClient: createDemoClient(config)," in ts_overlay_factory
    assert 'import { WailsV3Transport } from "../../transport";' in ts_overlay_client
    assert 'export * as Demo from "./demo";' in ts_overlay_index
    assert 'export * from "./factory";' in ts_overlay_index
    assert not (shared_ts / "api" / "transports" / "wailsv3" / "api" / "demo" / "gen_models.ts").exists()

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
    _write_wails_vnext_config(
        config,
        go_out=shared_go.name,
        ts_out=shared_ts.name,
        include=("group:demo",),
        with_http_transport=True,
    )
    _write_multi_group_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    assert (shared_go / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go").is_file()
    assert (shared_go / "transports" / "wailsv3" / "api" / "demo" / "impl_service.go").is_file()
    assert not (shared_go / "transports" / "wailsv3" / "api" / "demo" / "bindings").exists()
    assert not (shared_go / "transports" / "wailsv3" / "api" / "hello").exists()
    assert (shared_go / "routes" / "api" / "hello" / "gen_interface.go").is_file()

    assert (shared_ts / "api" / "transports" / "wailsv3" / "api" / "demo" / "gen_client.ts").is_file()
    assert not (shared_ts / "api" / "transports" / "wailsv3" / "api" / "hello").exists()
    assert (shared_ts / "api" / "routes" / "api" / "hello" / "gen_client.ts").is_file()
    transport_clients = (shared_ts / "api" / "transports" / "gen_clients.ts").read_text(encoding="utf-8")
    transport_index = (shared_ts / "api" / "transports" / "gen_index.ts").read_text(encoding="utf-8")
    assert 'import type { GeneratedClients as HttpGeneratedClients } from "./http/api/factory";' in transport_clients
    assert 'import { createClients as createHttpClients } from "./http/api/factory";' in transport_clients
    assert 'import type { GeneratedClients as WailsV3GeneratedClients } from "./wailsv3/api/factory";' in transport_clients
    assert 'import { createClients as createWailsV3Clients } from "./wailsv3/api/factory";' in transport_clients
    assert 'export type ApiTransportName = "http" | "wailsv3";' in transport_clients
    assert "export interface CommonGeneratedClients {\n  demoClient: DemoClient;\n}" in transport_clients
    assert "helloClient:" not in transport_clients
    assert "export function createClientsForTransport(config: ApiTransportClientConfig): CommonGeneratedClients" in transport_clients
    assert "demoClient: new DemoClientImpl(config)," in transport_clients
    assert 'export * from "./clients";' in transport_index

def test_wails_codegen_does_not_emit_typescript_overlay_for_unselected_root(tmp_path: Path):
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
    _write_wails_vnext_config(
        config,
        entrypoints='"blueprints.app:api_bp", "blueprints.app:third_bp"',
        go_out=shared_go.name,
        ts_out=shared_ts.name,
        include=("path:/api/**",),
    )
    _write_multi_root_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    assert (shared_go / "routes" / "third" / "proxy" / "gen_interface.go").is_file()
    assert (shared_ts / "third" / "routes" / "third" / "proxy" / "gen_client.ts").is_file()
    assert (shared_ts / "api" / "transports" / "wailsv3" / "api" / "demo" / "gen_client.ts").is_file()
    assert not (shared_go / "transports" / "wailsv3" / "third").exists()
    assert not (shared_ts / "third" / "transports" / "wailsv3").exists()
    assert "Transports" not in (shared_ts / "third" / "gen_index.ts").read_text(encoding="utf-8")

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
    _write_wails_vnext_config(
        config,
        go_out=shared_go.name,
        ts_out=shared_ts.name,
        target_id="desktop.v2",
        version="v2",
    )
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config, target_id="desktop.v2")
    assert result.exit_code == 0, result.output

    ts_overlay_transport = (shared_ts / "api" / "transports" / "wailsv2" / "gen_transport.ts").read_text(
        encoding="utf-8"
    )
    ts_overlay_runtime = (shared_ts / "api" / "transports" / "wailsv2" / "gen_runtime.ts").read_text(
        encoding="utf-8"
    )
    ts_overlay_connection = (shared_ts / "api" / "transports" / "wailsv2" / "gen_connection.ts").read_text(
        encoding="utf-8"
    )

    assert "export async function ensureWailsRuntime(): Promise<void>" in ts_overlay_runtime
    assert 'export { ensureWailsRuntime } from "./gen_runtime";' in ts_overlay_transport
    assert 'await loadWailsScript("/wails/ipc.js")' in ts_overlay_runtime
    assert 'await loadWailsScript("/wails/runtime.js")' in ts_overlay_runtime
    assert "export class WailsStreamBridge" in ts_overlay_connection
    assert "const namespaceObject = window.go?.[namespace]" in ts_overlay_transport
    assert "return await fn(payload) as R" in ts_overlay_transport
    assert "off(name);" in ts_overlay_transport
    assert "off(name, handler)" not in ts_overlay_transport
    assert "Call.ByName" not in ts_overlay_runtime
    assert "WailsV3Runtime" not in ts_overlay_runtime
    assert "window.wails" not in ts_overlay_runtime
    assert not (shared_ts / "api" / "transports" / "wailsv2" / "gen_bindings.ts").exists()

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
    _write_wails_vnext_config(
        config,
        go_out=shared_go.name,
        ts_out=shared_ts.name,
        frontend_mode="none",
    )
    _write_blueprint_package(tmp_path)

    result = _invoke_wails_generate(config)
    assert result.exit_code == 0, result.output

    assert (shared_go / "transports" / "wailsv3" / "api" / "demo" / "gen_service.go").is_file()
    assert (shared_go / "transports" / "wailsv3" / "api" / "demo" / "impl_service.go").is_file()
    assert not (shared_ts / "api" / "transports" / "wailsv3").exists()
    assert (shared_ts / "api" / "routes" / "api" / "demo" / "gen_client.ts").is_file()
