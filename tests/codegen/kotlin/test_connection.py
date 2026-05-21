from __future__ import annotations

from .helpers import *


def test_kotlin_writer_generates_named_message_keyframe_helpers(tmp_path):
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

    class CloseInfo(Model):
        reason = String(description="reason")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        ).CLOSE(CloseInfo)
        views.STREAM("/single-events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantSingleMessage",
            delta=AssistantDelta,
        ).CLOSE(CloseInfo)
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=AssistantInput,
            cancel=AssistantCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        ).CLOSE(CloseInfo)
    bp.is_built = True

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    route_text = (root_dir / "routes" / "api" / "demo" / "GenDemoApi.kt").read_text(encoding="utf-8")
    types_text = (root_dir / "routes" / "api" / "demo" / "DemoTypes.kt").read_text(encoding="utf-8")
    runtime_text = (root_dir / "runtime" / "ApiJson.kt").read_text(encoding="utf-8")

    assert "@Serializable\npublic data class AssistantClientMessage(" in types_text
    assert "@Serializable\npublic data class AssistantSingleMessage(" in types_text
    assert "public val type: String," in types_text
    assert "public val data: JsonElement? = null" in types_text
    assert "public object AssistantClientMessageVariants" in types_text
    assert "public object AssistantSingleMessageVariants" in types_text
    assert "public fun cancel(data: AssistantCancel): AssistantClientMessage" in types_text
    assert "public interface AssistantServerMessageHandlers<R>" in types_text
    assert "public fun delta(data: AssistantDelta, message: AssistantServerMessage): R" in types_text
    assert "public class AssistantServerMessageDispatchException(" in types_text
    assert "public fun <R> dispatchAssistantServerMessage(" in types_text
    assert "ApiStreamBridge<AssistantServerMessage, CloseInfo>" in route_text
    assert "ApiStreamBridge<AssistantSingleMessage, CloseInfo>" in route_text
    assert "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, CloseInfo>" in route_text
    assert "public val ApiJson: Json = Json" in runtime_text
    assert "private val apiJson" not in runtime_text

def test_kotlin_server_writer_generates_service_ktor_adapter_and_message_keyframes(tmp_path):
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")

    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class AssistantInput(Model):
        text = String(description="text")

    class AssistantCancel(Model):
        reason = String(description="reason")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    class CloseInfo(Model):
        reason = String(description="reason")

    bp = Blueprint(root="/api", errors=[CommonErr])
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(SubmitResponse)
    views.POST("/submit").REQ(SubmitJson).RSP(SubmitResponse)
    views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
        "AssistantClientMessage",
        input=AssistantInput,
        cancel=AssistantCancel,
    ).SERVER_MESSAGE(
        "AssistantServerMessage",
        delta=AssistantDelta,
    ).CLOSE(CloseInfo)
    bp.is_built = True

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    route_dir = root_dir / "routes" / "api" / "demo"
    transport_dir = root_dir / "transports" / "ktor" / "api" / "demo"
    route_dir.mkdir(parents=True)
    (route_dir / "DemoService.kt").write_text("// USER SERVICE\n", encoding="utf-8")

    writer = KotlinServerWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    runtime_json_text = (root_dir / "runtime" / "ApiJson.kt").read_text(encoding="utf-8")
    service_text = (route_dir / "GenDemoService.kt").read_text(encoding="utf-8")
    stub_text = (route_dir / "DemoServiceStub.kt").read_text(encoding="utf-8")
    user_service_text = (route_dir / "DemoService.kt").read_text(encoding="utf-8")
    types_text = (route_dir / "DemoTypes.kt").read_text(encoding="utf-8")
    transport_text = (transport_dir / "GenDemoKtorRoutes.kt").read_text(encoding="utf-8")

    for generated_text in (runtime_json_text, service_text, stub_text, types_text, transport_text):
        assert generated_text.startswith(KOTLIN_SERVER_GENERATED_HEADER)
    assert user_service_text == "// USER SERVICE\n"

    assert "public interface GenDemoService" in service_text
    assert "public suspend fun ping(" in service_text
    assert "query: DemoPingQuery" in service_text
    assert "): SubmitResponse" in service_text
    assert "public suspend fun assistant(" in service_text
    assert "openData: OpenPayload" in service_text
    assert "channel: ApiServerChannel<AssistantClientMessage, AssistantServerMessage, CloseInfo>" in service_text
    assert "): Unit" in service_text
    assert "public open class DemoServiceStub : GenDemoService" in stub_text
    assert 'throw NotImplementedError("api.demo.get.ping is not implemented")' in stub_text

    assert "@Serializable\npublic data class AssistantClientMessage(" in types_text
    assert "public object AssistantClientMessageVariants" in types_text
    assert "public fun <R> dispatchAssistantClientMessage(" in types_text

    assert "public fun Route.registerDemoRoutes(" in transport_text
    assert "service: GenDemoService = DemoServiceStub()" in transport_text
    assert 'get("/api/demo/ping")' in transport_text
    assert "val query = try {" in transport_text
    assert "decodeParameters(call.request.queryParameters, DemoPingQuery.serializer())" in transport_text
    assert "respondBadRequest(call)" in transport_text
    assert "return@get" in transport_text
    assert "return@post" in transport_text
    assert "val result = service.ping(" in transport_text
    assert "respondSuccess(call, result, SubmitResponse.serializer()," in transport_text
    assert "public interface ApiServerStream<Message, Close>" in (
        root_dir / "runtime" / "ApiServerResponse.kt"
    ).read_text(encoding="utf-8")
    assert "public interface ApiServerChannel<Recv, Send, Close>" in (
        root_dir / "runtime" / "ApiServerResponse.kt"
    ).read_text(encoding="utf-8")
    assert 'webSocket("/api/demo/assistant")' in transport_text
    assert "val openData = decodeParameters(call.request.queryParameters, OpenPayload.serializer())" in transport_text
    assert "KtorWebSocketChannel(" in transport_text
    assert "service.assistant(" in transport_text
    assert "clientMessageSerializer = AssistantClientMessage.serializer()" in transport_text
    assert "serverMessageSerializer = AssistantServerMessage.serializer()" in transport_text
    assert "closeSerializer = CloseInfo.serializer()" in transport_text
    assert "import kotlinx.serialization.SerializationException" in transport_text
    assert "} catch (_: SerializationException) {" in transport_text
    assert 'abort(code = 1003, reason = "invalid WebSocket message")' in transport_text
    assert "} catch (_: IllegalArgumentException) {" in transport_text
    assert "HttpStatusCode.NotImplemented" not in transport_text
