from __future__ import annotations

from .helpers import *


def test_java_selection_matches_path_tag_group_method_and_name(example_entrypoints) -> None:
    _config, entrypoints = example_entrypoints
    graph = build_contract_graph(entrypoints)
    route = next(route for route in graph.to_manifest()["routes"] if route["url"] == "/api/demo/abc")

    assert JavaRouteSelection(include=("path:/api/demo/*",)).includes(route)
    assert JavaRouteSelection(include=("tag:api",)).includes(route)
    assert JavaRouteSelection(include=("group:demo",)).includes(route)
    assert JavaRouteSelection(include=("method:GET",)).includes(route)
    assert JavaRouteSelection(include=("name:Abc",)).includes(route)
    assert not JavaRouteSelection(include=("tag:api",), exclude=("path:/api/demo/*",)).includes(route)

def test_java_client_and_server_generate_layout_and_preserve_user_files(tmp_path: Path) -> None:
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    class SubmitJson(Model):
        value = String(description="value")

    class FormPayload(Model):
        label = String(description="label")

    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class Event(Model):
        status = String(description="status")

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | 4 | | payload |
""".strip(),
        source_path="demo_packet.md",
    )

    bp = Blueprint(root="/api", errors=[CommonErr])
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(Result)
    views.POST("/submit").REQ(SubmitJson).RSP(Result)
    views.POST("/form").REQ_FORM(FormPayload).RSP(Result)
    views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(Event)
    views.CHANNEL("/chat").OPEN(OpenPayload).SERVER_MESSAGE(Event).CLIENT_MESSAGE(Event)
    with bp.group("/binary") as binary:
        binary.POST("/packet").REQ_BINARY(schema).RSP(Result)

    graph = build_contract_graph([bp])
    bp.is_built = True
    package_root = Path("com/example/generated/api")
    client_dir = tmp_path / "client"
    server_dir = tmp_path / "server"

    client_route_dir = client_dir / package_root / "routes/api/demo"
    client_runtime_dir = client_dir / package_root / "runtime"
    client_http_dir = client_dir / package_root / "transports/http"
    server_route_dir = server_dir / package_root / "routes/api/demo"
    for directory in (client_route_dir, client_runtime_dir, client_http_dir, server_route_dir):
        directory.mkdir(parents=True)
    (client_route_dir / "DemoApi.java").write_text("// USER ROUTE FACADE\n", encoding="utf-8")
    (client_runtime_dir / "ApiClient.java").write_text("// USER CLIENT FACADE\n", encoding="utf-8")
    (client_http_dir / "HttpApiClient.java").write_text("// USER HTTP FACADE\n", encoding="utf-8")
    (server_route_dir / "DemoService.java").write_text("// USER SERVICE\n", encoding="utf-8")

    client_writer = JavaClientWriter(
        client_dir,
        package="com.example.generated",
        base_url="http://localhost:2333",
        contract_graph=graph,
    )
    client_writer.register(bp)
    client_writer.gen()
    client_writer.gen()

    server_writer = JavaServerWriter(server_dir, package="com.example.generated", contract_graph=graph)
    server_writer.register(bp)
    server_writer.gen()
    server_writer.gen()

    runtime_text = (client_runtime_dir / "GenApiClient.java").read_text(encoding="utf-8")
    types_text = (client_runtime_dir / "GenApiTypes.java").read_text(encoding="utf-8")
    catalog_text = (client_runtime_dir / "GenApiErrors.java").read_text(encoding="utf-8")
    api_error_text = (client_runtime_dir / "GenApiError.java").read_text(encoding="utf-8")
    route_text = (client_route_dir / "GenDemoApi.java").read_text(encoding="utf-8")
    route_types_text = (client_route_dir / "GenDemoTypes.java").read_text(encoding="utf-8")
    transport_text = (client_http_dir / "GenJdkHttpApiTransport.java").read_text(encoding="utf-8")
    config_text = (client_http_dir / "GenHttpApiConfig.java").read_text(encoding="utf-8")
    binary_text = (client_dir / package_root / "routes/api/binary/GenBinaryTypes.java").read_text(encoding="utf-8")
    binary_service_text = (server_dir / package_root / "routes/api/binary/GenBinaryService.java").read_text(
        encoding="utf-8"
    )
    binary_controller_text = (
        server_dir / package_root / "transports/http/api/binary/GenBinaryController.java"
    ).read_text(encoding="utf-8")
    service_text = (server_route_dir / "GenDemoService.java").read_text(encoding="utf-8")
    service_stub_text = (server_route_dir / "GenDemoServiceStub.java").read_text(encoding="utf-8")
    controller_text = (
        server_dir / package_root / "transports/http/api/demo/GenDemoController.java"
    ).read_text(encoding="utf-8")

    for generated_text in (
        runtime_text,
        types_text,
        catalog_text,
        api_error_text,
        route_text,
        route_types_text,
        transport_text,
        config_text,
        binary_text,
    ):
        assert generated_text.startswith(JAVA_CLIENT_GENERATED_HEADER)
        assert _max_consecutive_blank_lines(generated_text) <= 1
    for generated_text in (
        service_text,
        controller_text,
    ):
        assert generated_text.startswith(JAVA_SERVER_GENERATED_HEADER)
        assert _max_consecutive_blank_lines(generated_text) <= 1
    assert (client_runtime_dir / "ApiClient.java").read_text(encoding="utf-8") == "// USER CLIENT FACADE\n"
    assert (client_route_dir / "DemoApi.java").read_text(encoding="utf-8") == "// USER ROUTE FACADE\n"
    assert (client_http_dir / "HttpApiClient.java").read_text(encoding="utf-8") == "// USER HTTP FACADE\n"
    assert (server_route_dir / "DemoService.java").read_text(encoding="utf-8") == "// USER SERVICE\n"

    assert "public record Result(" in types_text
    assert '@JsonProperty("status") String status' in types_text
    assert "public enum" not in route_types_text
    assert "public record PingQuery(" in route_types_text
    assert '@JsonProperty("q") String q' in route_types_text
    assert "public class GenApiClient" in runtime_text
    assert "public final DemoApi demo;" in runtime_text
    assert "public GenApiTypes.Result ping(" in route_text
    assert "GenDemoTypes.PingQuery query" in route_text
    assert "GenApiTypes.SubmitJson json" in route_text
    assert "GenApiTypes.FormPayload form" in route_text
    assert "GenBinaryTypes.DemoPacket binary" in (client_dir / package_root / "routes/api/binary/GenBinaryApi.java").read_text(
        encoding="utf-8"
    )
    assert "GenBinaryTypes.DemoPacketWire.toBinaryBody(binary)" in (
        client_dir / package_root / "routes/api/binary/GenBinaryApi.java"
    ).read_text(encoding="utf-8")
    assert "GenApiBinaryBody binaryBody" in (client_dir / package_root / "routes/api/binary/GenBinaryApi.java").read_text(
        encoding="utf-8"
    )
    assert "connectWs(" not in route_text
    assert "subscribeEvents(" in route_text
    assert "openChat(" in route_text
    assert "GenApiStreamBridge<GenApiTypes.Event, Object> subscribeEvents(" in route_text
    assert "GenApiChannelBridge<GenApiTypes.Event, GenApiTypes.Event, Object> openChat(" in route_text
    assert "GenDemoTypes.Event" not in route_text
    assert "public class GenJdkHttpApiTransport implements GenApiTransport" in transport_text
    assert "HttpClient.newHttpClient()" in transport_text
    assert "throw new GenApiError(payload" in transport_text
    assert "throw new GenApiException(response.statusCode(), body)" in transport_text
    assert "parseApiErrorPayload(nested, routeId, false)" in transport_text
    assert "parseApiErrorPayload(JsonNode node, String routeId, boolean synthesizeFallbackMessage)" in transport_text
    assert "UnsupportedOperationException" in (client_runtime_dir / "GenApiTransport.java").read_text(encoding="utf-8")
    assert 'this("http://localhost:2333");' in config_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "COMMONERR_TOKEN_EXPIRE" in catalog_text
    assert "public final class GenApiErrors" in catalog_text
    assert "ROUTE_API_ERRORS_BY_CODE" in catalog_text
    assert '"登录状态已失效，请重新登录"' in catalog_text
    assert "public class GenApiError extends RuntimeException" in api_error_text
    assert "\\u767b" not in catalog_text
    assert "public final class GenBinaryTypes" in binary_text
    assert "public record DemoPacket(GenApiBinaryBody body)" not in binary_text
    assert "public record DemoPacket(" in binary_text
    assert "DemoPacketBody body" in binary_text
    assert "public record DemoPacketBody(" in binary_text
    assert "byte[] payload" in binary_text
    assert "public static GenApiBinaryBody toBinaryBody(DemoPacket value)" in binary_text
    assert "public static DemoPacket parse(byte[] bytes)" in binary_text
    assert "GenBinaryTypes.DemoPacket binary" in binary_service_text
    assert "GenBinaryTypes.DemoPacket binary;" in binary_controller_text
    assert "binary = GenBinaryTypes.DemoPacketWire.parse(binaryBody == null ? new byte[0] : binaryBody);" in binary_controller_text
    assert "return badRequestResponse(error);" in binary_controller_text
    assert "public static final String CONTENT_TYPE = \"application/octet-stream\"" in binary_text

    assert "public interface GenDemoService" in service_text
    assert "GenApiTypes.Result ping(" in service_text
    assert "Object ws(" not in service_text
    assert "void events(" in service_text
    assert "GenApiServerStream<GenApiTypes.Event, Object> stream" in service_text
    assert "void chat(" in service_text
    assert "GenApiServerChannel<GenApiTypes.Event, GenApiTypes.Event, Object> channel" in service_text
    assert "public void events(\n        GenApiTypes.OpenPayload openData,\n        GenApiServerStream<GenApiTypes.Event, Object> stream\n    ) throws Exception" in service_stub_text
    assert "public void chat(\n        GenApiTypes.OpenPayload openData,\n        GenApiServerChannel<GenApiTypes.Event, GenApiTypes.Event, Object> channel\n    ) throws Exception" in service_stub_text
    assert "@RestController" in controller_text
    assert "@RequestMapping(path = \"/api/demo/ping\", method = RequestMethod.GET)" in controller_text
    assert "SseEmitter" in controller_text
    assert "implements WebSocketConfigurer" in controller_text
    assert "registry.addHandler(new ChatWebSocketHandler(), \"/api/demo/chat\")" in controller_text
    assert "SpringSseStream" in controller_text
    assert "SpringWebSocketChannel" in controller_text
    assert "private static final Object CLOSED = new Object();" in controller_text
    assert "private final BlockingQueue<Object> incoming = new LinkedBlockingQueue<>();" in controller_text
    assert "void markClosed(Exception error)" in controller_text
    assert "channel.markClosed" in controller_text
    assert "channel.abortUnchecked(1003, \"invalid WebSocket message\")" in controller_text
    assert "incoming.take()" in controller_text
    assert "return badRequestResponse(error);" in controller_text
    assert "private ResponseEntity<Map<String, Object>> badRequestResponse(Exception error)" in controller_text
    assert "ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED)" not in controller_text

def test_java_writer_name_filter_uses_resolved_operation_name(tmp_path: Path) -> None:
    bp = Blueprint(root="/api")
    with bp.group("/settings") as views:
        views.GET("/current").RSP(Result)
        views.PUT("/current").RSP(Result)

    writer = JavaClientWriter(
        tmp_path / "java",
        package="com.example.generated",
        include=("name:CurrentGet",),
    )
    writer.register(bp)
    writer.gen()

    route_text = (
        tmp_path
        / "java"
        / "com"
        / "example"
        / "generated"
        / "api"
        / "routes"
        / "api"
        / "settings"
        / "GenSettingsApi.java"
    ).read_text(encoding="utf-8")
    assert "currentGet(" in route_text
    assert "currentPut(" not in route_text
