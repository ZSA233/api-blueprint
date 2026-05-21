# Benchmarks

Benchmarks are opt-in trend tools for investigating generated-artifact performance regressions. They are not default CI thresholds. They share generated workspaces and server runners with examples conformance, so they measure the real protocol path of the current generated examples.

## Common Commands

```sh
uv run python -m scripts.example_benchmark list
uv run python -m scripts.example_benchmark binary --target go --count 10000
uv run python -m scripts.example_benchmark protocol --servers go --scenario rpc-json,binary --requests 1000 --concurrency 16 --warmup 100
uv run python -m scripts.example_benchmark sdk-smoke --servers go --clients python --scenario request-options,binary-response,media
```

The Makefile provides thin wrappers:

```sh
make benchmark-list
make benchmark-binary BINARY_BENCH_TARGET=go BINARY_BENCH_COUNT=10000
make example-benchmark-protocol EXAMPLE_BENCH_SERVERS=go,python EXAMPLE_BENCH_SCENARIOS=rpc-json,binary
make example-benchmark
```

## Binary Codec

The `binary` subcommand migrates the older `scripts/benchmark_binary.py` / `scripts/benchmark_binary_client.py` flow and compares generated binary schema codec read/write cost.

```sh
uv run python -m scripts.example_benchmark binary --target go,typescript,python,kotlin,java --count 10000
```

- `--target` supports `go`, `typescript`, `python`, `kotlin`, `java`, and `all`.
- `--count` controls the operation count per target.
- `--compare-head` keeps the older Go target HEAD comparison.
- The old scripts remain compatibility wrappers; new calls should prefer `python -m scripts.example_benchmark binary`.

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
EXAMPLE_BENCH_SERVERS ?= go
EXAMPLE_BENCH_SCENARIOS ?= rpc-json,binary
EXAMPLE_BENCH_REQUESTS ?= 1000
EXAMPLE_BENCH_CONCURRENCY ?= 16
EXAMPLE_BENCH_WARMUP ?= 100
EXAMPLE_BENCH_KEEP_WORKSPACE ?= 0
```

`EXAMPLE_BENCH_KEEP_WORKSPACE=1` passes `--keep-workspace` and keeps the generated temporary directory.
