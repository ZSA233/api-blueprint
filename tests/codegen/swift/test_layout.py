from __future__ import annotations

from .helpers import *


def test_swift_writer_generates_spm_runtime_routes_transport_and_preserved_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"
    source_dir = out_dir / "Sources" / "ApiBlueprintExampleClient"
    api_dir = source_dir / "API"
    route_dir = api_dir / "Routes" / "API" / "Demo"
    runtime_dir = api_dir / "Runtime"
    http_dir = api_dir / "Transports" / "HTTP"
    route_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    http_dir.mkdir(parents=True)
    (out_dir / "Package.swift").write_text("// USER PACKAGE\n", encoding="utf-8")
    (source_dir / "ApiBlueprintExampleClient.swift").write_text("// USER PACKAGE FACADE\n", encoding="utf-8")
    (api_dir / "APIRootClient.swift").write_text("// USER ROOT FACADE\n", encoding="utf-8")
    (runtime_dir / "APICoding.swift").write_text("// USER CODING\n", encoding="utf-8")
    (route_dir / "DemoAPI.swift").write_text("// USER ROUTE FACADE\n", encoding="utf-8")
    (route_dir / "DemoTypes.swift").write_text("// USER TYPES FACADE\n", encoding="utf-8")
    (http_dir / "HTTPAPIClient.swift").write_text("// USER HTTP FACADE\n", encoding="utf-8")

    write_demo_swift_package(out_dir)

    generated_package_facade = (source_dir / "GenApiBlueprintExampleClient.swift").read_text(encoding="utf-8")
    generated_root = (api_dir / "GenAPIRootClient.swift").read_text(encoding="utf-8")
    runtime_transport = (runtime_dir / "GenAPITransport.swift").read_text(encoding="utf-8")
    runtime_errors = (runtime_dir / "GenAPIErrors.swift").read_text(encoding="utf-8")
    runtime_error_lookup = (runtime_dir / "GenAPIErrorLookup.swift").read_text(encoding="utf-8")
    runtime_types = (runtime_dir / "GenAPITypes.swift").read_text(encoding="utf-8")
    binary_runtime = (runtime_dir / "Binary" / "GenBinaryRuntime.swift").read_text(encoding="utf-8")
    route_client = (route_dir / "GenDemoAPI.swift").read_text(encoding="utf-8")
    route_types = (route_dir / "GenDemoTypes.swift").read_text(encoding="utf-8")
    route_binary = (route_dir / "GenBinary.swift").read_text(encoding="utf-8")
    http_config = (http_dir / "GenHTTPAPIConfig.swift").read_text(encoding="utf-8")
    http_transport = (http_dir / "GenURLSessionAPITransport.swift").read_text(encoding="utf-8")
    http_connection = (http_dir / "GenHTTPConnection.swift").read_text(encoding="utf-8")

    for generated_text in (
        generated_package_facade,
        generated_root,
        runtime_transport,
        runtime_errors,
        runtime_error_lookup,
        runtime_types,
        binary_runtime,
        route_client,
        route_types,
        route_binary,
        http_config,
        http_transport,
        http_connection,
    ):
        assert generated_text.startswith(SWIFT_CLIENT_GENERATED_HEADER)

    assert (out_dir / "Package.swift").read_text(encoding="utf-8") == "// USER PACKAGE\n"
    assert (source_dir / "ApiBlueprintExampleClient.swift").read_text(encoding="utf-8") == "// USER PACKAGE FACADE\n"
    assert (api_dir / "APIRootClient.swift").read_text(encoding="utf-8") == "// USER ROOT FACADE\n"
    assert (runtime_dir / "APICoding.swift").read_text(encoding="utf-8") == "// USER CODING\n"
    assert (route_dir / "DemoAPI.swift").read_text(encoding="utf-8") == "// USER ROUTE FACADE\n"
    assert (route_dir / "DemoTypes.swift").read_text(encoding="utf-8") == "// USER TYPES FACADE\n"
    assert (http_dir / "HTTPAPIClient.swift").read_text(encoding="utf-8") == "// USER HTTP FACADE\n"

    assert "open class GenApiBlueprintExampleClient" in generated_package_facade
    assert "public lazy var api = APIRootClient(transport: transport)" in generated_package_facade
    assert "open class GenAPIRootClient" in generated_root
    assert "public lazy var demo = DemoAPI(transport: transport)" in generated_root

    assert "public protocol APITransport" in runtime_transport
    assert "func request<Response>(_ request: APIRequest<Response>) async throws -> Response" in runtime_transport
    assert "func openStream<Recv, Close>" in runtime_transport
    assert "func openChannel<Recv, Send, Close>" in runtime_transport
    assert "public struct APIRequestOptions" in runtime_transport
    assert "public struct APIRequest<Response>" in runtime_transport
    assert "public struct APIRawResponse" in runtime_transport
    assert "public struct APIStreamResponse" in runtime_transport
    assert "public struct APIFilePart: Codable, Sendable" in runtime_transport
    assert "public struct APIBinaryPayload: Sendable" in runtime_transport
    assert "public enum APIJSONValue" in runtime_transport
    assert "public struct APIErrorPayload" in runtime_errors
    assert "public struct APIError: Error" in runtime_errors
    assert "public enum APIErrorCodes" in runtime_error_lookup
    assert "public static let commonErrUnknown = 40000" in runtime_error_lookup
    assert "public static let demoErrUnknown = 40001" in runtime_error_lookup

    assert "public struct SubmitJSON: Codable, Sendable" in runtime_types
    assert "public var keyword: KeywordEnum?" in runtime_types
    assert "private enum CodingKeys: String, CodingKey" in runtime_types
    assert 'case enabled = "enabled"' in runtime_types
    assert "public enum StatusEnum: Int, Codable, Sendable, APIWireValue" in runtime_types
    assert "case default_ = \"default\"" in runtime_types
    assert "case class_ = \"class\"" in runtime_types

    assert "public func ping(" in route_client
    assert "query: query?.toQueryItems() ?? []" in route_client
    assert "public func submit(" in route_client
    assert "let jsonBody: Any?" in route_client
    assert "try apiEncodeJSONObject(json)" in route_client
    assert "public func form(" in route_client
    assert "let formBody = try form?.toFormFields()" in route_client
    assert "public func preview(" in route_client
    assert "let multipartBody = try multipart?.toMultipartFields()" in route_client
    assert "public func packetPost(" in route_client
    assert "public func packetGet(" in route_client
    assert "let binaryBody = try binary?.encode()" in route_client
    assert 'responseKind: "bytes"' in route_client
    assert 'responseKind: "file"' in route_client
    assert 'responseKind: "byte_stream"' in route_client
    assert 'responseKind: "binary_schema"' in route_client
    assert "public func subscribeEvents(" in route_client
    assert ") -> APIStreamBridge<AssistantServerMessage, CloseInfo>" in route_client
    assert "public func openAssistant(" in route_client
    assert ") -> APIChannelBridge<AssistantServerMessage, AssistantClientMessage, CloseInfo>" in route_client
    assert 'delivery: "unordered"' in route_client

    assert "public enum AssistantServerMessage: Codable, Sendable" in route_types
    assert "case delta(AssistantDelta)" in route_types
    assert "public enum AssistantClientMessage: Codable, Sendable" in route_types
    assert "case input(AssistantInput)" in route_types
    assert "case cancel(AssistantCancel)" in route_types
    assert "public static func input" not in route_types
    assert "public struct DemoPacket: Codable, Sendable" in route_binary
    assert "public func encodeDemoPacket(_ value: DemoPacket) throws -> Data" in route_binary

    assert 'baseURL: URL? = URL(string: "http://localhost:2333")!' in http_config
    assert "public final class URLSessionAPITransport: APITransport" in http_transport
    assert "application/x-www-form-urlencoded" in http_transport
    assert "multipart/form-data; boundary=" in http_transport
    assert "apiHTTPEmptyStreamBridge(routeID: options.routeID)" in http_transport
    assert "apiHTTPWebSocketBridge(" in http_transport
    assert "public func apiHTTPWebSocketBridge" in http_connection


def test_swift_transport_runtime_profiles_are_isolated_to_transport_templates(tmp_path: Path) -> None:
    modern_dir = tmp_path / "modern"
    compat_dir = tmp_path / "compat"
    write_demo_swift_package(modern_dir, runtime_profile="modern")
    write_demo_swift_package(compat_dir, runtime_profile="ios14-compat")

    modern_package = (modern_dir / "Package.swift").read_text(encoding="utf-8")
    compat_package = (compat_dir / "Package.swift").read_text(encoding="utf-8")
    modern_transport = (
        modern_dir
        / "Sources"
        / "ApiBlueprintExampleClient"
        / "API"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")
    compat_transport = (
        compat_dir
        / "Sources"
        / "ApiBlueprintExampleClient"
        / "API"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")

    assert ".iOS(.v15)" in modern_package
    assert ".iOS(.v14)" in compat_package
    assert "try await config.session.data(for: urlRequest)" in modern_transport
    assert "try await config.session.bytes(for: urlRequest)" in modern_transport
    assert "performCompatDataTask" not in modern_transport
    assert "performCompatDataTask" in compat_transport
    assert ".data(for:" not in compat_transport
    assert ".bytes(for:" not in compat_transport
