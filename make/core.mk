.PHONY: help sync test benchmark-binary build

help:
	@printf "%s\n" \
		"Usage: make <target>" \
		"" \
		"Core:" \
		"  make sync                    Install development dependencies" \
		"  make test                    Run Python tests" \
		"  make build                   Build sdist and wheel" \
		"  make benchmark-binary        Run binary codec benchmark" \
		"" \
		"Examples:" \
		"  make example-compile-check   Compile regenerated examples without drift enforcement" \
		"  make example-refresh         Refresh committed example snapshots" \
		"  make example-validation      Run strict example validation" \
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

benchmark-binary:
	uv run python scripts/benchmark_binary.py --target "$(BINARY_BENCH_TARGET)" --count "$(BINARY_BENCH_COUNT)" $(if $(filter 1,$(BINARY_BENCH_COMPARE_HEAD)),--compare-head)

build:
	uv build --sdist --wheel
