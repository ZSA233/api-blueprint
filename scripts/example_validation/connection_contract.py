from __future__ import annotations

from .models import BlueprintExampleWorkspace, ExampleValidationError

def _validate_blueprint_connection_examples(workspace: BlueprintExampleWorkspace) -> None:
    files = {
        "go_route_interface": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go",
        "go_route_gen_impl": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_impl.go",
        "go_route_types": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_types.go",
        "go_route_client_message": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_message.go",
        "go_route_client_constructors": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_constructors.go",
        "go_route_client_processor": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_processor.go",
        "go_route_client_visitor": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_visitor.go",
        "go_route_client_cases": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_cases.go",
        "go_route_impl": workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "impl.go",
        "go_route_assistant_session": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_session.go",
        "go_route_assistant_processor": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_processor.go",
        "go_route_assistant_error": workspace.golang_server_dir
        / "views"
        / "routes"
        / "api"
        / "demo"
        / "assistant_session_error.go",
        "go_http_adapter": workspace.golang_server_dir / "views" / "transports" / "http" / "api" / "demo" / "gen_interface.go",
        "go_client_route": workspace.golang_client_dir / "routes" / "api" / "demo" / "gen_client.go",
        "go_client_message_constructors": workspace.golang_client_dir
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_client_message_constructors.go",
        "go_client_sweep_visitor": workspace.golang_client_dir
        / "routes"
        / "api"
        / "demo"
        / "gen_sweep_stream_message_visitor.go",
        "go_client_server_visitor": workspace.golang_client_dir
        / "routes"
        / "api"
        / "demo"
        / "gen_assistant_server_message_visitor.go",
        "go_client_http": workspace.golang_client_dir / "transports" / "http" / "gen_transport.go",
        "go_error_lookup": workspace.golang_client_dir / "runtime" / "gen_error_lookup.go",
        "go_wails_v3_service": workspace.golang_server_dir
        / "views"
        / "transports"
        / "wailsv3"
        / "api"
        / "demo"
        / "gen_service.go",
        "ts_wails_v3_transport": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_transport.ts",
        "ts_wails_v3_runtime": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_runtime.ts",
        "ts_wails_v3_bindings": workspace.typescript_dir
        / "api"
        / "transports"
        / "wailsv3"
        / "gen_bindings.ts",
        "index": workspace.root / "api-blueprint.index.json",
        "ts_suite": workspace.typescript_dir / "suite.ts",
        "ts_route_client": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts",
        "ts_route_types": workspace.typescript_dir / "api" / "routes" / "api" / "demo" / "gen_types.ts",
        "ts_error_lookup": workspace.typescript_dir / "api" / "runtime" / "gen_error_lookup.ts",
        "python_binary_route": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_types.py",
        "python_error_lookup": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "runtime"
        / "gen_error_lookup.py",
        "python_client_demo_types": workspace.python_dir
        / "client"
        / "api_blueprint_example_client"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_types.py",
        "python_server_demo_types": workspace.python_dir
        / "server"
        / "api_blueprint_example_server"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_types.py",
        "kotlin_client_api_json": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "runtime"
        / "GenApiJson.kt",
        "kotlin_client_route": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoApi.kt",
        "kotlin_client_demo_types": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoTypes.kt",
        "kotlin_client_http": workspace.kotlin_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "transports"
        / "http"
        / "GenOkHttpApiTransport.kt",
        "kotlin_server_demo_types": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoTypes.kt",
        "kotlin_server_service": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoService.kt",
        "kotlin_server_ktor": workspace.kotlin_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "transports"
        / "ktor"
        / "api"
        / "demo"
        / "GenDemoKtorRoutes.kt",
        "java_client_demo_types": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoTypes.java",
        "java_client_route": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "GenDemoApi.java",
        "java_client_api_json": workspace.java_client_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "runtime"
        / "GenApiJson.java",
        "java_server_demo_types": workspace.java_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "types"
        / "GenDemoTypes.java",
        "java_server_demo_controller": workspace.java_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "controllers"
        / "GenDemoController.java",
        "java_server_demo_delegate": workspace.java_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "delegates"
        / "GenDemoDelegate.java",
        "java_server_contract_assertions": workspace.java_server_dir
        / "com"
        / "example"
        / "apiblueprint"
        / "api"
        / "spring"
        / "GenSpringMvcContractAssertions.java",
        "flutter_runtime_client": workspace.flutter_dir / "lib" / "src" / "api" / "runtime" / "gen_api_client.dart",
        "flutter_runtime_errors": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "runtime"
        / "gen_api_error_lookup.dart",
        "flutter_demo_api": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_demo_api.dart",
        "flutter_demo_types": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "demo"
        / "gen_demo_types.dart",
        "flutter_binary": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "routes"
        / "api"
        / "binary"
        / "gen_binary.dart",
        "flutter_http_transport": workspace.flutter_dir
        / "lib"
        / "src"
        / "api"
        / "transports"
        / "http"
        / "gen_http_api_transport.dart",
    }
    missing_files = [label for label, path in files.items() if not path.is_file()]
    if missing_files:
        raise ExampleValidationError("blueprint connection example missing generated files:\n" + "\n".join(missing_files))

    checks = {
        "go stream handler": (
            files["go_route_interface"],
            "SweepEvents(\n"
            "\t\tctx *CTX_SweepEvents,\n"
            "\t\tstream STREAM_SweepEvents,\n"
            "\t) error",
        ),
        "go channel handler": (
            files["go_route_interface"],
            "AssistantSession(\n"
            "\t\tctx *CTX_AssistantSession,\n"
            "\t\tchannel CHANNEL_AssistantSession,\n"
            "\t) error",
        ),
        "go stream message constructor example": (
            files["go_route_impl"],
            "message, err := NewSweepStreamMessageState(&SweepStreamMessage_State_DATA{",
        ),
        "go stream context send example": (files["go_route_impl"], "if err := stream.Send(ctx, message); err != nil {"),
        "go stream context close example": (
            files["go_route_impl"],
            'return stream.Close(ctx, &CLOSE_SweepEvents{Code: 1000, Reason: "example stream complete"})',
        ),
        "go channel scaffold route": (
            files["go_route_assistant_session"],
            "session := newAssistantSessionRouteSession(impl, ctx, channel, &assistantSessionMessageProcessor{})",
        ),
        "go channel scaffold serve loop": (
            files["go_route_assistant_session"],
            "message, err := session.channel.Recv(session.Context())",
        ),
        "go channel scaffold visitor": (
            files["go_route_assistant_session"],
            "if err := VisitAssistantClientMessage(session.messageScope(), message, session.processor); err != nil {",
        ),
        "go channel scaffold scope channel": (
            files["go_route_assistant_session"],
            "Channel CHANNEL_AssistantSession",
        ),
        "go channel processor example": (
            files["go_route_assistant_processor"],
            "type assistantSessionMessageProcessor struct{}",
        ),
        "go channel processor contract": (
            files["go_route_assistant_processor"],
            "var _ AssistantClientMessageProcessor[assistantSessionMessageScope] = (*assistantSessionMessageProcessor)(nil)",
        ),
        "go channel processor input": (
            files["go_route_assistant_processor"],
            "func (processor *assistantSessionMessageProcessor) OnInput(",
        ),
        "go channel processor cancel": (
            files["go_route_assistant_processor"],
            "func (processor *assistantSessionMessageProcessor) OnCancel(",
        ),
        "go channel processor constructor": (
            files["go_route_assistant_processor"],
            "message, err := NewAssistantServerMessageDelta(&AssistantServerMessage_Delta_DATA{",
        ),
        "go channel processor context send": (
            files["go_route_assistant_processor"],
            "return scope.Channel.Send(scope.Context, message)",
        ),
        "go channel processor context close": (
            files["go_route_assistant_processor"],
            "return scope.Channel.Close(scope.Context, &CLOSE_AssistantSession{Code: 1000, Reason: reason})",
        ),
        "go channel error scaffold": (
            files["go_route_assistant_error"],
            "func (session *assistantSessionRouteSession) handleMessageError(",
        ),
        "go channel error typed helper": (
            files["go_route_assistant_error"],
            "IsAssistantClientMessageErrorKind(err, AssistantClientMessageErrorNilProcessor)",
        ),
        "go channel error message type helper": (
            files["go_route_assistant_error"],
            "messageErr.MessageType()",
        ),
        "go generated channel processor": (
            files["go_route_client_processor"],
            "type AssistantClientMessageProcessor[C any] interface {",
        ),
        "go generated channel visitor": (
            files["go_route_client_visitor"],
            "func VisitAssistantClientMessage[C any](",
        ),
        "go generated channel case": (
            files["go_route_client_cases"],
            "type AssistantClientMessageInputCase struct {",
        ),
        "go generated channel decode error": (
            files["go_route_client_cases"],
            "AssistantClientMessageErrorDecodeFailed",
        ),
        "go generated channel handler error": (
            files["go_route_client_visitor"],
            "AssistantClientMessageErrorHandlerFailed",
        ),
        "go generated channel error helper": (
            files["go_route_client_visitor"],
            "func IsAssistantClientMessageErrorKind(err error, kinds ...AssistantClientMessageErrorKind) bool",
        ),
        "go generated connection messages": (
            files["go_route_client_message"],
            "type AssistantClientMessage struct {",
        ),
        "go generated message constructor": (
            files["go_route_client_constructors"],
            "func NewAssistantClientMessageCancel(",
        ),
        "go typed error return example": (files["go_route_impl"], "return nil, demo_err.RATE_LIMITED.WithToast("),
        "go typed error dynamic toast": (files["go_route_impl"], 'Text:    "请等待 30 秒后重试",'),
        "go unknown typed error example": (
            files["go_route_impl"],
            'return nil, apperrors.New(70001, "example undefined business error")',
        ),
        "go error demo client": (files["go_client_route"], "ErrorDemo("),
        "go error demo route lookup": (
            files["go_error_lookup"],
            'DemoErrRateLimited:   ApiErrorsByID["DemoErr.RATE_LIMITED"],',
        ),
        "go error demo constant": (files["go_error_lookup"], "DemoErrRateLimited   ApiErrorCode = 42901"),
        "go client unsupported connection": (files["go_client_http"], "UnsupportedConnectionError"),
        "go client generated connection messages": (
            files["go_client_message_constructors"],
            "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA)",
        ),
        "go client generated stream visitor": (
            files["go_client_sweep_visitor"],
            "func VisitSweepStreamMessage[C any](",
        ),
        "go client generated channel visitor": (
            files["go_client_server_visitor"],
            "func VisitAssistantServerMessage[C any](",
        ),
        "http stream adapter": (files["go_http_adapter"], "httptransport.STREAM("),
        "http channel adapter": (files["go_http_adapter"], "httptransport.CHANNEL("),
        "wails stream event base": (
            files["go_wails_v3_service"],
            'RouteID:            "api.demo.stream.sweepevents"',
        ),
        "wails channel event base": (
            files["go_wails_v3_service"],
            'RouteID:            "api.demo.channel.assistantsession"',
        ),
        "typescript stream client": (files["ts_route_client"], "subscribeSweepEvents("),
        "typescript channel client": (files["ts_route_client"], "openAssistantSession("),
        "typescript error demo client": (files["ts_route_client"], "errorDemo("),
        "typescript error demo constant": (files["ts_error_lookup"], "export const DemoErr = {"),
        "typescript error demo route lookup": (
            files["ts_error_lookup"],
            '"42901": ApiErrorsByID["DemoErr.RATE_LIMITED"],',
        ),
        "typescript stream union": (
            files["ts_route_types"],
            "export type SweepStreamMessage =\n"
            '  | { type: "state"; data: SweepState }\n'
            '  | { type: "progress"; data: SweepProgress }\n'
            '  | { type: "log"; data: SweepLog };',
        ),
        "typescript channel union": (
            files["ts_route_types"],
            "export type AssistantClientMessage =\n"
            '  | { type: "input"; data: AssistantInput }\n'
            '  | { type: "cancel"; data: AssistantCancel };',
        ),
        "typescript channel variants helper": (files["ts_route_types"], "export const AssistantClientMessageVariants = {"),
        "typescript server dispatcher helper": (files["ts_route_types"], "export function dispatchAssistantServerMessage<R>("),
        "typescript suite client message helper": (files["ts_suite"], "AssistantClientMessageVariants.cancel({ reason: \"suite\" })"),
        "typescript suite server dispatcher helper": (files["ts_suite"], "dispatchAssistantServerMessage(serverMessage, {"),
        "wails v3 bindings import": (
            files["ts_wails_v3_runtime"],
            'import { WAILS_V3_BINDINGS } from "./gen_bindings";',
        ),
        "wails v3 bindings manifest": (
            files["ts_wails_v3_bindings"],
            '"demo.DemoService.OpenAssistantSession": "example.com/project/golang/server/views/transports/wailsv3/api/demo.DemoService.OpenAssistantSession",',
        ),
        "index error demo route": (files["index"], '"id": "api.demo.get.errordemo"'),
        "index error demo url": (files["index"], '"url": "/api/demo/error-demo"'),
        "python binary public types export": (files["python_binary_route"], "from .gen_binary import *"),
        "python error demo constant": (files["python_error_lookup"], "class DemoErr:"),
        "python error demo route lookup": (files["python_error_lookup"], '42901: API_ERRORS_BY_ID["DemoErr.RATE_LIMITED"],'),
        "python client message variants": (
            files["python_client_demo_types"],
            "class AssistantClientMessageVariants:",
        ),
        "python client server dispatcher": (
            files["python_client_demo_types"],
            "def dispatch_assistant_server_message(",
        ),
        "python server client dispatcher": (
            files["python_server_demo_types"],
            "def dispatch_assistant_client_message(",
        ),
        "python typed dispatch error": (
            files["python_client_demo_types"],
            "class AssistantServerMessageDispatchError(Exception):",
        ),
        "kotlin client api json helper": (files["kotlin_client_api_json"], "public val ApiJson: Json = Json"),
        "kotlin channel bridge message types": (
            files["kotlin_client_route"],
            "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, ConnectionClose>",
        ),
        "kotlin client message variants": (
            files["kotlin_client_demo_types"],
            "public object AssistantClientMessageVariants",
        ),
        "kotlin client server dispatcher": (
            files["kotlin_client_demo_types"],
            "public fun <R> dispatchAssistantServerMessage(",
        ),
        "kotlin client sse transport": (files["kotlin_client_http"], "OkHttpEventStreamBridge"),
        "kotlin client websocket transport": (files["kotlin_client_http"], "WebSocketListener"),
        "kotlin server service": (files["kotlin_server_service"], "public interface GenDemoService"),
        "kotlin server client dispatcher": (
            files["kotlin_server_demo_types"],
            "public fun <R> dispatchAssistantClientMessage(",
        ),
        "kotlin server websocket adapter": (
            files["kotlin_server_ktor"],
            'webSocket("/api/demo/assistant-session")',
        ),
        "java api json helper": (files["java_client_api_json"], "public static final ObjectMapper MAPPER"),
        "java client message variants": (
            files["java_client_demo_types"],
            "public static final class AssistantClientMessageVariants",
        ),
        "java client server dispatcher": (
            files["java_client_demo_types"],
            "public static <R> R dispatchAssistantServerMessage(",
        ),
        "java client channel bridge message types": (
            files["java_client_route"],
            "GenApiChannelBridge<GenDemoTypes.AssistantServerMessage, GenDemoTypes.AssistantClientMessage, Object>",
        ),
        "java server operation marker": (
            files["java_server_demo_controller"],
            '@ApiBlueprintOperation("api.demo.get.abc")',
        ),
        "java server delegate": (
            files["java_server_demo_delegate"],
            "GenApiTypes.ApiDemoA abc(",
        ),
        "java server contract assertions": (
            files["java_server_contract_assertions"],
            "operation_marker_missing",
        ),
        "flutter runtime client route": (files["flutter_runtime_client"], "final demo = DemoApi(transport);"),
        "flutter error demo constant": (files["flutter_runtime_errors"], "const rateLimited = 42901;"),
        "flutter stream client": (files["flutter_demo_api"], "subscribeSweepEvents("),
        "flutter channel client": (files["flutter_demo_api"], "openAssistantSession("),
        "flutter channel bridge message types": (
            files["flutter_demo_api"],
            "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, ConnectionClose>",
        ),
        "flutter client message variants": (files["flutter_demo_types"], "class AssistantClientMessageVariants"),
        "flutter server dispatcher": (files["flutter_demo_types"], "R dispatchAssistantServerMessage<R>("),
        "flutter binary encode": (files["flutter_binary"], "Uint8List encodeDemoPacket(DemoPacket value)"),
        "flutter binary decode": (files["flutter_binary"], "DemoPacket decodeDemoPacket(Uint8List bytes)"),
        "flutter http transport": (files["flutter_http_transport"], "class HttpApiTransport implements ApiTransport"),
        "flutter websocket channel": (files["flutter_http_transport"], "WebSocketChannel.connect"),
    }
    validation_errors = []
    for label, (path, snippet) in checks.items():
        if snippet not in path.read_text(encoding="utf-8"):
            validation_errors.append(label)
    forbidden_checks = {
        "http stream explicit type args": (files["go_http_adapter"], "httptransport.STREAM["),
        "http channel explicit type args": (files["go_http_adapter"], "httptransport.CHANNEL["),
        "wails envelope explicit type args": (files["go_wails_v3_service"], "wailstransport.EnvelopeToReq["),
        "wails response envelope explicit type args": (
            files["go_wails_v3_service"],
            "WrapRSP_JSON_CodeMessageDataEnvelope[",
        ),
        "inline wails v3 bindings manifest": (files["ts_wails_v3_transport"], "const WAILS_V3_BINDINGS"),
        "generated stream scaffold": (
            files["go_route_gen_impl"],
            "serverMessage, err := NewSweepStreamMessageState(&serverData)",
        ),
        "generated channel scaffold": (files["go_route_gen_impl"], "clientMessage, err := channel.Recv(ctx)"),
        "generated router option": (files["go_route_gen_impl"], "type GenRouterOption func(router *_GenRouter)"),
        "generated flow option": (files["go_route_gen_impl"], "func WithAssistantSessionFlow("),
        "generated flow route": (files["go_route_gen_impl"], "return flow.Serve(ctx, channel)"),
        "generated stream sender": (files["go_route_impl"], "NewSweepEventsSender("),
        "manual assistant route in impl": (files["go_route_impl"], "func (impl *Router) AssistantSession("),
        "old channel dispatcher example": (files["go_route_impl"], "DispatchAssistantClientMessage("),
        "old generated channel dispatcher": (
            files["go_route_client_message"],
            "func DispatchAssistantClientMessage(",
        ),
        "old generated channel handlers": (
            files["go_route_client_message"],
            "type AssistantClientMessageHandlers struct {",
        ),
        "message union in gen_types": (files["go_route_types"], "type AssistantClientMessage struct {"),
        "user router flow field": (files["go_route_impl"], "assistantSessionFlow *AssistantSessionFlow"),
        "user router flow delegate": (files["go_route_impl"], "return flow.Serve(ctx, channel)"),
        "generated flow file": (
            workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_assistant_session_flow.go",
            "type AssistantSessionFlow struct {",
        ),
        "generated stream sender file": (
            workspace.golang_server_dir / "views" / "routes" / "api" / "demo" / "gen_sweep_events_stream.go",
            "type SweepEventsSender struct {",
        ),
        "old exported assistant processor": (files["go_route_assistant_processor"], "type AssistantSessionProcessor struct{}"),
        "old exported assistant scope": (files["go_route_assistant_processor"], "type AssistantSessionScope struct {"),
        "route-prefixed input processor": (files["go_route_assistant_processor"], "OnAssistantSessionInput"),
        "route-prefixed cancel processor": (files["go_route_assistant_processor"], "OnAssistantSessionCancel"),
    }
    for label, (path, snippet) in forbidden_checks.items():
        if path.is_file() and snippet in path.read_text(encoding="utf-8"):
            validation_errors.append(label)
    if validation_errors:
        raise ExampleValidationError(
            "blueprint connection example validation failed:\n" + "\n".join(validation_errors)
        )
