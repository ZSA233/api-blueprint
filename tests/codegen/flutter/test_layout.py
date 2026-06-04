from __future__ import annotations

from .helpers import *
from api_blueprint.engine.model import OneOf, LegacyStringID


def _flutter_format_violations(output_dir: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(output_dir.rglob("*.dart")):
        relative_path = path.relative_to(output_dir).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.rstrip(" \t") != line:
                violations.append(f"{relative_path}:{line_number}: trailing whitespace")
        if text.endswith("\n\n"):
            violations.append(f"{relative_path}: trailing blank line at EOF")
        blank_run = 0
        max_blank_run = 0
        for line in text.splitlines():
            if line.strip():
                blank_run = 0
            else:
                blank_run += 1
                max_blank_run = max(max_blank_run, blank_run)
        if max_blank_run >= 3:
            violations.append(f"{relative_path}: {max_blank_run} consecutive blank lines")
    return violations


def test_flutter_writer_generates_dart_package_runtime_routes_transport_and_preserved_files(tmp_path: Path) -> None:
    class CommonErr(Model):
        TOKEN_EXPIRE = Error(
            55555,
            "token expired",
            toast=Toast(
                key="auth.token_expire",
                default="Token expired",
                level="warning",
            ),
        )

    bp = Blueprint(root="/api", errors=[CommonErr])
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(SubmitResponse)
    views.POST("/submit").REQ(SubmitJson).RSP(SubmitResponse)
    views.DELETE("/raw").RSP_XML(String(description="raw"))
    views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
        "AssistantServerMessage",
        delta=AssistantDelta,
    ).CLOSE(CloseInfo)
    views.CHANNEL("/assistant", delivery=ConnectionDelivery.UNORDERED).OPEN(OpenPayload).CLIENT_MESSAGE(
        "AssistantClientMessage",
        input=AssistantInput,
        cancel=AssistantCancel,
    ).SERVER_MESSAGE(
        "AssistantServerMessage",
        delta=AssistantDelta,
    ).CLOSE(CloseInfo)

    out_dir = tmp_path / "flutter"
    route_dir = out_dir / "lib" / "src" / "api" / "routes" / "api" / "demo"
    runtime_dir = out_dir / "lib" / "src" / "api" / "runtime"
    http_dir = out_dir / "lib" / "src" / "api" / "transports" / "http"
    route_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    http_dir.mkdir(parents=True)
    (route_dir / "demo_api.dart").write_text("// USER ROUTE FACADE\n", encoding="utf-8")
    (runtime_dir / "api_client.dart").write_text("// USER CLIENT FACADE\n", encoding="utf-8")
    (runtime_dir / "api_json_codecs.dart").write_text("// USER CODECS\n", encoding="utf-8")
    (http_dir / "http_api_client.dart").write_text("// USER HTTP FACADE\n", encoding="utf-8")

    writer = FlutterWriter(out_dir, package="api_blueprint_example", base_url="http://localhost:2333")
    writer.register(bp)
    writer.gen()

    public_entry = (out_dir / "lib" / "api_blueprint_example.dart").read_text(encoding="utf-8")
    generated_public_entry = (out_dir / "lib" / "gen_api_blueprint_example.dart").read_text(encoding="utf-8")
    root_entry = (out_dir / "lib" / "api.dart").read_text(encoding="utf-8")
    generated_root_entry = (out_dir / "lib" / "gen_api.dart").read_text(encoding="utf-8")
    root_facade = (out_dir / "lib" / "src" / "api" / "api.dart").read_text(encoding="utf-8")
    root_barrel = (out_dir / "lib" / "src" / "api" / "gen_api.dart").read_text(encoding="utf-8")
    runtime_transport = (runtime_dir / "gen_api_transport.dart").read_text(encoding="utf-8")
    runtime_client = (runtime_dir / "gen_api_client.dart").read_text(encoding="utf-8")
    runtime_errors = (runtime_dir / "gen_api_errors.dart").read_text(encoding="utf-8")
    runtime_error_lookup = (runtime_dir / "gen_api_error_lookup.dart").read_text(encoding="utf-8")
    runtime_types = (runtime_dir / "gen_api_types.dart").read_text(encoding="utf-8")
    route_client = (route_dir / "gen_demo_api.dart").read_text(encoding="utf-8")
    route_types = (route_dir / "gen_demo_types.dart").read_text(encoding="utf-8")
    http_config = (http_dir / "gen_http_api_config.dart").read_text(encoding="utf-8")
    http_transport = (http_dir / "gen_http_api_transport.dart").read_text(encoding="utf-8")
    http_connection = (http_dir / "gen_http_connection.dart").read_text(encoding="utf-8")

    for generated_text in (
        generated_public_entry,
        generated_root_entry,
        root_barrel,
        runtime_transport,
        runtime_client,
        runtime_errors,
        runtime_error_lookup,
        runtime_types,
        route_client,
        route_types,
        http_config,
        http_transport,
        http_connection,
    ):
        assert generated_text.startswith(FLUTTER_CLIENT_GENERATED_HEADER)

    assert _flutter_format_violations(out_dir) == []

    assert (out_dir / "pubspec.yaml").is_file()
    assert not public_entry.startswith(FLUTTER_CLIENT_GENERATED_HEADER)
    assert not root_entry.startswith(FLUTTER_CLIENT_GENERATED_HEADER)
    assert not root_facade.startswith(FLUTTER_CLIENT_GENERATED_HEADER)
    assert "export 'gen_api_blueprint_example.dart';" in public_entry
    assert "export 'gen_api.dart';" in generated_public_entry
    assert "export 'gen_api.dart';" in root_entry
    assert "export 'src/api/gen_api.dart';" in generated_root_entry
    assert "export 'gen_api.dart';" in root_facade
    assert (runtime_dir / "api_client.dart").read_text(encoding="utf-8") == "// USER CLIENT FACADE\n"


    assert (runtime_dir / "api_json_codecs.dart").read_text(encoding="utf-8") == "// USER CODECS\n"
    assert (route_dir / "demo_api.dart").read_text(encoding="utf-8") == "// USER ROUTE FACADE\n"
    assert (http_dir / "http_api_client.dart").read_text(encoding="utf-8") == "// USER HTTP FACADE\n"

    assert "abstract interface class ApiTransport" in runtime_transport
    assert "class ApiRequestOptions" in runtime_transport
    assert "final Duration? timeout;" in runtime_transport
    assert "final ApiRequestOptions options;" in runtime_transport
    assert "abstract interface class ApiStreamBridge<Recv, Close>" in runtime_transport
    assert "abstract interface class ApiChannelBridge<Recv, Send, Close>" in runtime_transport
    assert "class ApiError implements Exception" in runtime_errors
    assert "ApiToastSpec resolveApiToast(" in runtime_errors
    assert "const tokenExpire = 55555;" in runtime_error_lookup
    assert "final demo = DemoApi(transport);" in runtime_client
    assert "enum StatusEnum" in runtime_types
    assert "enum KeywordEnum" in runtime_types
    assert 'default_("default")' in runtime_types

    assert "class GenDemoApi" in route_client
    assert "Future<SubmitResponse> ping(" in route_client
    assert "Future<SubmitResponse> submit(" in route_client
    assert "ApiRequestOptions options = const ApiRequestOptions()" in route_client
    assert "options: options," in route_client
    assert "Map<String, String> headers = const {},\n  }) {\n    return transport.request" not in route_client
    assert "Future<String> raw(" in route_client
    assert "responseMediaType: \"application/xml\"" in route_client
    assert "ApiStreamBridge<AssistantServerMessage, CloseInfo> subscribeEvents(" in route_client
    assert (
        "ApiChannelBridge<AssistantServerMessage, AssistantClientMessage, CloseInfo> openAssistant(" in route_client
    )
    assert 'path: "/api/demo/submit"' in route_client
    assert 'connectionKind: "channel"' in route_client
    assert 'delivery: "unordered"' in route_client

    assert "class SubmitJson" in runtime_types
    assert "factory SubmitJson.fromJson(Map<String, Object?> json)" in runtime_types
    assert "final codec = apiJsonCodecs.find<SubmitJson>();" in runtime_types
    assert "Map<String, Object?> toJson()" in runtime_types
    assert "sealed class AssistantClientMessage" in route_types
    assert "final class AssistantClientMessageInput extends AssistantClientMessage" in route_types
    assert "AssistantClientMessage input(AssistantInput data)" in route_types
    assert "R dispatchAssistantServerMessage<R>(" in route_types

    assert 'baseUrl = "http://localhost:2333"' in http_config
    assert "import 'package:http/http.dart' as http;" in http_transport
    assert "...request.options.headers" in http_transport
    assert "final timeout = request.options.timeout ?? config.timeout;" in http_transport
    assert "await send().timeout(timeout)" in http_transport
    assert "application/x-www-form-urlencoded" in http_transport
    assert "String _encodeFormBody(Object? form)" in http_transport
    assert "WebSocketChannel.connect" in http_transport
    assert "text/event-stream" in http_transport
    assert "class HttpEventStreamBridge" in http_connection
    assert "class HttpSocketBridge" in http_connection
    assert "for (final listener in List.of(_messages))" in http_connection
    assert "for (final listener in List.of(_closes))" in http_connection
    assert "var _didClose = false;" in http_connection
    assert "throw ApiException(response.statusCode, body);" in http_connection
    assert "RegExp(r'\\r?\\n\\r?\\n')" in http_connection
    assert "late final Future<void> ready = socket.ready;" in http_connection


def test_flutter_generates_legacy_json_compat_field_types(tmp_path: Path) -> None:
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        normalized = Array[LegacyStringID](description="normalized")
        room_id = LegacyStringID(alias="roomId", description="room id")

    bp = Blueprint(root="/api")
    with bp.group("/legacy") as views:
        views.GET("/payload").RSP(LegacyPayload)

    out_dir = tmp_path / "flutter"
    writer = FlutterWriter(out_dir, package="api_blueprint_example")
    writer.register(bp)
    writer.gen()

    runtime_types = (out_dir / "lib" / "src" / "api" / "runtime" / "gen_api_types.dart").read_text(
        encoding="utf-8"
    )
    runtime_errors = (out_dir / "lib" / "src" / "api" / "runtime" / "gen_api_errors.dart").read_text(
        encoding="utf-8"
    )
    assert "final Object? target;" in runtime_types
    assert "final List<String>? normalized;" in runtime_types
    assert "final String? roomId;" in runtime_types
    assert "apiBlueprintReadCoerceString" in runtime_types
    assert "String? apiBlueprintReadCoerceString(Object? value)" in runtime_errors


def test_flutter_generated_entry_templates_use_generated_names() -> None:
    template_dir = Path(__file__).resolve().parents[3] / "src" / "api_blueprint" / "writer" / "templates" / "flutter"

    assert (template_dir / "gen_public_entry.dart.j2").is_file()
    assert (template_dir / "gen_root_public_entry.dart.j2").is_file()
    assert (template_dir / "gen_root_barrel.dart.j2").is_file()
    assert not (template_dir / "root_barrel.dart.j2").exists()
    assert "Code generated by api-blueprint" not in (template_dir / "public_entry.dart.j2").read_text(encoding="utf-8")
    assert "Code generated by api-blueprint" not in (template_dir / "root_public_entry.dart.j2").read_text(encoding="utf-8")

def test_flutter_writer_exports_multiple_roots(tmp_path: Path) -> None:
    class Result(Model):
        ok = String(description="ok")

    api_bp = Blueprint(root="/api")
    api_bp.GET("/ping").RSP(Result)
    static_bp = Blueprint(root="/static")
    static_bp.GET("/doc").RSP(Result)

    out_dir = tmp_path / "flutter"
    writer = FlutterWriter(out_dir, package="api_blueprint_example")
    writer.register(api_bp)
    writer.register(static_bp)
    writer.gen()

    public_entry = (out_dir / "lib" / "api_blueprint_example.dart").read_text(encoding="utf-8")
    generated_public_entry = (out_dir / "lib" / "gen_api_blueprint_example.dart").read_text(encoding="utf-8")
    api_entry = (out_dir / "lib" / "api.dart").read_text(encoding="utf-8")
    generated_api_entry = (out_dir / "lib" / "gen_api.dart").read_text(encoding="utf-8")
    static_entry = (out_dir / "lib" / "static_.dart").read_text(encoding="utf-8")
    generated_static_entry = (out_dir / "lib" / "gen_static_.dart").read_text(encoding="utf-8")

    assert "export 'gen_api_blueprint_example.dart';" in public_entry
    assert "export 'gen_static_.dart';" not in public_entry
    assert "export 'gen_api.dart';" in generated_public_entry
    assert "export 'gen_api.dart';" in api_entry
    assert "export 'src/api/gen_api.dart';" in generated_api_entry
    assert "export 'gen_static_.dart';" in static_entry
    assert "export 'src/static_/gen_static_.dart';" in generated_static_entry
