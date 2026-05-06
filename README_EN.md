# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL, builds a unified `ContractGraph`, and generates a documentation service, Go server, TypeScript client, Kotlin Android client, Wails v2/v3 overlays, and gRPC proto/service definitions from the same protocol source of truth.

The DSL supports transport-neutral `STREAM` / `CHANNEL` long-connection message contracts alongside RPC; HTTP can map them to SSE / WebSocket, Wails maps them to session-scoped runtime events by default, and `CLOSE(Model)` generates a typed close lifecycle payload.

This README keeps only the onboarding path. See [Learn More](#learn-more) for full configuration, Wails, gRPC, DSL, and examples validation docs.

## Supported Outputs

| Target | Status | Command | Example |
|:---|:---:|:---|:---|
| Contract manifest | Available | `api-gen` | `api-blueprint.contract.json` |
| Go server | Available | `api-gen` | `examples/golang` |
| TypeScript client | Preview | `api-gen` | `examples/typescript` |
| Wails v3 | Experimental | `api-gen` | `examples/{golang,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | Preview | `api-gen` | `examples/{golang,typescript,wails-harness/v2}` |
| Kotlin Android client | Preview | `api-gen` | `examples/kotlin` |
| gRPC proto | Available | `api-gen` | `examples/grpc/protos` |


## Installation

The stable installation entrypoint points to the GitHub `stable` branch:

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## Quick Start

Define a Blueprint:

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class HelloResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(HelloResponse)
```

Create minimal config and generate code:

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client"]
```

```sh
api-doc-server -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

## Minimal Configuration

The following is a common multi-target config skeleton. See [Configuration](docs/en/configuration.md) for all fields.

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json", "markdown"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/project/golang"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client"]

[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"
```

## Common Commands

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen list-targets -c examples/api-blueprint.toml
api-gen explain-target -c examples/api-blueprint.toml --target go.server
api-gen manifest -c examples/api-blueprint.toml --out api-blueprint.contract.json
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
api-gen diff old.contract.json new.contract.json
```

## Generated Artifacts And User Files

- `examples/blueprints/` is the example Blueprint source of truth.
- `examples/blueprints/api_demo.py` includes `STREAM` / `CHANNEL` long-connection examples.
- `examples/golang/`, `examples/typescript/`, `examples/kotlin/`, and `examples/grpc/protos/` are generated snapshots.
- `examples/wails-hello/` is a standalone Wails v3 hello world example that demonstrates a GUI loop without starting an HTTP server.
- `gen_*` files are generator-owned and overwritten during regeneration.
- `impl_*` and non-`gen_*` passthrough files are user-owned extension points and are preserved during regeneration.
- Go / TypeScript artifacts use a `core + transports/<target>` layout; `api-gen generate --target wails.v3` does not generate a full Wails app shell, and external frontends must load the Wails runtime first.
- Wails target `include` / `exclude` trims target overlays / facades; roots with no selected routes do not get `transports/<overlay_name>` output, while shared contract layers are still generated in full.
- Go `views/providers` is a global runtime; use route-scoped provider factories when a provider implementation must vary by route. The user-owned hook is `SelectProvider(spec, handler)`. See the generator docs.
- `STREAM` / `CHANNEL` are the long-connection contract entrypoints; multi-message directions generate one discriminated union, while legacy `WS().RECV().SEND()` is outside the vNext mainline.
- The default HTTP/Wails runtimes fully support only `ConnectionScope.SESSION`; `APP` / `TOPIC` broadcast or topic routing can be added through a custom connection hub / manager.
- `examples/golang/views/routes/api/demo/impl.go` hand-writes a minimal `STREAM` / `CHANNEL` usage example that demonstrates `Open()`, `Send()`, `Recv()`, typed `Close()`, and exceptional `Abort()`.
- The Go HTTP adapter respects responses already written by Gin handlers, which fits small HTTP-only raw callbacks.
- The contract manifest records routes, schemas, connections, stable hashes, the resolved target plan, and the capability registry so AI agents can understand protocol boundaries.
- `[[targets]]` is the unified config entrypoint; transport targets use `kind = "http-transport"` / `kind = "wails-transport"` and explicitly declare `server` plus `clients`.
- gRPC proto is emitted by the `grpc-proto` target from ContractGraph; existing `.proto` trees are no longer an independent source of truth.

## Learn More

| Topic | Documentation |
|:---|:---|
| Getting started | [docs/en/getting-started.md](docs/en/getting-started.md) |
| Config fields | [docs/en/configuration.md](docs/en/configuration.md) |
| Blueprint DSL | [docs/en/blueprint-dsl.md](docs/en/blueprint-dsl.md) |
| Go / TypeScript / Kotlin | [docs/en/generators.md](docs/en/generators.md) |
| Wails | [docs/en/wails.md](docs/en/wails.md) |
| gRPC | [docs/en/grpc.md](docs/en/grpc.md) |
| Examples validation | [docs/en/examples-validation.md](docs/en/examples-validation.md) |
| Release process | [docs/release-process.md](docs/release-process.md) |

## Development

```sh
make sync
make test
make example-compile-check
make example-refresh
make example-validation
make wails-hello-dev
make wails-hello-check
```

`example-compile-check` is for development validation, `example-refresh` accepts intentional generation changes, and `example-validation` strictly confirms snapshot convergence. `wails-hello-dev` regenerates the hello overlay and starts the Wails v3 GUI; `wails-hello-check` strictly validates only the standalone hello example.

## Release

See [docs/release-process.md](docs/release-process.md) for the detailed release rules.

```sh
make release-version-show
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
