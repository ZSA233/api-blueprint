import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

import ABClient
import ABClientRuntime
import ABClientAPIRoutes
import ABClientAltRoutes

private let sampleJPEG = Data([
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
])

private struct ConformanceFailure: Error, CustomStringConvertible {
    let message: String

    var description: String {
        message
    }
}

@main
struct SwiftConformance {
    static func main() async throws {
        guard CommandLine.arguments.count >= 2 else {
            throw ConformanceFailure(message: "base URL argument is required")
        }
        guard let baseURL = URL(string: CommandLine.arguments[1]) else {
            throw ConformanceFailure(message: "invalid base URL: \(CommandLine.arguments[1])")
        }
        let selected = scenarioSet(
            CommandLine.arguments.count > 2
                ? CommandLine.arguments[2]
                : "rpc,binary,form,error,naming,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,binary-response,media,request-options,media-filename-edge,media-error"
        )
        let client = HTTPAPIClient.create(baseURL: baseURL)

        if selected.contains("rpc") {
            try await checkRPC(client)
        }
        if selected.contains("raw") {
            try await checkRaw(baseURL)
        }
        if selected.contains("xml") {
            try await checkXML(client)
        }
        if selected.contains("static") {
            try await checkStatic(baseURL)
        }
        if selected.contains("header") {
            try await checkHeader(client)
        }
        if selected.contains("scalar") {
            try await checkScalar(client)
        }
        if selected.contains("enum") {
            try await checkEnum(client)
        }
        if selected.contains("map") {
            try await checkMap(client)
        }
        if selected.contains("deprecated") {
            try await checkDeprecated(client)
        }
        if selected.contains("form") {
            try await checkForm(client)
        }
        if selected.contains("binary") {
            try await checkBinary(client)
        }
        if selected.contains("audit-binary") {
            try await checkAuditBinary(client)
        }
        if selected.contains("binary-response") {
            try await checkBinaryResponse(client)
        }
        if selected.contains("media") {
            try await checkMedia(client)
        }
        if selected.contains("request-options") {
            try await checkRequestOptions(baseURL)
        }
        if selected.contains("media-filename-edge") {
            try await checkMediaFilenameEdge(client)
        }
        if selected.contains("media-error") {
            try await checkMediaError(client)
        }
        if selected.contains("error") {
            try await checkTypedErrors(client)
        }
        if selected.contains("naming") {
            try await checkNaming(client)
        }
    }
}

private func scenarioSet(_ raw: String) -> Set<String> {
    Set(raw.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty })
}

private func checkRPC(_ client: ABClient) async throws {
    let post = try await client.api.demo.testPost(json: DemoTestPostJSON(req1: "swift", req2: 7))
    try expectEqual(post.list, ["test_post", "swift"], "testPost.list")
    try expectEqual(post.map["req2"]?.haha, 7, "testPost.map.req2")

    let put = try await client.api.demo.putDemo(
        query: DemoPutDemoQuery(arg1: "query", arg2: 3.5),
        json: DemoPutDemoJSON(req1: "body", req2: 9)
    )
    try expectEqual(put.list, ["query", "body"], "putDemo.list")
    try expectEqual(put.anonKv.kv1, 9, "putDemo.anonKv.kv1")
}

private func checkRaw(_ baseURL: URL) async throws {
    _ = try await rawHTTP(baseURL, method: "POST", path: "/api/demo/raw")
}

private func checkXML(_ client: ABClient) async throws {
    let response = try await client.api.demo.delete(query: DemoDeleteQuery(arg1: "swift-xml", arg2: 7))
    try expectContains(response, "swift-xml", "xml response")
}

private func checkStatic(_ baseURL: URL) async throws {
    _ = try await rawHTTP(baseURL, method: "GET", path: "/static/doc.json")
    let response = try await rawHTTP(baseURL, method: "GET", path: "/static/dochaha")
    let text = String(data: response.body, encoding: .utf8) ?? ""
    try expectContains(text, "hello world", "static.dochaha")
}

private func checkHeader(_ client: ABClient) async throws {
    let response = try await client.api.demo.abc(
        options: APIRequestOptions(headers: ["x-token": "conformance-token"])
    )
    try expectEqual(response.bc, "header-ok", "header.bc")
}

private func checkScalar(_ client: ABClient) async throws {
    try await expectEqual(client.api.hello.string(), "hello-string", "hello.string")
    try await expectEqual(client.api.hello.uint64(), 9_007_199_254_740_991, "hello.uint64")
}

private func checkEnum(_ client: ABClient) async throws {
    try await expectEqual(client.api.hello.stringEmun(), MapEnum.a, "hello.stringEmun")
    try await expectEqual(client.api.hello.listEnum(), [MapEnum.a, MapEnum.b], "hello.listEnum")
}

private func checkMap(_ client: ABClient) async throws {
    let model = try await client.api.demo.mapModel()
    try expectEqual(model["1"]?.haha, 101, "mapModel.1.haha")

    let hello = try await client.api.hello.abc(query: HelloAbcQuery(type_: .ping))
    try expectEqual(hello["ping"]?.haha, 1, "hello.abc.ping.haha")

    let enumMap = try await client.api.hello.mapEnum()
    try expectEqual(enumMap["a"]?.haha, 11, "hello.mapEnum.a.haha")
}

private func checkDeprecated(_ client: ABClient) async throws {
    let response = try await client.api.demo.postDeprecated(
        json: DemoPostDeprecatedJSON(req1: "swift-deprecated", req2: 3)
    )
    try expectEqual(response.list, ["swift-deprecated"], "deprecated.list")
}

private func checkForm(_ client: ABClient) async throws {
    let response = try await client.api.demo.formSubmit(
        form: DemoFormSubmitForm(title: "swift-form", count: 4, enabled: true)
    )
    try expectEqual(response.summary, "swift-form", "form.summary")
    try expectEqual(response.count, 4, "form.count")
    try expectEqual(response.enabled, true, "form.enabled")
}

private func checkBinary(_ client: ABClient) async throws {
    let response = try await client.api.binary.packet(
        query: BinaryPacketQuery(trace: "swift-typed"),
        binary: DemoPacket(data: demoPacketBytes())
    )
    try expectBinaryResponse(response, trace: "swift-typed")
}

private func checkAuditBinary(_ client: ABClient) async throws {
    let response = try await client.api.binary.auditPacket(
        query: BinaryAuditPacketQuery(trace: "swift-audit"),
        binary: AuditPacket(data: auditPacketBytes())
    )
    try expectEqual(response.trace, "swift-audit", "audit.trace")
    try expectEqual(response.itemCount, 2, "audit.itemCount")
    try expectEqual(response.checksum, 2, "audit.checksum")
}

private func checkBinaryResponse(_ client: ABClient) async throws {
    let response = try await client.api.binary.auditPacketResponse()
    try expectEqual(response.data, auditPacketBytes(), "binary response bytes")
}

private func checkMedia(_ client: ABClient) async throws {
    let preview = try await client.api.media.mediaPreview(
        multipart: MediaPreviewRequest(
            title: "swift-media",
            image: APIFilePart(filename: "preview.jpg", contentType: "image/jpeg", data: sampleJPEG)
        )
    )
    try expectEqual(preview.statusCode, 200, "media.preview.status")
    try expectPrefix(preview.body, [0xff, 0xd8], "media.preview")

    let frame = try await client.api.media.mediaFrame()
    try expectPrefix(frame.body, [0xff, 0xd8], "media.frame")

    let download = try await client.api.media.mediaDownload()
    try expectEqual(download.filename, "media-report.xlsx", "media.download.filename")
    try expectPrefix(download.body, [0x50, 0x4b], "media.download")

    let dynamic = try await client.api.media.mediaDownloadDynamic()
    try expectEqual(dynamic.filename, "media-report-dynamic.xlsx", "media.dynamic.filename")
    try expectPrefix(dynamic.body, [0x50, 0x4b], "media.dynamic")

    let stream = try await client.api.media.mediaMjpeg()
    var chunk = Data()
    for try await part in stream.body {
        chunk.append(part)
        if chunk.range(of: Data("--frame".utf8)) != nil || chunk.starts(with: sampleJPEG.prefix(2)) || chunk.count > 256 {
            break
        }
    }
    if chunk.range(of: Data("--frame".utf8)) == nil && !chunk.starts(with: sampleJPEG.prefix(2)) {
        throw ConformanceFailure(message: "media.mjpeg missing boundary or JPEG body: \(chunk.map { String(format: "%02x", $0) }.joined())")
    }
}

private func checkRequestOptions(_ baseURL: URL) async throws {
    let optionsClient = HTTPAPIClient.create(
        config: HTTPAPIConfig(
            baseURL: baseURL,
            defaultHeaders: [
                "x-options-default": "default",
                "x-options-token": "default",
            ],
            timeout: 0.02
        )
    )
    let ok = try await optionsClient.api.demo.requestOptions(
        query: DemoRequestOptionsQuery(delayMs: 30),
        options: APIRequestOptions(headers: ["x-options-token": "per-call"], timeout: 1.0)
    )
    try expectEqual(ok.status, "ok", "requestOptions.status")
    try expectEqual(ok.delayMs, 30, "requestOptions.delayMs")

    var timedOut = false
    do {
        _ = try await optionsClient.api.demo.requestOptions(
            query: DemoRequestOptionsQuery(delayMs: 120),
            options: APIRequestOptions(headers: ["x-options-token": "per-call"], timeout: 0.01)
        )
    } catch {
        timedOut = true
    }
    try expectEqual(timedOut, true, "requestOptions timeout")
}

private func checkMediaFilenameEdge(_ client: ABClient) async throws {
    let response = try await client.api.media.mediaDownloadFilenameEdge()
    try expectEqual(response.filename, "媒体报告.xlsx", "media.filenameEdge.filename")
    try expectPrefix(response.body, [0x50, 0x4b], "media.filenameEdge")
}

private func checkMediaError(_ client: ABClient) async throws {
    let ok = try await client.api.media.mediaErrorFrame(query: MediaMediaErrorFrameQuery(mode: "ok"))
    try expectPrefix(ok.body, [0xff, 0xd8], "media.error.ok")

    let rateLimited = try await expectAPIError(routeID: "api.media.get.errorframe") {
        try await client.api.media.mediaErrorFrame(query: MediaMediaErrorFrameQuery(mode: "rate_limit"))
    }
    try expectEqual(rateLimited.payload.code, APIErrorCodes.rateLimited, "media.error.code")
}

private func checkTypedErrors(_ client: ABClient) async throws {
    let ok = try await client.api.demo.errorDemo(query: DemoErrorDemoQuery(mode: "ok"))
    try expectEqual(ok.status, "ok", "errorDemo.ok.status")

    let rateLimited = try await expectAPIError {
        try await client.api.demo.errorDemo(query: DemoErrorDemoQuery(mode: "rate_limit"))
    }
    try expectEqual(rateLimited.payload.code, APIErrorCodes.rateLimited, "rateLimited.code")
    try expectEqual(rateLimited.payload.toastText, "请等待 30 秒后重试", "rateLimited.toastText")

    let unknown = try await expectAPIError {
        try await client.api.demo.errorDemo(query: DemoErrorDemoQuery(mode: "unknown"))
    }
    if let id = unknown.payload.id, !id.isEmpty {
        throw ConformanceFailure(message: "unknown.id=\(id) expected empty or nil")
    }
    try expectEqual(unknown.payload.code, 70001, "unknown.code")
    try expectEqual(unknown.payload.message, "example undefined business error", "unknown.message")
}

private func checkNaming(_ client: ABClient) async throws {
    let apiResponse = try await client.api.conflict.default_(
        query: ABClientAPIRoutes.ConflictDefaultQuery(class_: "swift-api")
    )
    try expectEqual(apiResponse.default_, "api-default", "api.conflict.default")
    try expectEqual(apiResponse.class_, "swift-api", "api.conflict.class")
    try expectEqual(apiResponse.enum_, KeywordEnum.default_, "api.conflict.enum")

    let altResponse = try await client.alt.conflict.default_(
        query: ABClientAltRoutes.ConflictDefaultQuery(class_: "swift-alt")
    )
    try expectEqual(altResponse.default_, "alt-default", "alt.conflict.default")
    try expectEqual(altResponse.class_, "swift-alt", "alt.conflict.class")
    try expectEqual(altResponse.enum_, KeywordEnum.class_, "alt.conflict.enum")
}

private func expectBinaryResponse(_ response: BinaryPacketResponse, trace: String) throws {
    try expectEqual(response.trace, trace, "binary.trace")
    try expectEqual(response.version, 1, "binary.version")
    try expectEqual(response.itemCount, 2, "binary.itemCount")
    try expectEqual(response.payload, "payload-ok", "binary.payload")
    try expectEqual(response.scoreSum, 8, "binary.scoreSum")
    try expectEqual(response.firstLabel, "alpha", "binary.firstLabel")
    try expectEqual(response.itemIds, [11, 22], "binary.itemIds")
    try expectEqual(response.checksum, 12, "binary.checksum")
}

private func expectAPIError<T>(
    routeID: String = "api.demo.get.errordemo",
    _ operation: () async throws -> T
) async throws -> APIError {
    do {
        _ = try await operation()
    } catch let error as APIError {
        try expectEqual(error.routeID, routeID, "apiError.routeID")
        if error.raw?.isEmpty ?? true {
            throw ConformanceFailure(message: "apiError.raw is empty")
        }
        return error
    }
    throw ConformanceFailure(message: "expected APIError but request succeeded")
}

private func rawHTTP(
    _ baseURL: URL,
    method: String,
    path: String,
    headers: [String: String] = [:]
) async throws -> (body: Data, response: HTTPURLResponse) {
    let base = baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    guard let url = URL(string: base + path) else {
        throw ConformanceFailure(message: "invalid URL path: \(path)")
    }
    var request = URLRequest(url: url)
    request.httpMethod = method
    for (name, value) in headers {
        request.setValue(value, forHTTPHeaderField: name)
    }
    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse else {
        throw ConformanceFailure(message: "expected HTTP response for \(path)")
    }
    if http.statusCode < 200 || http.statusCode >= 300 {
        let text = String(data: data, encoding: .utf8) ?? ""
        throw ConformanceFailure(message: "\(method) \(path) status=\(http.statusCode) body=\(text)")
    }
    return (data, http)
}

private func expectEqual<T: Equatable>(_ actual: T, _ expected: T, _ label: String) throws {
    if actual != expected {
        throw ConformanceFailure(message: "\(label)=\(actual) expected \(expected)")
    }
}

private func expectEqual<T: Equatable>(_ actual: T?, _ expected: T, _ label: String) throws {
    if actual != expected {
        throw ConformanceFailure(message: "\(label)=\(String(describing: actual)) expected \(expected)")
    }
}

private func expectContains(_ text: String, _ snippet: String, _ label: String) throws {
    if !text.contains(snippet) {
        throw ConformanceFailure(message: "\(label) missing \(snippet): \(text)")
    }
}

private func expectPrefix(_ data: Data, _ prefix: [UInt8], _ label: String) throws {
    if !data.starts(with: Data(prefix)) {
        throw ConformanceFailure(message: "\(label) prefix=\(Array(data.prefix(prefix.count))) expected \(prefix)")
    }
}

private func demoPacketBytes() -> Data {
    dataFromHex(
        "41425031010001000300000000000003020107000002000a00000002000b00000001000000000000f43f05616c7068611600000000000000000000044004626574617061796c6f61642d6f6b0000000000000c4000000000000012400c000000"
    )
}

private func auditPacketBytes() -> Data {
    dataFromHex("02000100000002000b000000650016000000ca0002000000")
}

private func dataFromHex(_ hex: String) -> Data {
    var result = Data()
    var index = hex.startIndex
    while index < hex.endIndex {
        let next = hex.index(index, offsetBy: 2)
        let byte = UInt8(hex[index..<next], radix: 16)!
        result.append(byte)
        index = next
    }
    return result
}
