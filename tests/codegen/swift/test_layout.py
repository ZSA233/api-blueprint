from __future__ import annotations

from .helpers import *


def test_swift_writer_generates_spm_runtime_routes_transport_and_preserved_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"
    aggregate_dir = out_dir / "Sources" / "ABClient"
    runtime_dir = out_dir / "Sources" / "ABClientRuntime"
    root_source_dir = out_dir / "Sources" / "ABClientAPIRoutes"
    api_dir = root_source_dir / "API"
    route_dir = api_dir / "Routes" / "API" / "Demo"
    runtime_http_dir = runtime_dir / "Transports" / "HTTP"
    aggregate_http_dir = aggregate_dir / "Transports" / "HTTP"
    route_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    runtime_http_dir.mkdir(parents=True)
    aggregate_http_dir.mkdir(parents=True)
    (aggregate_dir / "API").mkdir(parents=True)
    (out_dir / "Package.swift").write_text("// USER PACKAGE\n", encoding="utf-8")
    (aggregate_dir / "ABClient.swift").write_text("// USER PACKAGE FACADE\n", encoding="utf-8")
    (api_dir / "APIRootClient.swift").write_text("// USER ROOT FACADE\n", encoding="utf-8")
    (runtime_dir / "APICoding.swift").write_text("// USER CODING\n", encoding="utf-8")
    (route_dir / "DemoAPI.swift").write_text("// USER ROUTE FACADE\n", encoding="utf-8")
    (route_dir / "DemoTypes.swift").write_text("// USER TYPES FACADE\n", encoding="utf-8")
    (aggregate_http_dir / "HTTPAPIClient.swift").write_text("// USER HTTP FACADE\n", encoding="utf-8")

    write_demo_swift_package(out_dir)

    package_manifest = (out_dir / "Package.swift").read_text(encoding="utf-8")
    generated_package_facade = (aggregate_dir / "GenABClient.swift").read_text(encoding="utf-8")
    generated_root = (api_dir / "GenAPIRootClient.swift").read_text(encoding="utf-8")
    runtime_transport = (runtime_dir / "GenAPITransport.swift").read_text(encoding="utf-8")
    runtime_errors = (runtime_dir / "GenAPIErrors.swift").read_text(encoding="utf-8")
    runtime_error_lookup = (runtime_dir / "GenAPIErrorLookup.swift").read_text(encoding="utf-8")
    runtime_types = (runtime_dir / "GenAPITypes.swift").read_text(encoding="utf-8")
    binary_runtime = (runtime_dir / "Binary" / "GenBinaryRuntime.swift").read_text(encoding="utf-8")
    route_client = (route_dir / "GenDemoAPI.swift").read_text(encoding="utf-8")
    route_types = (route_dir / "GenDemoTypes.swift").read_text(encoding="utf-8")
    route_binary = (route_dir / "GenBinary.swift").read_text(encoding="utf-8")
    http_config = (runtime_http_dir / "GenHTTPAPIConfig.swift").read_text(encoding="utf-8")
    http_transport = (runtime_http_dir / "GenURLSessionAPITransport.swift").read_text(encoding="utf-8")
    http_connection = (runtime_http_dir / "GenHTTPConnection.swift").read_text(encoding="utf-8")

    assert package_manifest.startswith("// swift-tools-version: 5.9\n" + SWIFT_CLIENT_GENERATED_HEADER)
    assert 'name: "ApiBlueprintExampleClient"' in package_manifest
    assert '.library(name: "ABClientRuntime"' in package_manifest
    assert '.library(name: "ABClientAPIRoutes"' in package_manifest
    assert 'exclude: ["API"]' in package_manifest

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

    assert (aggregate_dir / "ABClient.swift").read_text(encoding="utf-8") == "// USER PACKAGE FACADE\n"
    assert (api_dir / "APIRootClient.swift").read_text(encoding="utf-8") == "// USER ROOT FACADE\n"
    assert (runtime_dir / "APICoding.swift").read_text(encoding="utf-8") == "// USER CODING\n"
    assert (route_dir / "DemoAPI.swift").read_text(encoding="utf-8") == "// USER ROUTE FACADE\n"
    assert (route_dir / "DemoTypes.swift").read_text(encoding="utf-8") == "// USER TYPES FACADE\n"
    assert (aggregate_http_dir / "HTTPAPIClient.swift").read_text(encoding="utf-8") == "// USER HTTP FACADE\n"

    assert "import ABClientRuntime" in generated_package_facade
    assert "import ABClientAPIRoutes" in generated_package_facade
    assert "open class GenABClient" in generated_package_facade
    assert "public lazy var api = ABClientAPIRoutes.APIRootClient(transport: transport)" in generated_package_facade
    assert "import ABClientRuntime" in generated_root
    assert "public typealias APITransport = ABClientRuntime.APITransport" in generated_root
    assert "open class GenAPIRootClient" in generated_root
    assert "public lazy var demo = DemoAPI(transport: transport)" in generated_root

    assert "public protocol APITransport" in runtime_transport
    assert "func request<Response>(_ request: APIRequest<Response>) async throws -> Response" in runtime_transport
    assert "func openStream<Recv, Close>(_ options: APIStreamConnectOptions<Recv, Close>) throws -> APIStreamBridge" in runtime_transport
    assert "func openChannel<Recv, Send, Close>(_ options: APIChannelConnectOptions<Recv, Send, Close>) throws -> APIChannelBridge" in runtime_transport
    assert "public struct APICodingConfig: Sendable" in runtime_transport
    assert "public enum APITransportError" in runtime_transport
    assert "public struct APIRequestOptions" in runtime_transport
    assert "public struct APIRequest<Response>" in runtime_transport
    assert "public var json: ((APICodingConfig) throws -> Data)?" in runtime_transport
    assert "public var decodeData: (Data, APIResponseEnvelope, APICodingConfig) throws -> Response" in runtime_transport
    assert "public struct APIRawResponse" in runtime_transport
    assert "public struct APIStreamResponse" in runtime_transport
    assert "public struct APIFilePart: Codable, Sendable" in runtime_transport
    assert "public struct APIBinaryPayload: Sendable" in runtime_transport
    assert "public enum APIJSONValue" in runtime_transport
    assert "public struct APIErrorPayload" in runtime_errors
    assert "public struct APIError: Error" in runtime_errors
    assert "let fallback = code.flatMap { lookupAPIError(code: $0) }" in runtime_errors
    assert 'let nested = apiBlueprintObject(apiBlueprintValue(object, "error"))' in runtime_errors
    assert "private func apiBlueprintValue(_ object: [String: Any?]?, _ key: String) -> Any?" in runtime_errors
    assert runtime_errors.count("guard let object = apiBlueprintObject(value)") == 2
    assert "fallback?.id" in runtime_errors
    assert "fallback?.toastKey" in runtime_errors
    assert "public enum APIErrorCodes" in runtime_error_lookup
    assert "public static let commonErrUnknown = 40000" in runtime_error_lookup
    assert "public static let demoErrUnknown = 40001" in runtime_error_lookup
    assert 'toastKey: "common.unknown"' in runtime_error_lookup
    assert 'toastDefault: "Common unknown"' in runtime_error_lookup

    assert "public struct SubmitJSON: Codable, Sendable" in runtime_types
    assert "public var keyword: KeywordEnum?" in runtime_types
    assert "private enum CodingKeys: String, CodingKey" in runtime_types
    assert 'case enabled = "enabled"' in runtime_types
    assert "public enum StatusEnum: Int, Codable, Sendable, APIWireValue" in runtime_types
    assert "case default_ = \"default\"" in runtime_types
    assert "case class_ = \"class\"" in runtime_types

    assert "import ABClientRuntime" in route_client
    assert "public func ping(" in route_client
    assert "query: query?.toQueryItems() ?? []" in route_client
    assert "public func submit(" in route_client
    assert "let jsonBody: ((APICodingConfig) throws -> Data)?" in route_client
    assert "try apiEncodeJSONData(json, coding: coding)" in route_client
    assert "try apiEncodeJSONObject(json)" not in route_client
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
    assert "decodeData: { data, envelope, coding in try apiDecodeResponse(" in route_client
    assert "public func subscribeEvents(" in route_client
    assert ") throws -> APIStreamBridge<AssistantServerMessage, CloseInfo>" in route_client
    assert "public func openAssistant(" in route_client
    assert ") throws -> APIChannelBridge<AssistantServerMessage, AssistantClientMessage, CloseInfo>" in route_client
    assert 'delivery: "unordered"' in route_client

    assert "import ABClientRuntime" in route_types
    assert "public enum AssistantServerMessage: Codable, Sendable" in route_types
    assert "case delta(AssistantDelta)" in route_types
    assert "public enum AssistantClientMessage: Codable, Sendable" in route_types
    assert "case input(AssistantInput)" in route_types
    assert "case cancel(AssistantCancel)" in route_types
    assert "public static func input" not in route_types
    assert "public struct DemoPacket: Codable, Sendable" in route_binary
    assert "public enum DemoPacketWire" in route_binary
    assert "public struct DemoPacketBody: Codable, Sendable" in route_binary
    assert "public var payload: Data" in route_binary
    assert "public var data: Data" not in route_binary
    assert "let payload = try reader.readBytes(\"payload\", 4)" in route_binary
    assert "try writer.writeBytesExact(\"payload\", value.payload, 4)" in route_binary
    assert "public static func encode(_ value: DemoPacket) throws -> Data" in route_binary
    assert "public func encodeDemoPacket(_ value: DemoPacket) throws -> Data" in route_binary
    assert "public final class APIBinaryWriter" in binary_runtime
    assert "public final class APIBinaryReader" in binary_runtime
    assert "public struct APIBinaryEncodeError" in binary_runtime
    assert "public struct APIBinaryDecodeError" in binary_runtime
    assert "public func readU24(_ path: String) throws -> Int" in binary_runtime
    assert "public func apiBinaryWrapIndex(_ path: String, _ index: Int, _ error: APIBinaryDecodeError)" in binary_runtime

    assert 'baseURL: URL? = URL(string: "http://localhost:2333")' in http_config
    assert "public let byteStreamChunkSize: Int" in http_config
    assert "public let maxErrorBodyBytes: Int" in http_config
    assert "public let maxSSEEventBytes: Int" in http_config
    assert "public let maxWebSocketMessageBytes: Int" in http_config
    assert "public let streamBufferLimit: Int" in http_config
    assert "public let coding: APICodingConfig" in http_config
    assert "public final class URLSessionAPITransport: APITransport" in http_transport
    assert "application/x-www-form-urlencoded" in http_transport
    assert "CharacterSet.alphanumerics" in http_transport
    assert 'allowed.insert(charactersIn: "-._~")' in http_transport
    assert ".urlQueryAllowed" not in http_transport
    assert "components.url!" not in http_transport
    assert "URLComponents(string: raw)!" not in http_transport
    assert "Data([byte])" not in http_transport
    assert "request.json" in http_transport
    assert "try json(config.coding)" in http_transport
    assert "multipart/form-data; boundary=" in http_transport
    assert "InputStream(url: fileURL)" in http_transport
    assert "filename*=UTF-8''" in http_transport
    assert "validateHeaderValue(file.filename)" in http_transport
    assert "APITransportError.invalidHeaderValue" in http_transport
    assert "APITransportError.payloadTooLarge" in http_transport
    assert "httpResponse.statusCode >= 400 || isJSONResponse(httpResponse)" in http_transport
    assert "validateStatus(httpResponse, body: Data()" not in http_transport
    assert "apiHTTPEventStreamBridge(" in http_transport
    assert "apiHTTPWebSocketBridge(" in http_transport
    assert "performModernEventStreamTask" in http_transport
    assert 'request.setValue("text/event-stream", forHTTPHeaderField: "Accept")' in http_transport
    assert "public func apiHTTPEventStreamBridge" in http_connection
    assert "public func apiHTTPWebSocketBridge" in http_connection
    assert "private final class APIHTTPSSEParser" in http_connection
    assert "bufferingPolicy: .bufferingNewest(max(1, streamBufferLimit))" in http_connection
    assert "bufferingPolicy: .bufferingNewest(1)" in http_connection
    assert "APITransportError.payloadTooLarge(kind: \"sse\"" in http_connection
    assert "APITransportError.payloadTooLarge(kind: \"websocket\"" in http_connection
    assert 'buffer.range(of: "\\n\\n")' in http_connection
    assert 'buffer.range(of: "\\r\\n\\r\\n")' in http_connection
    assert 'dataLines.joined(separator: "\\n")' in http_connection
    assert 'if type == "message"' in http_connection
    assert 'if type == "close"' in http_connection
    assert "return .message(value)" in http_connection

    assert "{\n\n    public static let" not in runtime_error_lookup
    assert "commonErrUnknown = 40000\n\n    public static let demoErrUnknown" not in runtime_error_lookup
    assert "switch code {\n\n" not in runtime_error_lookup
    assert "{\n\n    case " not in runtime_types
    assert "{\n\n    case " not in route_types
    assert "switch type {\n\n" not in route_types
    assert "\n\n        case ." not in route_types
    assert 'case delta = "delta"\n    }' in route_types
    assert "self = .delta(try container.decode(AssistantDelta.self, forKey: .data))\n        }" in route_types
    assert "try container.encode(data, forKey: .data)\n        }" in route_types
    assert "\n}\n\n    public init(from decoder" not in route_types
    assert "(\n\n        headers" not in route_client


def test_swift_writer_preserves_package_identity_when_module_is_shorter(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"

    write_demo_swift_package(out_dir, package="api-blueprint-client", module="ABClient")

    package_manifest = (out_dir / "Package.swift").read_text(encoding="utf-8")

    assert 'name: "api-blueprint-client"' in package_manifest
    assert '.library(name: "ABClient", targets: ["ABClient"])' in package_manifest
    assert '.library(name: "ABClientRuntime", targets: ["ABClientRuntime"])' in package_manifest
    assert '.library(name: "ABClientAPIRoutes", targets: ["ABClientAPIRoutes"])' in package_manifest
    assert "apiBlueprintClient" not in package_manifest


def test_swift_writer_generates_one_target_per_root_and_shared_runtime_once(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"

    write_demo_swift_package(out_dir, include_alt=True)

    package_manifest = (out_dir / "Package.swift").read_text(encoding="utf-8")
    aggregate_facade = (out_dir / "Sources" / "ABClient" / "GenABClient.swift").read_text(encoding="utf-8")
    runtime_types = (out_dir / "Sources" / "ABClientRuntime" / "GenAPITypes.swift").read_text(
        encoding="utf-8"
    )
    alt_route = (
        out_dir / "Sources" / "ABClientAltRoutes" / "Alt" / "Routes" / "Alt" / "Demo" / "GenDemoAPI.swift"
    ).read_text(encoding="utf-8")

    assert '.target(\n            name: "ABClientAPIRoutes"' in package_manifest
    assert '.target(\n            name: "ABClientAltRoutes"' in package_manifest
    assert "import ABClientAPIRoutes" in aggregate_facade
    assert "import ABClientAltRoutes" in aggregate_facade
    assert "public lazy var api = ABClientAPIRoutes.APIRootClient(transport: transport)" in aggregate_facade
    assert "public lazy var alt = ABClientAltRoutes.AltRootClient(transport: transport)" in aggregate_facade
    assert len(list(out_dir.rglob("GenURLSessionAPITransport.swift"))) == 1
    assert runtime_types.count("public struct SubmitResponse: Codable, Sendable") == 1
    assert "public func ping(" in alt_route


def test_swift_writer_dedupes_root_module_and_aggregate_property_names(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"
    first = Blueprint(root="/api")
    with first.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))
    second = Blueprint(root="/API")
    with second.group("/demo") as views:
        views.GET("/pong").RSP(message=String(description="message"))

    writer = SwiftWriter(out_dir, package="ApiBlueprintExampleClient", module="ABClient")
    writer.register(first, second)
    writer.gen()

    package_manifest = (out_dir / "Package.swift").read_text(encoding="utf-8")
    aggregate_facade = (
        out_dir / "Sources" / "ABClient" / "GenABClient.swift"
    ).read_text(encoding="utf-8")

    assert '.library(name: "ABClientAPIRoutes", targets: ["ABClientAPIRoutes"])' in package_manifest
    assert '.library(name: "ABClientAPIRoutes2", targets: ["ABClientAPIRoutes2"])' in package_manifest
    assert "public lazy var api = ABClientAPIRoutes.APIRootClient(transport: transport)" in aggregate_facade
    assert "public lazy var api2 = ABClientAPIRoutes2.APIRootClient(transport: transport)" in aggregate_facade


def test_swift_writer_routes_suffix_avoids_runtime_root_module_collision(tmp_path: Path) -> None:
    out_dir = tmp_path / "swift"
    bp = Blueprint(root="/runtime")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    writer = SwiftWriter(out_dir, package="ApiBlueprintExampleClient", module="ABClient")
    writer.register(bp)
    writer.gen()

    package_manifest = (out_dir / "Package.swift").read_text(encoding="utf-8")
    aggregate_facade = (out_dir / "Sources" / "ABClient" / "GenABClient.swift").read_text(encoding="utf-8")

    assert '.library(name: "ABClientRuntime", targets: ["ABClientRuntime"])' in package_manifest
    assert '.library(name: "ABClientRuntimeRoutes", targets: ["ABClientRuntimeRoutes"])' in package_manifest
    assert "ABClientRuntime2" not in package_manifest
    assert "import ABClientRuntimeRoutes" in aggregate_facade
    assert "public lazy var runtime = ABClientRuntimeRoutes.RuntimeRootClient(transport: transport)" in aggregate_facade


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
        / "ABClientRuntime"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")
    modern_connection = (
        modern_dir
        / "Sources"
        / "ABClientRuntime"
        / "Transports"
        / "HTTP"
        / "GenHTTPConnection.swift"
    ).read_text(encoding="utf-8")
    compat_transport = (
        compat_dir
        / "Sources"
        / "ABClientRuntime"
        / "Transports"
        / "HTTP"
        / "GenURLSessionAPITransport.swift"
    ).read_text(encoding="utf-8")

    assert ".iOS(.v15)" in modern_package
    assert ".iOS(.v14)" in compat_package
    assert "try await config.session.data(for: built.request)" in modern_transport
    assert "try await config.session.bytes(for: built.request)" in modern_transport
    assert "performCompatDataTask" not in modern_transport
    assert "apiHTTPEventStreamBridge" in modern_transport
    assert "apiHTTPWebSocketBridge" in modern_transport
    assert "APIHTTPSSEParser" in modern_connection
    assert 'type == "message"' in modern_connection
    assert 'type == "close"' in modern_connection
    assert "performCompatDataTask" in compat_transport
    assert "performCompatEventStreamTask" in compat_transport
    assert "URLSessionDataDelegate" in compat_transport
    assert "didReceive data: Data" in compat_transport
    assert ".data(for:" not in compat_transport
    assert ".bytes(for:" not in compat_transport
