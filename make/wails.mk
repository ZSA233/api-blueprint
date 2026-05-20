.PHONY: wails-hello-dev wails-hello-check wails-hello-compile-check wails-hello-refresh

wails-hello-dev:
	uv run api-gen generate -c examples/wails-hello/api-blueprint.toml --target hello.v3
	cd examples/wails-hello/app && wails3 task dev

wails-hello-check:
	uv run python scripts/example_validation.py --scope wails-hello --mode check

wails-hello-compile-check:
	uv run python scripts/example_validation.py --scope wails-hello --mode compile

wails-hello-refresh:
	uv run python scripts/example_validation.py --scope wails-hello --mode refresh
