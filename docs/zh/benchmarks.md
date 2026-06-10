# Benchmark

benchmark 是可选趋势工具，用于排查生成物性能回归，不作为默认 CI 阈值。它和 examples conformance 共享生成 workspace 与 server runner，因此测的是当前 examples 生成物的真实协议路径。

## 常用命令

```sh
uv run python -m scripts.example_benchmark list
uv run python -m scripts.example_benchmark binary --target go --count 10000
uv run python -m scripts.example_benchmark protocol --servers go --scenario rpc-json,binary --requests 1000 --concurrency 16 --warmup 100
uv run python -m scripts.example_benchmark sdk-smoke --servers go --clients python --scenario request-options,binary-response,media
uv run python -m scripts.example_benchmark swift-runtime --scenario all --count 100
```

Makefile 提供薄封装：

```sh
make benchmark-list
make benchmark-binary BINARY_BENCH_TARGET=go BINARY_BENCH_COUNT=10000
make benchmark-swift-runtime SWIFT_RUNTIME_BENCH_SCENARIOS=json-envelope,byte-stream
make example-benchmark-protocol EXAMPLE_BENCH_SERVERS=go,python EXAMPLE_BENCH_SCENARIOS=rpc-json,binary
make example-benchmark
make example-java-spring-server-benchmark
```

## Binary Codec

`binary` 子命令迁移自旧的 `scripts/benchmark_binary.py` / `scripts/benchmark_binary_client.py`，用于比较生成的 binary schema codec 读写成本。

```sh
uv run python -m scripts.example_benchmark binary --target go,typescript,python,kotlin,java,swift --count 10000
```

- `--target` 支持 `go`、`typescript`、`python`、`kotlin`、`java`、`swift` 和 `all`。
- `--count` 控制每个 target 的操作次数。
- `--compare-head` 保留 Go target 的旧 HEAD 对比能力。
- Swift benchmark 会创建临时 SwiftPM executable，依赖当前 `examples/swift` 的 `ABClientAPIRoutes` product，并要求本机可用 `swift` toolchain。
- 旧脚本仍作为兼容 wrapper 保留，推荐新调用使用 `python -m scripts.example_benchmark binary`。

## Swift Runtime

`swift-runtime` 子命令创建临时 SwiftPM executable，依赖当前 `examples/swift` 的 `ABClientRuntime` 与 `ABClientAPIRoutes` product，测 Swift generated runtime 的本地微基准路径。

```sh
uv run python -m scripts.example_benchmark swift-runtime \
  --scenario json-envelope,byte-stream,multipart-file,sse-limit,websocket-limit \
  --count 100 \
  --payload-bytes 262144
```

- `--scenario` 支持 `json-envelope`、`byte-stream`、`multipart-file`、`sse-limit`、`websocket-limit` 和 `all`。
- `--count` 是每个场景的操作次数。
- `--payload-bytes` 控制 byte stream、multipart file、SSE/WebSocket payload limit 的 payload 大小。
- 该 benchmark 只测本地 runtime 热路径，不启动真实 server，不覆盖登录、重试、缓存或 session lifecycle。
- 输出字段包括 `scenario`、`iterations`、`elapsed_ns`、`ns_per_op` 和 `bytes`，用于同机同 target 趋势对比。

## Java Spring Contract Boundary

Java Spring benchmark 位于 `examples/java/spring-server`，用于比较 generated Controller -> delegate 调用和普通 Spring 风格 Controller 方法。它不启动 HTTP server；它只跑本地 handler 调用、Spring merged annotation 查询，以及针对轻量 `RequestMappingHandlerMapping` 的 generated contract assertion 扫描。

```sh
make example-java-spring-server-benchmark
make example-java-spring-server-benchmark \
  JAVA_SPRING_BENCH_ITERATIONS=20000 \
  JAVA_SPRING_BENCH_WARMUP=2000 \
  JAVA_SPRING_BENCH_CONTRACT_ITERATIONS=100 \
  JAVA_SPRING_BENCH_CONTRACT_WARMUP=5
```

- `handler.generated-controller-delegate` 调用 generated Controller 和 delegate 实现。
- `handler.plain-spring-annotation` 调用同形态方法，但直接使用 Spring 注解。
- `annotation-lookup.generated-meta` 和 `annotation-lookup.plain-direct` 对比 Spring `AnnotatedElementUtils` 查询 generated Controller 方法与直接注解方法的成本。
- `contract-assertion.inspect` 测 generated 测试/CI 断言扫描成本，不在生产请求热路径上。
- 输出只作为同机趋势信号；直接 handler 调用里 ns 级的小波动不应被解释为业务请求延迟差异。

## Protocol

`protocol` 子命令复用 example conformance 的临时 workspace、工具检查和 Go / Java / Kotlin / Python server runner。它用 `httpx.AsyncClient` 直接压测生成服务端的 HTTP 协议路径，不通过生成客户端。

```sh
uv run python -m scripts.example_benchmark protocol \
  --servers go,java,kotlin,python \
  --scenario rpc-json,form,binary,typed-error \
  --requests 1000 \
  --concurrency 16 \
  --warmup 100
```

- `--servers` 支持 `go`、`java`、`kotlin`、`python` 和 `all`。
- `--scenario` 支持 `rpc-json`、`form`、`binary`、`typed-error`。
- `--requests` 是每个 server/scenario 的计量请求数。
- `--concurrency` 是最大并发请求数。
- `--warmup` 是计量前预热请求数。
- `--keep-workspace` 保留临时 workspace，便于排查失败。

输出字段包括 `requests`、`concurrency`、`warmup`、`elapsed`、`req/s`、`p50`、`p95`、`p99` 和 `errors`。这些数值受本机 CPU、JVM 冷启动、网络栈、Python event loop 和依赖缓存影响，不应直接作为跨机器硬阈值。

## SDK Smoke

`sdk-smoke` 子命令复用 example conformance runner，但定位是 generated client SDK 最小热路径 smoke，而不是吞吐压测。它适合在改动 request options、binary response、multipart/raw response 或 HTTP adapter 时快速确认生成客户端仍能真实调用服务端。

```sh
uv run python -m scripts.example_benchmark sdk-smoke \
  --servers go \
  --clients python \
  --scenario request-options,binary-response,media
```

- `--servers`、`--clients` 与 `--scenario` 使用 conformance 的同一套过滤语义。
- 默认场景是 `request-options,binary-response,media`。
- `--keep-workspace` 保留临时 workspace，便于排查失败。

## 环境变量

Makefile 默认值：

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

`EXAMPLE_BENCH_KEEP_WORKSPACE=1` 会传递 `--keep-workspace`，用于保留生成后的临时目录。
