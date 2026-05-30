from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


SCENARIOS = ("json-envelope", "byte-stream", "multipart-file", "sse-limit", "websocket-limit")


@dataclass(frozen=True)
class SwiftRuntimeBenchmarkContext:
    repo_root: Path
    scenarios: tuple[str, ...]
    count: int
    payload_bytes: int
    env: dict[str, str]


@dataclass(frozen=True)
class SwiftRuntimeBenchmarkResult:
    returncode: int


SWIFT_RUNTIME_BENCHMARK_SOURCE = r"""
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

import ABClientRuntime
import ABClientAPIRoutes

private let count = Int(CommandLine.arguments.dropFirst().first ?? "0") ?? 0
private let scenarioInput = CommandLine.arguments.dropFirst(2).first ?? "all"
private let payloadBytes = Int(CommandLine.arguments.dropFirst(3).first ?? "262144") ?? 262_144
private let selectedScenarios = scenarioInput == "all"
    ? Set(["json-envelope", "byte-stream", "multipart-file", "sse-limit", "websocket-limit"])
    : Set(scenarioInput.split(separator: ",").map(String.init))

private struct BenchmarkFailure: Error, CustomStringConvertible {
    let message: String

    var description: String {
        message
    }
}

private final class BenchmarkURLProtocol: URLProtocol {
    static var responseBody = Data()
    static var contentType = "application/octet-stream"
    static var observedUploadBytes = 0

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        Self.observedUploadBytes += readUploadBody().count
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "https://benchmark.local")!,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: ["content-type": Self.contentType]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Self.responseBody)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private func readUploadBody() -> Data {
        if let body = request.httpBody {
            return body
        }
        guard let stream = request.httpBodyStream else {
            return Data()
        }
        var data = Data()
        let bufferSize = 64 * 1024
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer {
            buffer.deallocate()
        }
        stream.open()
        defer {
            stream.close()
        }
        while stream.hasBytesAvailable {
            let count = stream.read(buffer, maxLength: bufferSize)
            if count <= 0 {
                break
            }
            data.append(buffer, count: count)
        }
        return data
    }
}

@main
struct SwiftRuntimeBenchmark {
    static func main() async throws {
        guard count > 0 else {
            throw BenchmarkFailure(message: "count must be greater than zero")
        }
        let unknown = selectedScenarios.subtracting(["json-envelope", "byte-stream", "multipart-file", "sse-limit", "websocket-limit"])
        if !unknown.isEmpty {
            throw BenchmarkFailure(message: "unknown scenarios: \(unknown.sorted().joined(separator: ","))")
        }

        if selectedScenarios.contains("json-envelope") {
            try benchmark("json-envelope", iterations: count) {
                try runJSONEnvelopeDecode(iterations: count)
            }
        }
        if selectedScenarios.contains("byte-stream") {
            try await benchmarkAsync("byte-stream", iterations: count) {
                try await runByteStream(iterations: count, payloadBytes: payloadBytes)
            }
        }
        if selectedScenarios.contains("multipart-file") {
            try await benchmarkAsync("multipart-file", iterations: count) {
                try await runMultipartFile(iterations: count, payloadBytes: payloadBytes)
            }
        }
        if selectedScenarios.contains("sse-limit") {
            try await benchmarkAsync("sse-limit", iterations: count) {
                try await runSSELimit(iterations: count, payloadBytes: payloadBytes)
            }
        }
        if selectedScenarios.contains("websocket-limit") {
            try await benchmarkAsync("websocket-limit", iterations: count) {
                try await runWebSocketLimit(iterations: count, payloadBytes: payloadBytes)
            }
        }
    }
}

private func benchmark(_ scenario: String, iterations: Int, _ operation: () throws -> Int) throws {
    let started = DispatchTime.now().uptimeNanoseconds
    let bytes = try operation()
    let elapsed = DispatchTime.now().uptimeNanoseconds - started
    printResult(scenario: scenario, iterations: iterations, elapsed: elapsed, bytes: bytes)
}

private func benchmarkAsync(_ scenario: String, iterations: Int, _ operation: () async throws -> Int) async throws {
    let started = DispatchTime.now().uptimeNanoseconds
    let bytes = try await operation()
    let elapsed = DispatchTime.now().uptimeNanoseconds - started
    printResult(scenario: scenario, iterations: iterations, elapsed: elapsed, bytes: bytes)
}

private func printResult(scenario: String, iterations: Int, elapsed: UInt64, bytes: Int) {
    print("scenario=\(scenario) iterations=\(iterations) elapsed_ns=\(elapsed) ns_per_op=\(Double(elapsed) / Double(iterations)) bytes=\(bytes)")
}

private func runJSONEnvelopeDecode(iterations: Int) throws -> Int {
    let coding = APICodingConfig()
    let envelope = codeMessageDataEnvelope()
    let data = Data("{\"code\":0,\"message\":\"ok\",\"data\":{\"list\":[\"test_post\",\"swift\"],\"map\":{\"req2\":{\"haha\":7}}}}".utf8)
    var total = 0
    for _ in 0..<iterations {
        let response = try apiDecodeResponse(
            DemoTestPostResponse.self,
            from: data,
            envelope: envelope,
            routeID: "api.demo.post.testpost",
            coding: coding
        )
        total += response.list.count + (response.map["req2"]?.haha ?? 0)
    }
    return total
}

private func runByteStream(iterations: Int, payloadBytes: Int) async throws -> Int {
    let transport = benchmarkTransport(
        responseBody: Data(repeating: 0x61, count: payloadBytes),
        contentType: "application/octet-stream",
        byteStreamChunkSize: 4 * 1024
    )
    let request = APIRequest<APIStreamResponse>(
        routeID: "benchmark.byte_stream",
        method: "GET",
        path: "/byte-stream",
        responseMediaType: "application/octet-stream",
        responseKind: "byte_stream",
        responseEnvelope: APIResponseEnvelope(),
        decode: { value in try apiDecodeStreamResponse(value) }
    )
    var total = 0
    for _ in 0..<iterations {
        let response = try await transport.request(request)
        for try await chunk in response.body {
            total += chunk.count
        }
    }
    return total
}

private func runMultipartFile(iterations: Int, payloadBytes: Int) async throws -> Int {
    let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("api-blueprint-swift-runtime-bench-\(UUID().uuidString).bin")
    try Data(repeating: 0x62, count: payloadBytes).write(to: tempURL)
    defer {
        try? FileManager.default.removeItem(at: tempURL)
    }

    let transport = benchmarkTransport(
        responseBody: Data("ok".utf8),
        contentType: "application/octet-stream",
        byteStreamChunkSize: 16 * 1024
    )
    var total = 0
    for _ in 0..<iterations {
        BenchmarkURLProtocol.observedUploadBytes = 0
        let request = APIRequest<APIRawResponse>(
            routeID: "benchmark.multipart_file",
            method: "POST",
            path: "/multipart",
            multipart: [
                "title": "swift-runtime",
                "file": APIFilePart(fileURL: tempURL, filename: "payload.bin", contentType: "application/octet-stream"),
            ],
            responseMediaType: "application/octet-stream",
            responseKind: "bytes",
            responseEnvelope: APIResponseEnvelope(),
            decode: { value in try apiDecodeRawResponse(value) }
        )
        let response = try await transport.request(request)
        total += response.body.count + BenchmarkURLProtocol.observedUploadBytes
    }
    return total
}

private func runSSELimit(iterations: Int, payloadBytes: Int) async throws -> Int {
    let event = Data(("data: {\"text\":\"" + String(repeating: "s", count: payloadBytes) + "\"}\n\n").utf8)
    var failures = 0
    for _ in 0..<iterations {
        let bridge = apiHTTPEventStreamBridge(
            routeID: "benchmark.sse_limit",
            streamBufferLimit: 1,
            maxSSEEventBytes: 64,
            start: { onResponse, onData, onComplete in
                do {
                    try onResponse(okHTTPResponse(contentType: "text/event-stream"))
                    onData(event)
                    onComplete(nil)
                } catch {
                    onComplete(error)
                }
                return APIHTTPCancellable {}
            },
            decodeMessage: { value in String(describing: value) },
            decodeClose: { _ in APISocketCloseInfo() }
        )
        var iterator = bridge.messages.makeAsyncIterator()
        do {
            _ = try await iterator.next()
            throw BenchmarkFailure(message: "sse limit did not throw")
        } catch APITransportError.payloadTooLarge(let kind, _) where kind == "sse" {
            failures += 1
        }
    }
    return failures
}

private func runWebSocketLimit(iterations: Int, payloadBytes: Int) async throws -> Int {
    var failures = 0
    for _ in 0..<iterations {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 0.1
        let session = URLSession(configuration: configuration)
        let socket = session.webSocketTask(with: URL(string: "ws://127.0.0.1:9/benchmark")!)
        let bridge = apiHTTPWebSocketBridge(
            routeID: "benchmark.websocket_limit",
            socket: socket,
            coding: APICodingConfig(),
            streamBufferLimit: 1,
            maxWebSocketMessageBytes: 64,
            decodeMessage: { value in String(describing: value) },
            encodeMessage: { (_: String, _: APICodingConfig) in Data(repeating: 0x77, count: payloadBytes) },
            decodeClose: { _ in APISocketCloseInfo() }
        )
        do {
            try await bridge.send("oversized")
            throw BenchmarkFailure(message: "websocket limit did not throw")
        } catch APITransportError.payloadTooLarge(let kind, _) where kind == "websocket" {
            failures += 1
        }
        await bridge.close()
        session.invalidateAndCancel()
    }
    return failures
}

private func benchmarkTransport(
    responseBody: Data,
    contentType: String,
    byteStreamChunkSize: Int
) -> URLSessionAPITransport {
    BenchmarkURLProtocol.responseBody = responseBody
    BenchmarkURLProtocol.contentType = contentType
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [BenchmarkURLProtocol.self]
    let session = URLSession(configuration: configuration)
    return URLSessionAPITransport(
        config: HTTPAPIConfig(
            baseURL: URL(string: "https://benchmark.local")!,
            session: session,
            byteStreamChunkSize: byteStreamChunkSize,
            multipartMemoryThreshold: 1
        )
    )
}

private func okHTTPResponse(contentType: String) -> HTTPURLResponse {
    HTTPURLResponse(
        url: URL(string: "https://benchmark.local/stream")!,
        statusCode: 200,
        httpVersion: "HTTP/1.1",
        headerFields: ["content-type": contentType]
    )!
}

private func codeMessageDataEnvelope() -> APIResponseEnvelope {
    APIResponseEnvelope(
        name: "CodeMessageDataEnvelope",
        kind: "code_message_data",
        errorIdentity: "nested",
        successCode: 0,
        successMessage: "ok",
        fields: APIResponseEnvelopeFields(code: "code", message: "message", data: "data", error: "error", ok: "ok")
    )
}
"""


def run(ctx: SwiftRuntimeBenchmarkContext) -> SwiftRuntimeBenchmarkResult:
    if not _require_tool("swift"):
        print("\n== swift-runtime ==")
        print("missing required tool `swift` on PATH; install it or skip this benchmark.")
        return SwiftRuntimeBenchmarkResult(returncode=127)
    with tempfile.TemporaryDirectory(prefix="api-blueprint-swift-runtime-bench-") as raw_bench_dir:
        bench_dir = Path(raw_bench_dir)
        source_dir = bench_dir / "Sources" / "SwiftRuntimeBenchmark"
        source_dir.mkdir(parents=True, exist_ok=True)
        swift_package = ctx.repo_root / "examples" / "swift"
        package_path = str(swift_package).replace("\\", "\\\\").replace('"', '\\"')
        (bench_dir / "Package.swift").write_text(
            textwrap.dedent(
                f"""
                // swift-tools-version: 5.9
                import PackageDescription

                let package = Package(
                    name: "SwiftRuntimeBenchmark",
                    platforms: [.macOS(.v12)],
                    products: [
                        .executable(name: "SwiftRuntimeBenchmark", targets: ["SwiftRuntimeBenchmark"])
                    ],
                    dependencies: [
                        .package(path: "{package_path}")
                    ],
                    targets: [
                        .executableTarget(
                            name: "SwiftRuntimeBenchmark",
                            dependencies: [
                                .product(name: "ABClientRuntime", package: "swift"),
                                .product(name: "ABClientAPIRoutes", package: "swift")
                            ]
                        )
                    ]
                )
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (source_dir / "main.swift").write_text(
            textwrap.dedent(SWIFT_RUNTIME_BENCHMARK_SOURCE).strip() + "\n",
            encoding="utf-8",
        )
        command = [
            "swift",
            "run",
            "-c",
            "release",
            "SwiftRuntimeBenchmark",
            str(ctx.count),
            ",".join(ctx.scenarios),
            str(ctx.payload_bytes),
        ]
        result = _run(command, bench_dir, ctx.env)
        print("\n== swift-runtime ==")
        print(result.stdout + result.stderr, end="")
        return SwiftRuntimeBenchmarkResult(returncode=result.returncode)


def parse_scenarios(raw: str) -> tuple[str, ...]:
    if raw == "all":
        return SCENARIOS
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = [value for value in values if value not in SCENARIOS]
    if unknown:
        raise ValueError(f"unknown Swift runtime benchmark scenario: {', '.join(unknown)}")
    if not values:
        raise ValueError("at least one Swift runtime benchmark scenario is required")
    return values


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def _require_tool(binary: str) -> bool:
    return shutil.which(binary) is not None
