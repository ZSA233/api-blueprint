# gRPC

`api-gen-grpc` orchestrates compilation for existing `.proto` trees. It does not generate proto/service definitions from the Blueprint DSL.

## Target Mode

Use `[grpc]` and `[[grpc.targets]]` as the primary mode:

```toml
[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["commonpb/common.proto", "greeterpb/greeter.proto"]

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "grpc/python"
files = ["**/*.proto"]
python_package_root = "examplegrpc_pb"
```

- `id`: used only for target selection.
- `source_root`: resolves `files` and acts as the `protoc` working root.
- `import_roots`: only extends proto import lookup.
- `out_dir`: final generated directory.
- `python_package_root`: applies only to Python targets.

## CLI

```sh
api-gen-grpc -c api-blueprint.toml --list-targets
api-gen-grpc -c api-blueprint.toml --target go.*
api-gen-grpc -c api-blueprint.toml --explain-target go.greeter
```

## Go Target

A Go target walks upward from `out_dir`, discovers the nearest `go.mod`, parses the module path, and validates selected proto `option go_package` values against the output directory.

Public target config no longer requires manual `module` or `layout`.

## Python Target

Python targets generate source-relative output by default.

When `python_package_root` is set, output lands deterministically under:

```text
out_dir/<python_package_root>/...
```

Generated-code imports also use that package root.

## Legacy Jobs

`[[grpc.jobs]]` remains available, but only as legacy/raw mode. Older configs can still use:

```sh
api-gen-grpc -c api-blueprint.toml --list-jobs
api-gen-grpc -c api-blueprint.toml --job legacy.name
```

## External Toolchain

- Python targets require `grpcio-tools`.
- Go targets require `protoc`, `protoc-gen-go`, and `protoc-gen-go-grpc` on `PATH`.
