# Benchmarks

Benchmarks are opt-in trend tools for investigating generated-artifact performance regressions. They are not default CI thresholds. They share generated workspaces and server runners with examples conformance, so they measure the real protocol path of the current generated examples.

## Common Commands

```sh
uv run python -m scripts.example_benchmark list
uv run python -m scripts.example_benchmark binary --target go --count 10000
uv run python -m scripts.example_benchmark protocol --servers go --scenario rpc-json,binary --requests 1000 --concurrency 16 --warmup 100
uv run python -m scripts.example_benchmark sdk-smoke --servers go --clients python --scenario request-options,binary-response,media
uv run python -m scripts.example_benchmark swift-runtime --scenario all --count 100
```

The Makefile provides thin wrappers:

```sh
make benchmark-list
make benchmark-binary BINARY_BENCH_TARGET=go BINARY_BENCH_COUNT=10000
make benchmark-swift-runtime SWIFT_RUNTIME_BENCH_SCENARIOS=json-envelope,byte-stream
make example-benchmark-protocol EXAMPLE_BENCH_SERVERS=go,python EXAMPLE_BENCH_SCENARIOS=rpc-json,binary
make example-benchmark
make example-java-spring-server-benchmark
```

## Binary Codec

The `binary` subcommand migrates the older `scripts/benchmark_binary.py` / `scripts/benchmark_binary_client.py` flow and compares generated binary schema codec read/write cost.

```sh
uv run python -m scripts.example_benchmark binary --target go,typescript,python,kotlin,java,swift --count 10000
```

- `--target` supports `go`, `typescript`, `python`, `kotlin`, `java`, `swift`, and `all`.
- `--count` controls the operation count per target.
- `--compare-head` keeps the older Go target HEAD comparison.
- The Swift benchmark creates a temporary SwiftPM executable, depends on the current `examples/swift` `ABClientAPIRoutes` product, and requires a local `swift` toolchain.
- The old scripts remain compatibility wrappers; new calls should prefer `python -m scripts.example_benchmark binary`.

## Swift Runtime

The `swift-runtime` subcommand creates a temporary SwiftPM executable, depends on the current `examples/swift` `ABClientRuntime` and `ABClientAPIRoutes` products, and measures local microbenchmark paths in the generated Swift runtime.

```sh
uv run python -m scripts.example_benchmark swift-runtime \
  --scenario json-envelope,byte-stream,multipart-file,sse-limit,websocket-limit \
  --count 100 \
  --payload-bytes 262144
```

- `--scenario` supports `json-envelope`, `byte-stream`, `multipart-file`, `sse-limit`, `websocket-limit`, and `all`.
- `--count` is the operation count per scenario.
- `--payload-bytes` controls the payload size for byte stream, multipart file, and SSE/WebSocket payload-limit scenarios.
- This benchmark measures local runtime hot paths only. It does not start a real server and does not cover login, retry, cache, or session lifecycle behavior.
- Output fields include `scenario`, `iterations`, `elapsed_ns`, `ns_per_op`, and `bytes`, intended for same-machine same-target trend comparisons.

## Java Spring Contract Boundary

The Java Spring benchmark lives in `examples/java/spring-server` and compares the generated Controller -> delegate call with a plain Spring-style controller method. It does not start an HTTP server; it exercises local handler calls, Spring merged-annotation lookup, and generated contract assertion inspection against a lightweight `RequestMappingHandlerMapping`.

```sh
make example-java-spring-server-benchmark
make example-java-spring-server-benchmark \
  JAVA_SPRING_BENCH_ITERATIONS=20000 \
  JAVA_SPRING_BENCH_WARMUP=2000 \
  JAVA_SPRING_BENCH_CONTRACT_ITERATIONS=100 \
  JAVA_SPRING_BENCH_CONTRACT_WARMUP=5
```

- `handler.generated-controller-delegate` calls the generated Controller and delegate implementation.
- `handler.plain-spring-annotation` calls the same shape of method using direct Spring annotations.
- `annotation-lookup.generated-meta` and `annotation-lookup.plain-direct` measure Spring `AnnotatedElementUtils` lookup on the generated Controller method versus a direct annotation method.
- `contract-assertion.inspect` measures the generated test/CI assertion scan. This is not on the production request path.
- The output is a same-machine trend signal. Small nanosecond-level differences in direct handler calls should not be treated as product latency.

## Protocol

The `protocol` subcommand reuses the example conformance temporary workspace, tool checks, and Go / Java / Kotlin / Python server runners. It uses `httpx.AsyncClient` to benchmark generated server HTTP protocol paths directly instead of going through generated clients.

```sh
uv run python -m scripts.example_benchmark protocol \
  --servers go,java,kotlin,python \
  --scenario rpc-json,form,binary,typed-error \
  --requests 1000 \
  --concurrency 16 \
  --warmup 100
```

- `--servers` supports `go`, `java`, `kotlin`, `python`, and `all`.
- `--scenario` supports `rpc-json`, `form`, `binary`, and `typed-error`.
- `--requests` is the measured request count per server/scenario.
- `--concurrency` is the maximum concurrent request count.
- `--warmup` is the request count before measurement.
- `--keep-workspace` keeps the temporary workspace for failure investigation.

Output fields include `requests`, `concurrency`, `warmup`, `elapsed`, `req/s`, `p50`, `p95`, `p99`, and `errors`. These values depend on local CPU, JVM cold start, network stack, Python event loop, and dependency caches, so they should not be treated as cross-machine hard thresholds.

## SDK Smoke

The `sdk-smoke` subcommand reuses the example conformance runner, but it is a generated client SDK smoke path rather than a throughput benchmark. It is useful after changes to request options, binary responses, multipart/raw responses, or HTTP adapters because it proves generated clients can still call a real server.

```sh
uv run python -m scripts.example_benchmark sdk-smoke \
  --servers go \
  --clients python \
  --scenario request-options,binary-response,media
```

- `--servers`, `--clients`, and `--scenario` use the same filter semantics as conformance.
- The default scenarios are `request-options,binary-response,media`.
- `--keep-workspace` keeps the temporary workspace for failure investigation.

## Environment Variables

Makefile defaults:

```make
BINARY_BENCH_TARGET ?= go
BINARY_BENCH_COUNT ?= 10000
BINARY_BENCH_COMPARE_HEAD ?= 0
SWIFT_RUNTIME_BENCH_SCENARIOS ?= all
SWIFT_RUNTIME_BENCH_COUNT ?= 100
SWIFT_RUNTIME_BENCH_PAYLOAD_BYTES ?= 262144
EXAMPLE_BENCH_SERVERS ?= go
EXAMPLE_BENCH_SCENARIOS ?= rpc-json,binary
EXAMPLE_BENCH_REQUESTS ?= 1000
EXAMPLE_BENCH_CONCURRENCY ?= 16
EXAMPLE_BENCH_WARMUP ?= 100
EXAMPLE_BENCH_KEEP_WORKSPACE ?= 0
JAVA_SPRING_BENCH_ITERATIONS ?= 200000
JAVA_SPRING_BENCH_WARMUP ?= 20000
JAVA_SPRING_BENCH_CONTRACT_ITERATIONS ?= 1000
JAVA_SPRING_BENCH_CONTRACT_WARMUP ?= 20
```

`EXAMPLE_BENCH_KEEP_WORKSPACE=1` passes `--keep-workspace` and keeps the generated temporary directory.
