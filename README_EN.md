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
4. Compile existing `.proto` trees into gRPC outputs from named jobs declared in `api-blueprint.toml`.

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
- Compile existing proto trees into Go / Python gRPC outputs with named jobs through `api-gen-grpc`.
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
proto_root = 'grpc/protos'
include_paths = []

[[grpc.jobs]]
name = 'python.greeter'
preset = 'python'
output = 'grpc/python'
# optional: override the per-job proto discovery / execution root
# proto_root = 'grpc/protos/services/exampledomain/api'
protos = ['**/*.proto']

[[grpc.jobs]]
name = 'go.greeter'
preset = 'go'
output = 'grpc/go'
# optional: write Go outputs by go_package instead of source-relative paths
# layout = 'go_package'
# module = 'examplemod'
protos = [
    'commonpb/common.proto',
    'greeterpb/greeter.proto',
]
```

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
api-gen-grpc -c examples/api-blueprint.toml --list-jobs
api-gen-grpc -c examples/api-blueprint.toml --job go.* --job python.greeter
api-gen-typescript -c examples/api-blueprint.toml
```

## Generated Artifacts And Repository Rules

- `examples/blueprints/` is the blueprint source of truth.
- `examples/golang/` and `examples/typescript/` are Blueprint snapshots and should not be hand-edited for business logic.
- `examples/grpc/protos/` is the gRPC example source of truth, and `examples/grpc/go/` and `examples/grpc/python/` are the corresponding generated snapshots.
- `api-gen-grpc` only orchestrates compilation for existing `.proto` trees; it does not derive gRPC proto/service definitions from the Blueprint DSL.
- `api-gen-grpc` can run with only the `[grpc]` section and does not require `[blueprint]`, `[golang]`, or `[typescript]`.
- `[typescript]` supports both literal `base_url` values and raw TypeScript `base_url_expr` expressions; they are mutually exclusive, and resolution order is fixed as `base_url_expr -> base_url -> upstream -> ""`.
- `[[grpc.jobs]].proto_root` inherits `[grpc].proto_root` by default; it overrides proto expansion, the `protoc` working root, and the source-relative output base for that specific job.
- Python gRPC jobs require `grpcio-tools`; Go gRPC jobs require `protoc`, `protoc-gen-go`, and `protoc-gen-go-grpc` on `PATH`; `grpcio-tools` is not a runtime dependency.
- Go gRPC jobs default to `layout = "source_relative"`; when you need direct `go_package`-based output, set `layout = "go_package"` and pass your own module name at the module root, for example `module = "examplemod"`.
- When a Go gRPC job sets `module`, `output` must point at the Go module root, not a leaf `pb/...` directory.
- Python gRPC jobs do not support `layout = "go_package"` or `module`.
- `[[grpc.jobs]].proto_root` is a per-job generation-root override, not a Python `module` or path-remap feature.
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
