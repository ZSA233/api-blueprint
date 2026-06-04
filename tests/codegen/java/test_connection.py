from __future__ import annotations

from .helpers import *


def test_java_client_and_server_generate_named_message_keyframe_helpers(tmp_path: Path) -> None:
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

    graph = build_contract_graph([bp])
    package_root = Path("com/example/generated/api")

    client_dir = tmp_path / "client"
    client_writer = JavaClientWriter(client_dir, package="com.example.generated", contract_graph=graph)
    client_writer.register(bp)
    client_writer.gen()
    client_route_dir = client_dir / package_root / "routes/api/demo"
    client_runtime_dir = client_dir / package_root / "runtime"
    client_types = (client_route_dir / "GenDemoTypes.java").read_text(encoding="utf-8")
    client_route = (client_route_dir / "GenDemoApi.java").read_text(encoding="utf-8")
    api_json = (client_runtime_dir / "GenApiJson.java").read_text(encoding="utf-8")

    assert "public record AssistantClientMessage(String type, JsonNode data)" in client_types
    assert "public record AssistantSingleMessage(String type, JsonNode data)" in client_types
    assert "public static final class AssistantClientMessageVariants" in client_types
    assert "public static final class AssistantSingleMessageVariants" in client_types
    assert "public static AssistantClientMessage cancel(GenApiTypes.AssistantCancel data)" in client_types
    assert "public interface AssistantServerMessageHandlers<R>" in client_types
    assert "R delta(GenApiTypes.AssistantDelta data, AssistantServerMessage message) throws Exception;" in client_types
    assert "public static final class AssistantServerMessageDispatchException extends RuntimeException" in client_types
    assert "public static <R> R dispatchAssistantServerMessage(" in client_types
    assert "GenApiStreamBridge<GenDemoTypes.AssistantServerMessage, Object>" in client_route
    assert "GenApiStreamBridge<GenDemoTypes.AssistantSingleMessage, Object>" in client_route
    assert "GenApiChannelBridge<GenDemoTypes.AssistantServerMessage, GenDemoTypes.AssistantClientMessage, Object>" in client_route
    assert "public final class GenApiJson" in api_json
    assert "public static final ObjectMapper MAPPER" in api_json

    server_dir = tmp_path / "server"
    server_writer = JavaServerWriter(server_dir, package="com.example.generated", contract_graph=graph)
    server_writer.register(bp)
    server_writer.gen()
    server_types = (server_dir / package_root / "types/api/demo/GenDemoTypes.java").read_text(encoding="utf-8")
    assistant_annotation = (server_dir / package_root / "annotations/api/demo/GenAssistant.java").read_text(
        encoding="utf-8"
    )
    spring_assertions = (server_dir / package_root / "spring/GenSpringMvcContractAssertions.java").read_text(
        encoding="utf-8"
    )

    assert "public static final class AssistantClientMessageVariants" in server_types
    assert "public static <R> R dispatchAssistantClientMessage(" in server_types
    assert "@RequestMapping(path = \"/api/demo/assistant\"" in assistant_annotation
    assert '@ApiBlueprintOperation("api.demo.channel.assistant")' in assistant_annotation
    assert '"api.demo.channel.assistant"' in spring_assertions
    assert '"com.example.generated.api.runtime.GenApiTypes.OpenPayload"' in spring_assertions
    assert "operation_marker_missing" in spring_assertions
