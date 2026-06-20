.PHONY: help sync test benchmark-list benchmark-binary benchmark-swift-runtime example-benchmark-protocol example-benchmark build

help:
	@printf "%s\n" \
		"Usage: make <target>" \
		"" \
		"Core:" \
		"  make sync                    Install development dependencies" \
		"  make test                    Run Python tests" \
		"  make build                   Build sdist and wheel" \
		"  make benchmark-list          List generated example benchmark targets" \
		"  make benchmark-binary        Run binary codec benchmark" \
		"  make benchmark-swift-runtime Run Swift runtime microbenchmarks" \
		"  make example-benchmark-protocol" \
		"  make example-benchmark       Run binary and protocol benchmarks" \
		"" \
		"Examples:" \
		"  make example-compile-check   Compile regenerated examples without drift enforcement" \
		"  make example-refresh         Refresh committed example snapshots" \
		"  make example-refresh-go-server Refresh Go server example snapshots only" \
		"  make example-validation      Run strict example validation" \
		"  make example-validation-go-server Validate Go server example snapshots only" \
		"  make example-conformance     Run generated example interoperability checks" \
		"  make example-conformance-list" \
		"  make example-conformance-run EXAMPLE_CONFORMANCE_SERVERS=go EXAMPLE_CONFORMANCE_CLIENTS=flutter EXAMPLE_CONFORMANCE_SCENARIOS=sse,websocket" \
		"  make example-conformance-check EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all" \
		"" \
		"Wails:" \
		"  make wails-hello-dev" \
		"  make wails-hello-check" \
		"  make wails-hello-compile-check" \
		"" \
		"Release:" \
		"  make release-version-show" \
		"  make release-preflight RELEASE_TAG=vX.Y.Z" \
		"  make release-local RELEASE_TAG=vX.Y.Z" \
		"  make release-install-check RELEASE_TAG=vX.Y.Z"

sync:
	uv sync --dev

test:
	uv run pytest -q

benchmark-list:
	uv run python -m scripts.example_benchmark list

benchmark-binary:
	uv run python scripts/benchmark_binary.py --target "$(BINARY_BENCH_TARGET)" --count "$(BINARY_BENCH_COUNT)" $(if $(filter 1,$(BINARY_BENCH_COMPARE_HEAD)),--compare-head)

benchmark-swift-runtime:
	uv run python -m scripts.example_benchmark swift-runtime --scenario "$(SWIFT_RUNTIME_BENCH_SCENARIOS)" --count "$(SWIFT_RUNTIME_BENCH_COUNT)" --payload-bytes "$(SWIFT_RUNTIME_BENCH_PAYLOAD_BYTES)"

example-benchmark-protocol:
	uv run python -m scripts.example_benchmark protocol --servers "$(EXAMPLE_BENCH_SERVERS)" --scenario "$(EXAMPLE_BENCH_SCENARIOS)" --requests "$(EXAMPLE_BENCH_REQUESTS)" --concurrency "$(EXAMPLE_BENCH_CONCURRENCY)" --warmup "$(EXAMPLE_BENCH_WARMUP)" $(if $(filter 1,$(EXAMPLE_BENCH_KEEP_WORKSPACE)),--keep-workspace)

example-benchmark:
	$(MAKE) benchmark-binary
	$(MAKE) example-benchmark-protocol

build:
	uv build --sdist --wheel
