.PHONY: sync test example-validation example-compile-check example-refresh wails-hello-dev wails-hello-check wails-hello-compile-check wails-hello-refresh build release-tag-check release-preflight release-local release-install-check release-version-show release-version-rc release-version-stable

RELEASE_TAG ?=
DIST_DIR ?= dist

sync:
	uv sync --dev

test:
	uv run pytest -q

example-validation:
	uv run python scripts/example_validation.py

example-compile-check:
	uv run python scripts/example_validation.py --mode compile

example-refresh:
	uv run python scripts/example_validation.py --mode refresh

wails-hello-dev:
	uv run api-gen generate -c examples/wails-hello/api-blueprint.toml --target hello.v3
	cd examples/wails-hello/app && wails3 task dev

wails-hello-check:
	uv run python scripts/example_validation.py --scope wails-hello --mode check

wails-hello-compile-check:
	uv run python scripts/example_validation.py --scope wails-hello --mode compile

wails-hello-refresh:
	uv run python scripts/example_validation.py --scope wails-hello --mode refresh

build:
	uv build --sdist --wheel

release-tag-check:
	@if [ -z "$(RELEASE_TAG)" ]; then echo "RELEASE_TAG is required" >&2; exit 1; fi
	uv run python scripts/release_version.py check-sync --tag "$(RELEASE_TAG)"
	uv run python scripts/release_assets.py validate-config
	uv run python scripts/release_assets.py validate-docs
	uv run python scripts/release_assets.py validate-release-version --tag "$(RELEASE_TAG)"

release-preflight:
	@if [ -z "$(RELEASE_TAG)" ]; then echo "RELEASE_TAG is required" >&2; exit 1; fi
	$(MAKE) release-tag-check RELEASE_TAG="$(RELEASE_TAG)"
	$(MAKE) test
	$(MAKE) example-validation

release-local:
	@if [ -z "$(RELEASE_TAG)" ]; then echo "RELEASE_TAG is required" >&2; exit 1; fi
	rm -rf "$(DIST_DIR)"
	uv build --sdist --wheel --out-dir "$(DIST_DIR)"

release-install-check:
	@if [ -z "$(RELEASE_TAG)" ]; then echo "RELEASE_TAG is required" >&2; exit 1; fi
	uv run python scripts/release_assets.py install-check --tag "$(RELEASE_TAG)" --dist-dir "$(DIST_DIR)"

release-version-show:
	uv run python scripts/release_version.py show

release-version-rc:
	@if [ -z "$(BASE_VERSION)" ] || [ -z "$(RC)" ]; then \
		echo "Usage: make release-version-rc BASE_VERSION=<version> RC=<number> [CHECK=1]" >&2; \
		exit 2; \
	fi
	uv run python scripts/release_version.py set-rc --base "$(BASE_VERSION)" --rc "$(RC)" $(if $(filter 1,$(CHECK)),--check)

release-version-stable:
	@if [ -z "$(BASE_VERSION)" ]; then \
		echo "Usage: make release-version-stable BASE_VERSION=<version> [CHECK=1]" >&2; \
		exit 2; \
	fi
	uv run python scripts/release_version.py set-stable --base "$(BASE_VERSION)" $(if $(filter 1,$(CHECK)),--check)
