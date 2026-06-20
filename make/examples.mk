.PHONY: example-validation example-compile-check example-refresh example-refresh-go-server example-validation-go-server example-conformance example-conformance-list example-conformance-generate example-conformance-run example-conformance-check example-conformance-refresh example-golang-suite example-java-suite example-java-spring-server example-java-spring-server-benchmark

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

example-validation-go-server:
	uv run python scripts/example_validation.py --target go.server

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
