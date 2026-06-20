.PHONY: example-validation example-compile-check example-refresh example-refresh-go-server example-refresh-go-client example-refresh-typescript example-refresh-python example-refresh-kotlin example-refresh-java example-refresh-flutter example-refresh-swift example-refresh-grpc example-refresh-wails example-refresh-wails-hello example-validation-go-server example-validation-go-client example-validation-typescript example-validation-python example-validation-kotlin example-validation-java example-validation-flutter example-validation-swift example-validation-grpc example-validation-wails example-validation-wails-hello example-conformance example-conformance-list example-conformance-generate example-conformance-run example-conformance-check example-conformance-refresh example-golang-suite example-java-suite example-java-spring-server example-java-spring-server-benchmark

JAVA_SPRING_BENCH_ITERATIONS ?= 200000
JAVA_SPRING_BENCH_WARMUP ?= 20000
JAVA_SPRING_BENCH_CONTRACT_ITERATIONS ?= 1000
JAVA_SPRING_BENCH_CONTRACT_WARMUP ?= 20

example-validation:
	uv run python scripts/example_validation.py

example-compile-check:
	uv run python scripts/example_validation.py --mode compile

example-refresh:
	uv run python scripts/example_validation.py --mode refresh

example-refresh-go-server:
	uv run python scripts/example_validation.py --mode refresh --target go.server

example-refresh-go-client:
	uv run python scripts/example_validation.py --mode refresh --target go.client

example-refresh-typescript:
	uv run python scripts/example_validation.py --mode refresh --target typescript.client

example-refresh-python:
	uv run python scripts/example_validation.py --mode refresh --target python.http

example-refresh-kotlin:
	uv run python scripts/example_validation.py --mode refresh --target kotlin.http

example-refresh-java:
	uv run python scripts/example_validation.py --mode refresh --target java.http

example-refresh-flutter:
	uv run python scripts/example_validation.py --mode refresh --target flutter.client

example-refresh-swift:
	uv run python scripts/example_validation.py --mode refresh --target swift.client

example-refresh-grpc:
	uv run python scripts/example_validation.py --mode refresh --target grpc

example-refresh-wails:
	uv run python scripts/example_validation.py --mode refresh --target wails.blueprint

example-refresh-wails-hello:
	uv run python scripts/example_validation.py --mode refresh --target wails.hello

example-validation-go-server:
	uv run python scripts/example_validation.py --target go.server

example-validation-go-client:
	uv run python scripts/example_validation.py --target go.client

example-validation-typescript:
	uv run python scripts/example_validation.py --target typescript.client

example-validation-python:
	uv run python scripts/example_validation.py --target python.http

example-validation-kotlin:
	uv run python scripts/example_validation.py --target kotlin.http

example-validation-java:
	uv run python scripts/example_validation.py --target java.http

example-validation-flutter:
	uv run python scripts/example_validation.py --target flutter.client

example-validation-swift:
	uv run python scripts/example_validation.py --target swift.client

example-validation-grpc:
	uv run python scripts/example_validation.py --target grpc

example-validation-wails:
	uv run python scripts/example_validation.py --target wails.blueprint

example-validation-wails-hello:
	uv run python scripts/example_validation.py --target wails.hello

example-conformance:
	@$(MAKE) example-conformance-check

example-conformance-list:
	@uv run python -m scripts.example_conformance list

example-conformance-generate:
	@uv run python -m scripts.example_conformance generate $(EXAMPLE_CONFORMANCE_KEEP_ARG)

example-conformance-run:
	@uv run python -m scripts.example_conformance run $(EXAMPLE_CONFORMANCE_MATRIX_ARGS) $(EXAMPLE_CONFORMANCE_KEEP_ARG)

example-conformance-check:
	@uv run python -m scripts.example_conformance check $(EXAMPLE_CONFORMANCE_MATRIX_ARGS) $(EXAMPLE_CONFORMANCE_KEEP_ARG)

example-conformance-refresh:
	@uv run python -m scripts.example_conformance refresh $(EXAMPLE_CONFORMANCE_MATRIX_ARGS)

example-golang-suite:
	uv run python scripts/example_validation.py --scope blueprint --mode golang-suite

example-java-suite:
	uv run python scripts/example_validation.py --scope blueprint --mode java-suite

example-java-spring-server:
	uv run api-gen check -c examples/java/spring-server/api-blueprint.toml
	uv run api-gen generate -c examples/java/spring-server/api-blueprint.toml --target java.server
	gradle_bin="$${API_BLUEPRINT_GRADLE_BIN:-gradle}"; \
	cd examples/java/spring-server && "$$gradle_bin" --no-daemon test

example-java-spring-server-benchmark:
	uv run api-gen check -c examples/java/spring-server/api-blueprint.toml
	uv run api-gen generate -c examples/java/spring-server/api-blueprint.toml --target java.server
	gradle_bin="$${API_BLUEPRINT_GRADLE_BIN:-gradle}"; \
	cd examples/java/spring-server && "$$gradle_bin" --no-daemon benchmark \
		-PbenchmarkIterations="$(JAVA_SPRING_BENCH_ITERATIONS)" \
		-PbenchmarkWarmup="$(JAVA_SPRING_BENCH_WARMUP)" \
		-PbenchmarkContractIterations="$(JAVA_SPRING_BENCH_CONTRACT_ITERATIONS)" \
		-PbenchmarkContractWarmup="$(JAVA_SPRING_BENCH_CONTRACT_WARMUP)"
