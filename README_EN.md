# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL, builds a unified `ContractGraph`, and generates a documentation service, Go server/client, TypeScript client, Kotlin Android client, Python client/server, Wails v2/v3 overlays, gRPC proto/service definitions, and protoc-backed Go/Python gRPC stubs from the same protocol source of truth and shared target planner.

The DSL supports transport-neutral `STREAM` / `CHANNEL` long-connection message contracts alongside RPC; HTTP can map them to SSE / WebSocket, Wails maps them to session-scoped runtime events with a client-allocated `session_id` handshake by default, and `CLOSE(Model)` generates a typed close lifecycle payload.

Long-connection routes also support `ConnectionDelivery`: the default is `ordered`. On HTTP, ordered delivery relies on the native per-connection ordering of SSE / WebSocket and does not add the Wails-style seq/reorder overlay; only ordered Wails routes add transport-level ordering and fail fast through a structured `onClose` when they hit an unrecoverable gap, protocol error, or buffer overflow, with application code deciding whether to reopen. `unordered` should be an explicit opt-in only for high-frequency telemetry-style flows, and it currently matters primarily for the Wails transport.

This README keeps only the onboarding path. See [Learn More](#learn-more) for full configuration, Wails, gRPC, DSL, and examples validation docs.

## Supported Outputs

| Target | Status | Command | Example |
|:---|:---:|:---|:---|
| Inspect / contract index | Available | `api-gen` | `api-gen inspect` / `api-blueprint.index.json` |
| Go server | Available | `api-gen` | `examples/golang/server` |
| Go client | Preview | `api-gen` | `examples/golang/client` |
| TypeScript client | Preview | `api-gen` | `examples/typescript` |
| Wails v3 | Experimental | `api-gen` | `examples/{golang/server,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | Preview | `api-gen` | `examples/{golang/server,typescript,wails-harness/v2}` |
| Kotlin Android client | Preview | `api-gen` | `examples/kotlin` |
| Python client/server | Preview | `api-gen` | `python_package_root` package layout |
| gRPC proto | Available | `api-gen` | `examples/grpc/protos` |
| gRPC Go/Python stubs | Available | `api-gen` | `examples/grpc/{go,python}` |


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

[[go.server]]
id = "go.server"
out_dir = "golang"

[[go.client]]
id = "go.client"
out_dir = "golang-client"
base_url = "http://localhost:2333"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[kotlin.client]]
id = "kotlin.client"
out_dir = "kotlin"
module = "com.example.apiblueprint"

[[python.server]]
id = "python.server"
out_dir = "python/server"
module = "api_blueprint_example_server"

[[python.client]]
id = "python.client"
out_dir = "python/client"
module = "api_blueprint_example_client"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client", "kotlin.client", "python.client"]
```

```sh
api-doc-server -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

`api-doc-server` prints the effective entry URL after startup; when `[blueprint].docs_server` uses `host:0`, the output shows the OS-assigned port rather than `:0`.

See the generator docs for extension points, file ownership, and output layout.

## Minimal Configuration

The following is a common multi-target config skeleton. See [Configuration](docs/en/configuration.md) for all fields.

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

[[contract]]
id = "contract"
out_dir = "."

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
module = "example.com/project/golang/server"

[[go.client]]
id = "go.client"
out_dir = "golang/client"
module = "example.com/project/golang/client"
base_url = "http://localhost:2333"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client"]

[[transport.wails]]
id = "wails.v3"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

[[grpc.proto]]
id = "grpc.proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[grpc.proto.proto_files]]
file = "api/demo/v1/demo.proto"
package = "example.api.demo.v1"
go_package = "example.com/project/grpc/go/api/demo/v1;demopb"
schema_modules = ["blueprints.api.demo"]
route_paths = ["/api/demo/v1/**"]
service = "DemoService"

[[grpc.go]]
id = "grpc.go"
proto = "grpc.proto"
out_dir = "grpc/go"
module = "example.com/project/grpc/go"
files = ["api/**/*.proto"]

[[grpc.python]]
id = "grpc.python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
module = "pb"
```

## Common Commands

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen list-targets -c examples/api-blueprint.toml
api-gen explain-target -c examples/api-blueprint.toml --target go.server
api-gen inspect routes -c examples/api-blueprint.toml
api-gen inspect route api.demo.post.testpost api.demo.channel.assistantsession -c examples/api-blueprint.toml
api-gen inspect files -c examples/api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession --target go.server
api-gen inspect schema ApiDemoA RSP_TestPost -c examples/api-blueprint.toml
api-gen inspect errors -c examples/api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession
api-gen manifest -c examples/api-blueprint.toml --out api-blueprint.index.json
api-gen manifest -c examples/api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c examples/api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c examples/api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
api-gen diff old.contract.json new.contract.json
```

## Learn More

| Topic | Documentation |
|:---|:---|
| Getting started | [docs/en/getting-started.md](docs/en/getting-started.md) |
| Config fields | [docs/en/configuration.md](docs/en/configuration.md) |
| Blueprint DSL | [docs/en/blueprint-dsl.md](docs/en/blueprint-dsl.md) |
| Go / TypeScript / Kotlin / Python | [docs/en/generators.md](docs/en/generators.md) |
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
make release-preflight RELEASE_TAG=v1.0.0
make release-local RELEASE_TAG=v1.0.0
make release-install-check RELEASE_TAG=v1.0.0
```
