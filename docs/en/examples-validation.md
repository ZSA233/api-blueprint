# Examples Validation

`examples/` carries the public Blueprint, Wails, Kotlin, and gRPC examples. Most example directories are generated snapshots and should not be hand-edited for business logic.

## Sources And Snapshots

- `examples/blueprints/`: Blueprint source of truth.
- `examples/golang/`, `examples/typescript/`, `examples/kotlin/`: Blueprint generated snapshots.
- `examples/wails-harness/v2/`, `examples/wails-harness/v3/`: handwritten minimal Wails harnesses that consume shared generated artifacts.
- `examples/wails-hello/`: standalone Wails v3 hello example; `blueprints/` is the source of truth, `golang/` and `typescript/` are generated snapshots, and `app/` is a handwritten Wails app shell.
- `examples/grpc/protos/`: gRPC proto source of truth.
- `examples/grpc/go/`, `examples/grpc/python/`: gRPC generated snapshots.

## Common Commands

```sh
make example-compile-check
make example-refresh
make example-validation
make wails-hello-compile-check
make wails-hello-check
```

- `example-compile-check`: for feature development; allows snapshot drift and only verifies regenerated artifacts still compile or import.
- `example-refresh`: accepts intentional generation changes and refreshes committed snapshots.
- `example-validation`: strict mode; requires generator output and committed snapshots to converge.
- `wails-hello-compile-check`: validates only the standalone Wails hello example, allows snapshot drift, and is useful for fast development checks.
- `wails-hello-check`: strictly validates only the standalone Wails hello example, including regeneration, snapshot drift, TypeScript, Go, `wails3 doctor`, and `wails3 build`.

You can also use the script scope directly:

```sh
uv run python scripts/example_validation.py --scope wails-hello --mode check
uv run python scripts/example_validation.py --scope wails-hello --mode compile
uv run python scripts/example_validation.py --scope wails-hello --mode refresh
```

## Drift Meaning

Snapshot drift means the current generator output differs from committed snapshots. It is a change signal, not an automatic bug.

If the drift is intentional:

```sh
make example-refresh
make example-validation
```

If the drift is not intentional, fix the writer, template, DSL, or config layer instead of directly editing generated snapshots.

## External Toolchain

Strict examples validation may require:

- `go`
- `go-enum`
- `npm`
- Gradle or `API_BLUEPRINT_GRADLE_BIN`
- Wails v2 CLI `wails` or `API_BLUEPRINT_WAILS_V2_BIN`
- Wails v3 CLI `wails3` or `API_BLUEPRINT_WAILS_V3_BIN`
- `protoc`
- `protoc-gen-go`
- `protoc-gen-go-grpc`
- Python `grpc_tools`

## Release Requirement

`make release-preflight` must include strict `make example-validation`. Before release, all intentional snapshot changes should already have been accepted through `make example-refresh` and committed.
