import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

import ABClient
import ABClientRuntime
import ABClientAPIRoutes
import ABClientAltRoutes
import ABClientLegacyRoutes

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
                : "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,empty-response,path-params,audit-binary,wide-binary,binary-response,media,request-options,media-filename-edge,media-error,single-channel,legacy-json"
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
        if selected.contains("empty-response") {
            try await checkEmptyResponse(client)
        }
        if selected.contains("path-params") {
            try await checkPathParams(client)
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
        if selected.contains("wide-binary") {
            try await checkWideBinary(client)
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
        if selected.contains("sse") {
            try await checkSSE(client)
        }
        if selected.contains("websocket") {
            try await checkWebSocket(client)
        }
        if selected.contains("single-channel") {
            try await checkSingleChannel(client)
        }
        if selected.contains("naming") {
            try await checkNaming(client)
        }
        if selected.contains("legacy-json") {
            try await checkLegacyJson(client)
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

private func checkEmptyResponse(_ client: ABClient) async throws {
    _ = try await client.api.demo.emptyResponse()
}

private func checkPathParams(_ client: ABClient) async throws {
    let response = try await client.api.demo.pathEcho(path: PathEchoPath(item: "alpha", badge: "gold badge"))
    try expectEqual(response.item, "alpha", "pathEcho.item")
    try expectEqual(response.badge, "gold badge", "pathEcho.badge")
    try expectEqual(response.combined, "alpha:gold badge", "pathEcho.combined")
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
        binary: try decodeDemoPacket(demoPacketBytes())
    )
    try expectBinaryResponse(response, trace: "swift-typed")
}

private func checkAuditBinary(_ client: ABClient) async throws {
    let response = try await client.api.binary.auditPacket(
        query: BinaryAuditPacketQuery(trace: "swift-audit"),
        binary: try decodeAuditPacket(auditPacketBytes())
    )
    try expectEqual(response.trace, "swift-audit", "audit.trace")
    try expectEqual(response.itemCount, 2, "audit.itemCount")
    try expectEqual(response.checksum, 2, "audit.checksum")
}

private func checkWideBinary(_ client: ABClient) async throws {
    let payload = Data("wide-payload".utf8)
    let response = try await client.api.binary.widePacket(
        query: BinaryWidePacketQuery(trace: "swift-wide"),
        binary: WidePacket(
            header: WidePacketHeader(
                payloadLen: UInt64(payload.count),
                signedWide: -4_000_000_000
            ),
            body: WidePacketBody(
                payload: payload,
                checksum: UInt64(payload.count)
            )
        )
    )
    try expectEqual(response.trace, "swift-wide", "wideBinary.trace")
    try expectEqual(response.payloadSize, payload.count, "wideBinary.payloadSize")
    try expectEqual(response.signedWide, -4_000_000_000, "wideBinary.signedWide")
    try expectEqual(response.checksum, payload.count, "wideBinary.checksum")
}

private func checkBinaryResponse(_ client: ABClient) async throws {
    let response = try await client.api.binary.auditPacketResponse()
    try expectEqual(try encodeAuditPacket(response), auditPacketBytes(), "binary response bytes")
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
    defer { stream.cancel() }
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

private func checkSSE(_ client: ABClient) async throws {
    let bridge = try client.api.demo.subscribeSweepEvents(openPayload: SweepOpen(runId: "swift-sse"))
    let received = try await withTimeout(label: "sse.message") {
        try await nextMessage(bridge.messages, label: "sse.message")
    }
    switch received {
    case .state(let state):
        try expectContains(state.status, "swift-sse", "sse.message.status")
    default:
        throw ConformanceFailure(message: "sse.message=\(received) expected state")
    }

    let closed = try await withTimeout(label: "sse.close") {
        try await nextClose(bridge.closes, label: "sse.close")
    }
    try expectEqual(closed.code, 1000, "sse.close.code")
    try expectEqual(closed.reason, "example stream complete", "sse.close.reason")
}

private func checkWebSocket(_ client: ABClient) async throws {
    let channel = try client.api.demo.openAssistantSession(openPayload: AssistantOpen(sessionId: "swift-ws"))
    try await channel.send(.input(AssistantInput(text: "hello")))

    let received = try await withTimeout(label: "websocket.message") {
        try await nextMessage(channel.messages, label: "websocket.message")
    }
    let text: String
    switch received {
    case .delta(let delta):
        text = delta.text
    case .done(let done):
        text = done.messageId
    case .log(let log):
        text = "\(log.level):\(log.message)"
    }
    try expectContains(text, "swift-ws", "websocket.message.session")
    try expectContains(text, "hello", "websocket.message.text")

    try await channel.send(.cancel(AssistantCancel(reason: "swift complete")))
    let closed = try await withTimeout(label: "websocket.close") {
        try await nextClose(channel.closes, label: "websocket.close")
    }
    try expectEqual(closed.code, 1000, "websocket.close.code")
    try expectEqual(closed.reason, "swift complete", "websocket.close.reason")
}

private func checkSingleChannel(_ client: ABClient) async throws {
    let channel = try client.api.api.openHelloChannel()
    try await channel.send(HelloChannelMessage(type_: .ping, data: .object(["source": .string("swift")])))

    let received = try await withTimeout(label: "single-channel.message") {
        try await nextMessage(channel.messages, label: "single-channel.message")
    }
    try expectEqual(received.type_, .pong, "single-channel.type")

    let closed = try await withTimeout(label: "single-channel.close") {
        try await nextClose(channel.closes, label: "single-channel.close")
    }
    try expectEqual(closed.code, 1000, "single-channel.close.code")
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

private func checkLegacyJson(_ client: ABClient) async throws {
    let profile = try await client.legacy.account.accountProfile()
    try expectEqual(profile.userId, "1000010", "legacy.profile.userId")
    try expectEqual(profile.nickname, "legacy-user", "legacy.profile.nickname")

    let rooms = try await client.legacy.room.roomList()
    try expectEqual(rooms.rooms.first?.roomId, "100", "legacy.room.roomId")
    try expectEqual(rooms.rooms.first?.title, "legacy-room", "legacy.room.title")

    let compat = try await client.legacy.legacyJson.legacyJsonCompat()
    try expectLegacyTargetArray(compat.target, ["legacy-room", "backup-room"], "legacy.compat.target")
    try expectLegacyIDs(compat.ids, ["1", "2", "3"], "legacy.compat.ids")
    try expectEqual(compat.normalizedIds, ["1", "2", "3"], "legacy.compat.normalizedIds")

    let decoder = JSONDecoder()
    let numericProfile = try decoder.decode(
        AccountProfile.self,
        from: Data(#"{"user_id":1000010,"nickname":"legacy-user"}"#.utf8)
    )
    try expectEqual(numericProfile.userId, "1000010", "legacy.fixture.profile.userId")

    let numericRooms = try decoder.decode(
        RoomRoomListResponse.self,
        from: Data(#"{"rooms":[{"room_id":100,"title":"legacy-room"}]}"#.utf8)
    )
    try expectEqual(numericRooms.rooms.first?.roomId, "100", "legacy.fixture.room.roomId")

    let stringTarget = try decoder.decode(
        LegacyJsonCompatPayload.self,
        from: Data(#"{"target":"legacy-room","ids":["1",2,"3"],"normalized_ids":["1",2,"3"]}"#.utf8)
    )
    switch stringTarget.target {
    case .string(let value):
        try expectEqual(value, "legacy-room", "legacy.fixture.target.string")
    default:
        throw ConformanceFailure(message: "legacy.fixture.target.string=\(stringTarget.target) expected string")
    }
    try expectLegacyIDs(stringTarget.ids, ["1", "2", "3"], "legacy.fixture.ids.string")
    try expectEqual(stringTarget.normalizedIds, ["1", "2", "3"], "legacy.fixture.normalizedIds.string")

    let arrayTarget = try decoder.decode(
        LegacyJsonCompatPayload.self,
        from: Data(#"{"target":["legacy-room","backup-room"],"ids":["1",2,"3"],"normalized_ids":["1",2,"3"]}"#.utf8)
    )
    try expectLegacyTargetArray(arrayTarget.target, ["legacy-room", "backup-room"], "legacy.fixture.target.array")
    try expectLegacyIDs(arrayTarget.ids, ["1", "2", "3"], "legacy.fixture.ids.array")
    try expectEqual(arrayTarget.normalizedIds, ["1", "2", "3"], "legacy.fixture.normalizedIds.array")
}

private func expectLegacyTargetArray(
    _ target: APIStringOrArrayOfStringOneOf,
    _ expected: [String],
    _ label: String
) throws {
    switch target {
    case .arrayOfString(let values):
        try expectEqual(values, expected, label)
    default:
        throw ConformanceFailure(message: "\(label)=\(target) expected array")
    }
}

private func expectLegacyIDs(_ ids: [APIStringOrIntOneOf], _ expected: [String], _ label: String) throws {
    let actual = ids.map { item -> String in
        switch item {
        case .string(let value):
            return value
        case .int(let value):
            return String(value)
        }
    }
    try expectEqual(actual, expected, label)
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

private func nextMessage<T>(_ stream: AsyncThrowingStream<T, Error>, label: String) async throws -> T {
    var iterator = stream.makeAsyncIterator()
    guard let value = try await iterator.next() else {
        throw ConformanceFailure(message: "\(label) ended before first message")
    }
    return value
}

private func nextClose<T>(_ stream: AsyncStream<T>, label: String) async throws -> T {
    var iterator = stream.makeAsyncIterator()
    if let value = await iterator.next() {
        return value
    }
    throw ConformanceFailure(message: "\(label) ended before close payload")
}

private func withTimeout<T>(label: String, seconds: UInt64 = 5, _ operation: @escaping () async throws -> T) async throws -> T {
    try await withThrowingTaskGroup(of: T.self) { group in
        group.addTask {
            try await operation()
        }
        group.addTask {
            try await Task.sleep(nanoseconds: seconds * 1_000_000_000)
            throw ConformanceFailure(message: "\(label) timed out")
        }
        guard let result = try await group.next() else {
            throw ConformanceFailure(message: "\(label) produced no result")
        }
        group.cancelAll()
        return result
    }
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
