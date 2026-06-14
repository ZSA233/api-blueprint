from __future__ import annotations

from .helpers import *


def test_python_server_generates_connection_adapter_scaffolds(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(Event).SERVER_MESSAGE(Event)

    output_dir = tmp_path / "python"
    writer = PythonServerWriter(output_dir)
    writer.register(bp)
    writer.gen()

    adapter_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py"
    ).read_text(encoding="utf-8")

    assert "from fastapi import APIRouter, WebSocket" in adapter_text
    assert "from starlette.responses import StreamingResponse" in adapter_text
    assert "@router.api_route(\"/api/demo/events\", methods=[\"GET\"])" in adapter_text
    assert "@router.websocket(\"/api/demo/chat\")" in adapter_text
    assert "stream = _SseStream(api_config.sse_queue_capacity)" in adapter_text
    assert "async for chunk in stream:" in adapter_text
    assert "channel = _WebSocketChannel(websocket, api_demo_types.Event.from_value, api_config)" in adapter_text
    assert "except _WebSocketClosed:" in adapter_text
    assert "except (UnicodeDecodeError, json.JSONDecodeError) as err:" in adapter_text
    assert 'await self.abort(1003, "invalid WebSocket message")' in adapter_text
    assert "await service.chat(" in adapter_text
    assert "media_type=\"text/event-stream\"" in adapter_text
    service_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_service.py"
    ).read_text(encoding="utf-8")
    assert "stream: ApiServerStream[Event, EventsClose] | None = None" in service_text
    assert "channel: ApiServerChannel[Event, Event, ChatClose] | None = None" in service_text
    _compile_generated_files(output_dir)

def test_python_client_generates_connection_bridge_methods(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class Event(Model):
        value = String(description="value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(Event)
        views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(Event).SERVER_MESSAGE(Event)

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_text = (
        output_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_client.py"
    ).read_text(encoding="utf-8")
    runtime_text = (output_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_client.py").read_text(
        encoding="utf-8"
    )
    transport_text = (
        output_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py"
    ).read_text(encoding="utf-8")

    assert "class ApiSocketBridge(Protocol" not in runtime_text
    assert "def connect_socket(" not in runtime_text
    assert "def open_stream(" in runtime_text
    assert "def open_channel(" in runtime_text
    assert "def connect_ws(" not in route_text
    assert "return self._transport.connect_socket(" not in route_text
    assert "def subscribe_events(" in route_text
    assert "return self._transport.open_stream(" in route_text
    assert "def open_chat(" in route_text
    assert "return self._transport.open_channel(" in route_text
    assert "raise NotImplementedError" in transport_text
    assert "default httpx adapter" in transport_text
    _compile_generated_files(output_dir)

def test_python_client_and_server_generate_named_message_helpers(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class AssistantInput(Model):
        text = String(description="text")

    class AssistantCancel(Model):
        reason = String(description="reason")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    class AssistantDone(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )
        views.STREAM("/single-events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantSingleMessage",
            delta=AssistantDelta,
        )
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=AssistantInput,
            cancel=AssistantCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    client_types = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_types.py"
    ).read_text(encoding="utf-8")
    client_public = (
        client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "client.py"
    ).read_text(encoding="utf-8")

    assert "@dataclass(kw_only=True)\nclass AssistantClientMessage:" in client_types
    assert "data: Any = None" in client_types
    assert "@dataclass(kw_only=True)\nclass AssistantSingleMessage:" in client_types
    assert "class AssistantSingleMessageVariants:" in client_types
    assert "class AssistantClientMessageVariants:" in client_types
    assert "def cancel(data: AssistantCancel) -> AssistantClientMessage:" in client_types
    assert "@dataclass(kw_only=True)\nclass AssistantServerMessageHandlers(Generic[R]):" in client_types
    assert "class AssistantServerMessageProcessor(Protocol[C]):" in client_types
    assert 'def on_delta(self, ctx: C, msg: "AssistantServerMessageDeltaCase") -> None:' in client_types
    assert "class AssistantServerMessageCase(Protocol):" in client_types
    assert "@dataclass\nclass AssistantServerMessageDeltaCase:" in client_types
    assert "def decode(self) -> AssistantDelta:" in client_types
    assert "data = AssistantDelta.from_value(self._message.data" in client_types
    assert "def visit_assistant_server_message(" in client_types
    assert 'raise AssistantServerMessageDispatchError("nil_processor", typed_message)' in client_types
    assert 'raise AssistantServerMessageDispatchError("handler_failed", typed_message, err) from err' in client_types
    assert "def dispatch_assistant_server_message(" in client_types
    assert "class AssistantServerMessageDispatchError(Exception):" in client_types
    assert "kind: str = \"unknown_type\"" in client_types
    assert "from .gen_types import *" in client_public
    assert "Preserved channel processor scaffolds" in client_public
    assert "class AssistantChannelSession:" in client_public
    assert "bridge: ApiChannelBridge[AssistantServerMessage, AssistantClientMessage, AssistantClose]" in client_public
    assert "async def serve(self) -> None:" in client_public
    assert "visit_assistant_server_message(self.context, message, self.processor)" in client_public

    types_module = _import_generated_module(
        client_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_types",
    )

    class DeltaProcessor:
        def __init__(self):
            self.context = None
            self.chunk = ""

        def on_delta(self, ctx, msg):
            self.context = ctx
            self.chunk = msg.decode().chunk

        def on_done(self, ctx, msg):
            raise AssertionError("unexpected done message")

    processor = DeltaProcessor()
    typed_message = types_module.AssistantServerMessageVariants.delta(types_module.AssistantDelta(chunk="hello"))
    types_module.visit_assistant_server_message({"trace_id": "demo"}, typed_message, processor)
    assert processor.context == {"trace_id": "demo"}
    assert processor.chunk == "hello"

    with pytest.raises(types_module.AssistantServerMessageDispatchError) as error_info:
        types_module.visit_assistant_server_message(None, typed_message, None)
    assert error_info.value.kind == "nil_processor"

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    server_types = (
        server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "gen_types.py"
    ).read_text(encoding="utf-8")
    server_public = (
        server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "demo" / "service.py"
    ).read_text(encoding="utf-8")

    assert "class AssistantClientMessageVariants:" in server_types
    assert "class AssistantClientMessageProcessor(Protocol[C]):" in server_types
    assert 'def on_input(self, ctx: C, msg: "AssistantClientMessageInputCase") -> None:' in server_types
    assert "def visit_assistant_client_message(" in server_types
    assert "def dispatch_assistant_single_message(" in server_types
    assert "def dispatch_assistant_client_message(" in server_types
    assert "class AssistantClientMessageDispatchError(Exception):" in server_types
    assert "from .gen_types import *" in server_public
    _compile_generated_files(tmp_path)


def test_python_client_channel_adapter_hook_passes_typed_messages_to_custom_transport(tmp_path: Path):
    class OpenPayload(Model):
        value = String(description="value")

    class LookupRequest(Model):
        key = String(description="lookup key")

    class LookupResult(Model):
        value = String(description="lookup value")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.CHANNEL("/lookup").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            lookup=LookupRequest,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            found=LookupResult,
        )

    output_dir = tmp_path / "python"
    writer = PythonClientWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_module = _import_generated_module(
        output_dir,
        "api_blueprint_generated.api.routes.api.demo.gen_client",
    )
    types_module = importlib.import_module("api_blueprint_generated.api.routes.api.demo.gen_types")

    class DemoChannelBridge:
        def __init__(self):
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def send(self, message):
            self.sent.append(message)

        async def close(self):
            return None

    class DemoChannelTransport:
        def __init__(self):
            self.bridge = DemoChannelBridge()
            self.channel_request = None

        async def request(self, request):
            raise AssertionError("CHANNEL should use open_channel")

        def open_stream(self, **kwargs):
            raise AssertionError("CHANNEL should use open_channel")

        def open_channel(self, **kwargs):
            self.channel_request = dict(kwargs)
            return self.bridge

    transport = DemoChannelTransport()
    client = route_module.DemoClient(transport)
    bridge = client.open_lookup(types_module.LookupOpen(value="demo"))

    message = types_module.AssistantClientMessageVariants.lookup(types_module.LookupRequest(key="alpha"))
    asyncio.run(bridge.send(message))

    class LookupProcessor:
        def __init__(self):
            self.context = None
            self.key = ""

        def on_lookup(self, ctx, msg):
            self.context = ctx
            self.key = msg.decode().key

    processor = LookupProcessor()
    types_module.visit_assistant_client_message({"transport": "demo"}, transport.bridge.sent[0], processor)

    assert transport.channel_request == {
        "route_id": "api.demo.channel.lookup",
        "path": "/api/demo/lookup",
        "open_data": {"value": "demo"},
        "headers": None,
        "protocols": (),
    }
    assert transport.bridge.sent[0].to_mapping() == {"type": "lookup", "data": {"key": "alpha"}}
    assert processor.context == {"transport": "demo"}
    assert processor.key == "alpha"
    _compile_generated_files(output_dir)
