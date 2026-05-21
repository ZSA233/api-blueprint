from __future__ import annotations

from .helpers import *


def test_route_contract_assigns_stable_connection_service_and_event_names():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.CHANNEL("/chat").SERVER_MESSAGE(Payload).CLIENT_MESSAGE(Payload)
    contract = route_contract(router)

    assert contract.route_id == "api.demo.channel.chat"
    assert contract.service_name == "DemoService"
    assert contract.namespace == "demo"
    assert contract.channel is not None
    assert contract.channel.connect_method == "OpenChat"
    assert contract.channel.send_method == "SendChat"
    assert contract.channel.close_method == "CloseChat"
    assert contract.channel.event_base == "api_blueprint.channel.api.demo.channel.chat"

def test_typescript_http_generation_uses_stream_and_channel_bridges(tmp_path: Path):
    bp = Blueprint(root="/api")

    class ServerMessage(Model):
        value = String(description="value")

    class ClientMessage(Model):
        value = String(description="value")

    with bp.group("/demo") as views:
        views.GET("/ping").ARGS(q=String(description="q")).RSP(message=String(description="message"))
        views.CHANNEL("/chat").SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir, base_url="http://localhost:2333")
    writer.register(bp)
    writer.gen()

    http_transport = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")
    http_response = (output_dir / "api" / "transports" / "http" / "gen_response.ts").read_text(encoding="utf-8")
    http_connection = (output_dir / "api" / "transports" / "http" / "gen_connection.ts").read_text(encoding="utf-8")
    runtime_client = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    runtime_index = (output_dir / "api" / "runtime" / "gen_index.ts").read_text(encoding="utf-8")
    http_factory = (output_dir / "api" / "transports" / "http" / "api" / "gen_factory.ts").read_text(encoding="utf-8")
    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "export class DefaultTransport implements ApiTransport" in http_transport
    assert 'import { unwrapResponseEnvelope, extractApiErrorPayload, normalizeApiErrorPayload, tryParseJson } from "./gen_response";' in http_transport
    assert 'import { HttpEventStreamBridge, HttpSocketBridge } from "./gen_connection";' in http_transport
    assert "function unwrapResponseEnvelope" not in http_transport
    assert "class HttpEventStreamBridge" not in http_transport
    assert "export function unwrapResponseEnvelope" in http_response
    assert "export class HttpEventStreamBridge" in http_connection
    assert "export class HttpSocketBridge" in http_connection
    assert "protected connectRaw(options: ChannelConnectOptions<unknown, unknown, SocketCloseInfo>): WebSocket" in http_transport
    assert "export interface ApiClientConfig {\n  transport?: ApiTransport;\n}" in runtime_client
    assert "export interface ApiHttpTransportConfig extends ApiClientConfig" in http_transport
    assert "baseUrl?: string;" in http_transport
    assert "fetcher?: typeof fetch;" in http_transport
    assert not (output_dir / "api" / "runtime" / "gen_factory.ts").exists()
    assert 'demoClient: new DemoClientImpl(sharedConfig),' in http_factory
    assert 'new DefaultTransport(config, "http://localhost:2333")' in http_factory
    assert 'export * from "./factory";' not in runtime_index
    assert "http://localhost:2333" not in client_text
    assert "super(config);" in client_text
    assert "super(config," not in client_text
    assert "openChat(" in client_text
    assert "openChannel<Shared.ServerMessage, Shared.ClientMessage" in client_text
    assert "connectWsRaw(" not in client_text
    assert "legacy_ws" not in client_text

def test_typescript_generates_stream_and_channel_contracts(tmp_path: Path):
    bp = Blueprint(root="/api")

    class Open(Model):
        run_id = String(description="run id")

    class TaskState(Model):
        status = String(description="status")

    class TaskProgress(Model):
        value = String(description="value")

    class ClientInput(Model):
        text = String(description="text")

    class ClientCancel(Model):
        reason = String(description="reason")

    class CloseInfo(Model):
        reason = String(description="reason")

    with bp.group("/runs") as views:
        views.STREAM("/events").OPEN(Open).SERVER_MESSAGE(
            "TaskStreamMessage",
            state=TaskState,
            progress=TaskProgress,
        ).CLOSE(CloseInfo)
        views.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED).OPEN(Open).CLIENT_MESSAGE(ClientInput).SERVER_MESSAGE(TaskState).CLOSE(CloseInfo)
        views.CHANNEL("/assistant").OPEN(Open).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=ClientInput,
            cancel=ClientCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            state=TaskState,
        ).CLOSE(CloseInfo)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    runtime_client = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    models_text = (output_dir / "api" / "routes" / "api" / "runs" / "gen_types.ts").read_text(encoding="utf-8")
    client_text = (output_dir / "api" / "routes" / "api" / "runs" / "gen_client.ts").read_text(encoding="utf-8")
    transport_text = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")
    connection_text = (output_dir / "api" / "transports" / "http" / "gen_connection.ts").read_text(encoding="utf-8")

    assert "export interface ApiStreamBridge<Recv, Close = SocketCloseInfo>" in runtime_client
    assert "export interface ApiChannelBridge<Recv, Send, Close = SocketCloseInfo> extends ApiStreamBridge<Recv, Close>" in runtime_client
    assert 'delivery?: "ordered" | "unordered";' in runtime_client
    assert (
        "export type TaskStreamMessage =\n"
        '  | { type: "state"; data: TaskState }\n'
        '  | { type: "progress"; data: TaskProgress };'
        in models_text
    )
    assert "export const TaskStreamMessageVariants = {" in models_text
    assert "state(data: TaskState): TaskStreamMessage {" in models_text
    assert 'return { type: "state", data };' in models_text
    assert "export type TaskStreamMessageDispatchErrorKind = \"unknown_type\";" in models_text
    assert "export class TaskStreamMessageDispatchError extends Error {" in models_text
    assert "export function isTaskStreamMessageDispatchError(error: unknown): error is TaskStreamMessageDispatchError {" in models_text
    assert "export type TaskStreamMessageHandlers<R> = {" in models_text
    assert 'state: (data: TaskState, message: Extract<TaskStreamMessage, { type: "state" }>) => R;' in models_text
    assert "export function dispatchTaskStreamMessage<R>(" in models_text
    assert 'case "state": return handlers.state(message.data, message);' in models_text
    assert 'throw new TaskStreamMessageDispatchError("unknown_type", message);' in models_text
    assert (
        "export type AssistantClientMessage =\n"
        '  | { type: "input"; data: ClientInput }\n'
        '  | { type: "cancel"; data: ClientCancel };'
        in models_text
    )
    assert "export const AssistantClientMessageVariants = {" in models_text
    assert "input(data: ClientInput): AssistantClientMessage {" in models_text
    assert "export class AssistantClientMessageDispatchError extends Error {" in models_text
    assert "export function isAssistantClientMessageDispatchError(error: unknown): error is AssistantClientMessageDispatchError {" in models_text
    assert "export type AssistantClientMessageHandlers<R> = {" in models_text
    assert "export function dispatchAssistantClientMessage<R>(" in models_text
    assert "subscribeEvents(" in client_text
    assert "openChat(" in client_text
    assert "openAssistant(" in client_text
    assert "ApiStreamBridge<Types.TaskStreamMessage, Shared.CloseInfo>" in client_text
    assert "ApiChannelBridge<Shared.TaskState, Shared.ClientInput, Shared.CloseInfo>" in client_text
    assert "ApiChannelBridge<Types.AssistantServerMessage, Types.AssistantClientMessage, Shared.CloseInfo>" in client_text
    assert "openStream<Types.TaskStreamMessage, Shared.CloseInfo>" in client_text
    assert "openChannel<Shared.TaskState, Shared.ClientInput, Shared.CloseInfo>" in client_text
    assert "openChannel<Types.AssistantServerMessage, Types.AssistantClientMessage, Shared.CloseInfo>" in client_text
    assert 'connectionKind: "stream"' in client_text
    assert 'connectionKind: "channel"' in client_text
    assert 'scope: "session"' in client_text
    assert 'delivery: "ordered"' in client_text
    assert 'delivery: "unordered"' in client_text
    assert (
        "class HttpEventStreamBridge<Recv, Close = SocketCloseInfo> implements ApiStreamBridge<Recv, Close>"
        in connection_text
    )
    assert 'envelope.type === "close"' in connection_text
    assert "return new HttpEventStreamBridge(" in transport_text
    assert "return new HttpSocketBridge(" in transport_text

def test_typescript_channel_operation_id_changes_generated_method_name(tmp_path: Path):
    bp = Blueprint(root="/api")

    class Open(Model):
        device_id = String(description="device id")

    class ServerMessage(Model):
        text = String(description="text")

    class ClientMessage(Model):
        text = String(description="text")

    class CloseInfo(Model):
        reason = String(description="reason")

    with bp.group("/demo") as views:
        views.CHANNEL("/ws", operation_id="Realtime").OPEN(Open).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(
            ServerMessage
        ).CLOSE(CloseInfo)

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    client_text = (output_dir / "api" / "routes" / "api" / "demo" / "gen_client.ts").read_text(encoding="utf-8")
    assert "openRealtime(" in client_text
    assert 'routeId: "api.demo.channel.ws"' in client_text
    assert 'connectMethod: "OpenRealtime"' in client_text
    assert 'sendMethod: "SendRealtime"' in client_text
    assert 'closeMethod: "CloseRealtime"' in client_text
