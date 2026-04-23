# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

🌍 Language: [中文](README.md) | English

## Overview

`api-blueprint` is a project that connects a Python DSL, FastAPI/OpenAPI, and multi-language code generation.

Its main workflow is:

1. Describe `Blueprint`, routes, request/response models, and error structures in Python.
2. Build a FastAPI application at runtime and expose OpenAPI documentation.
3. Generate Go and TypeScript code snapshots from the same blueprint source.
4. Compile existing `.proto` trees from gRPC targets declared in `api-blueprint.toml`, while still supporting legacy/raw job mode.

## Supported Outputs

| Target | Status | Command | Example Directory |
|:---|:---:|:---|:---|
| Go | Available | `api-gen-golang` | `examples/golang` |
| gRPC | Available | `api-gen-grpc` | `examples/grpc/{go,python}` |
| TypeScript | Preview | `api-gen-typescript` | `examples/typescript` |

Kotlin / Java are not exposed as public commands yet; they remain internal extension points only.

## Installation

This repository currently maintains a GitHub-only install entrypoint; the stable install path is fixed to the `stable` branch.

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## Core Workflow

- Define `Blueprint` objects and route DSLs in directories such as `examples/blueprints/`.
- Use `examples/grpc/` as the public proto and committed Go / Python gRPC snapshot example; its `[grpc]` settings share the same `examples/api-blueprint.toml` file as the Blueprint examples.
- Build the documentation service with `api-doc-server`, reusing FastAPI OpenAPI output.
- Generate language-side snapshot artifacts with `api-gen-golang` and `api-gen-typescript`.
- Compile existing proto trees through `api-gen-grpc` targets; when you need older config semantics, legacy/raw jobs are still available.
- During feature work, use `make example-compile-check` to regenerate the Blueprint and gRPC examples and verify their compile/import smoke checks still pass.
- When the generator change is intentional, use `make example-refresh` to refresh the committed example snapshots.
- When you need strict snapshot convergence, use `make example-validation`.

## Configuration File

```toml
[blueprint]
docs_server = '0.0.0.0:2332'
docs_domain = ''
entrypoints = [
    'blueprints.app:*',
]

[golang]
codegen_output = 'golang'
upstream = 'http://localhost:2333'
module = ''

[typescript]
codegen_output = 'typescript'
upstream = 'http://localhost:2333'
# literal URL fallback
base_url = 'http://localhost:2333'
# raw runtime expression, mutually exclusive with base_url
# base_url_expr = 'import.meta.env.VITE_API_BASE_URL'

[grpc]
source_root = 'grpc/protos'
import_roots = []

[[grpc.targets]]
id = 'python.greeter'
lang = 'python'
out_dir = 'grpc/python'
files = ['**/*.proto']
python_package_root = 'examplegrpc_pb'

[[grpc.targets]]
id = 'go.greeter'
lang = 'go'
out_dir = 'grpc/go'
files = [
    'commonpb/common.proto',
    'greeterpb/greeter.proto',
]
```

## gRPC Semantic Model

- `id` is only used to select a target through `--target`, `--list-targets`, and `--explain-target`.
- `source_root` only defines how `files` are resolved and where `protoc` runs.
- `import_roots` only affects proto import lookup.
- `python_package_root` only controls the Python output namespace and generated-code import path.
- `out_dir` always means the final generated directory and no longer means the Go module root.

### Advanced / Legacy Mode

- `[[grpc.jobs]]` is still supported, but it is kept only as legacy/raw mode and is no longer the primary README path.
- `--job` and `--list-jobs` remain available for older configs that still depend on `proto_root`, `include_paths`, `layout`, and `module`.

## Go Targets And Modules

- A Go target walks upward from `out_dir`, discovers the nearest `go.mod`, and parses the module path automatically.
- The tool derives the expected `go_package` import path prefix from `out_dir`, then validates every selected proto `option go_package`.
- Public config no longer requires manual `module` or `layout` fields; when `go_package` and `out_dir` disagree, the error reports `out_dir`, `module_root`, `module_path`, and the expected prefix directly.

## Python Source Root And Output Paths

- By default, a Python target uses `source_root` as the `grpc_tools.protoc` working root and its first `-I`, and generated files still follow source-relative layout.
- When `python_package_root` is set, `api-blueprint` stages a temporary proto tree, rewrites local imports, and uses a virtual include prefix so outputs land deterministically under `out_dir/<package_root>/...`.
- `import_roots` only extends proto lookup; it does not directly define the Python artifact namespace.

## Blueprint DSL Example

```python
from api_blueprint.includes import *
from blueprints.app import apibp


class ApiDemoSubA(Model):
    hello = Map[String, Int](description="hello")


class ApiDemoA(Model):
    bc = String(description="bc")
    a = Int(description="a")
    efg = Float32(description="efg")
    hijk = Array[Uint](description="hijk")
    lmnop = Array[ApiDemoSubA](description="lmnop", omitempty=True)


with apibp.group("/demo") as views:
    views.GET(
        "/abc",
        summary="这是 abc 的 summary",
        description="这是 abc 的 description",
    ).ARGS(
        arg1=Bool(description="arg1", default=True),
        arg2=Float(description="arg2", default=6.666),
    ).RSP(ApiDemoA)
```

## CLI Commands

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen-golang -c examples/api-blueprint.toml
api-gen-grpc -c examples/api-blueprint.toml --list-targets
api-gen-grpc -c examples/api-blueprint.toml --target go.*
api-gen-grpc -c examples/api-blueprint.toml --explain-target go.greeter
api-gen-grpc -c examples/api-blueprint.toml --list-jobs
api-gen-typescript -c examples/api-blueprint.toml
```

## Generated Artifacts And Repository Rules

- `examples/blueprints/` is the blueprint source of truth.
- `examples/golang/` and `examples/typescript/` are Blueprint snapshots and should not be hand-edited for business logic.
- `examples/grpc/protos/` is the gRPC example source of truth, and `examples/grpc/go/` and `examples/grpc/python/` are the corresponding generated snapshots.
- `api-gen-grpc` only orchestrates compilation for existing `.proto` trees; it does not derive gRPC proto/service definitions from the Blueprint DSL.
- `api-gen-grpc` can run with only the `[grpc]` section and does not require `[blueprint]`, `[golang]`, or `[typescript]`.
- `[typescript]` supports both literal `base_url` values and raw TypeScript `base_url_expr` expressions; they are mutually exclusive, and resolution order is fixed as `base_url_expr -> base_url -> upstream -> ""`.
- Python gRPC targets require `grpcio-tools`; Go gRPC targets require `protoc`, `protoc-gen-go`, and `protoc-gen-go-grpc` on `PATH`; `grpcio-tools` is not a runtime dependency.
- `[[grpc.targets]].python_package_root` only applies to Python targets; when it is set, the public Python gRPC snapshots are generated under `examples/grpc/python/examplegrpc_pb/...`.
- legacy/raw `[[grpc.jobs]]` still resolves proto expansion from `proto_root` by default; Go legacy jobs still support `layout = "go_package"` and `module`, while Python legacy jobs still do not.
- `Blueprint(app=None)` shares the global `FastAPI` app by default; if you need separate documentation apps, you must pass `app` explicitly.
- Example snapshot drift means the current generator output differs from the committed snapshots; it is a change signal, not an automatic bug.
- `make example-compile-check` allows drift and only checks whether regenerated outputs still compile.
- `make example-refresh` accepts intentional changes and refreshes the committed example snapshots in place.
- `make example-validation` wraps the strict mode of `scripts/example_validation.py`, regenerates the Blueprint and gRPC examples in a temporary workspace, then runs snapshot diffs, `tsc --noEmit`, `go test ./...`, and a Python gRPC import smoke check.
- Strict Blueprint example regeneration depends on `go-enum`; the gRPC example flow depends on `protoc`, `protoc-gen-go`, `protoc-gen-go-grpc`, and Python `grpc_tools`.
- `make release-preflight` must include strict `make example-validation`, because by release time any intentional snapshot drift should already have been accepted and committed.
- `examples/api-blueprint.toml` carries the public shared example config for both Blueprint and gRPC, and `examples/grpc/go/` plus `examples/grpc/python/` are part of the committed examples snapshot contract.
- `main.py` and `debug.py` are kept only as local helper scripts and are not part of the public release surface.

## Development

```sh
make sync
make test
make example-compile-check
make example-refresh
make example-validation
make build
```

## Release

- The documentation convergence order is fixed as `PRE_README.MD -> README.md -> README_EN.md`.
- The version source of truth is fixed as `release-version.toml` and `src/api_blueprint/_version.py`.
- `make release-preflight` runs the release contract checks together with `make test` and `make example-validation`.
- If release-preflight finds intentional example drift, run `make example-refresh`, review and commit the updated snapshots, then rerun `make release-preflight`.
- The stable release workflow is bound to the GitHub `production` environment; if that environment has required reviewers configured, publication pauses for manual approval.
- See [`docs/release-process.md`](docs/release-process.md) for the detailed release rules.

```sh
make release-version-show
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
