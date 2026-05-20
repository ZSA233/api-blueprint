.PHONY: example-validation example-compile-check example-refresh example-conformance example-conformance-list example-conformance-generate example-conformance-run example-conformance-check example-conformance-refresh example-golang-suite example-java-suite

example-validation:
	uv run python scripts/example_validation.py

example-compile-check:
	uv run python scripts/example_validation.py --mode compile

example-refresh:
	uv run python scripts/example_validation.py --mode refresh

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
