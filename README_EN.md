# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL, builds a unified `ContractGraph`, and generates a documentation service, Go server/client, TypeScript client, Kotlin Android client, Python client/server, Wails v2/v3 overlays, gRPC proto/service definitions, and protoc-backed Go/Python gRPC stubs from the same protocol source of truth and shared target planner.

The DSL supports transport-neutral `STREAM` / `CHANNEL` long-connection message contracts alongside RPC; HTTP can map them to SSE / WebSocket, Wails maps them to session-scoped runtime events by default, and `CLOSE(Model)` generates a typed close lifecycle payload.

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

For TypeScript, Kotlin, and Python clients, `base_url` / `base_url_expr` are owned by the HTTP transport adapter / factory; shared route/runtime clients stay transport-neutral.

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

## Generated Artifacts And User Files

- `examples/blueprints/` is the example Blueprint source of truth.
- `examples/blueprints/api_demo.py` includes `STREAM` / `CHANNEL` long-connection examples.
- `examples/golang/server/`, `examples/golang/client/`, `examples/typescript/`, `examples/kotlin/`, `examples/api-blueprint.index.json`, optional contract/agent/shard snapshots, `examples/grpc/protos/`, `examples/grpc/go/`, and `examples/grpc/python/` are generated snapshots.
- `examples/wails-hello/` is a standalone Wails v3 hello world example that demonstrates a GUI loop without starting an HTTP server.
- Go / TypeScript / Python `gen_*` files are generator-owned and overwritten during regeneration; Kotlin `Gen*.kt` files are generator-owned and include a generated header.
- `impl_*`, Python `client.py` / `service.py`, and Kotlin non-`Gen*` façade/extension files are user-owned extension points and are preserved during regeneration.
- Go server `out_dir` is the generated package root and no longer appends `views` implicitly. The example uses `golang/server/views`, so server artifacts live under `views/routes`, `views/providers`, `views/runtime/errors`, and `views/transports`. Go client artifacts use `runtime`, `routes/<root>/<group...>`, and `transports/http`, with `base_url` owned only by the HTTP transport config. Kotlin uses the new `<package>/<root>/runtime`, `<package>/<root>/routes/<root>/<group...>`, and `<package>/<root>/transports/http` layout, and the old `<package>/ApiClient.kt`, `endpoints/`, `models/`, and `internal/` layout is a breaking change.
- Python client/server use `python_package_root` as the package root; route output mirrors the full path, for example `routes/api/demo`, root-level routes live in `routes/api`, and `routes/root` is no longer used. The client is async-first over HTTP, and the server emits route service contracts/stubs plus a FastAPI HTTP adapter scaffold.
- `api-gen check` and writers share planner / capability metadata; contract / agent artifact indexes point to the new Kotlin / Python full route path outputs.
- `api-gen generate --target wails.v3` does not generate a full Wails app shell, and external frontends must load the Wails runtime first; Wails targets still combine only a Go server and TypeScript client.
- Wails target `include` / `exclude` trims target overlays / facades; roots with no selected routes do not get `transports/<overlay_name>` output, while shared contract layers are still generated in full.
- Go `providers` is a global runtime under the generated package root; use route-scoped provider factories when a provider implementation must vary by route. The user-owned hook is `SelectProvider(spec, handler)`. See the generator docs.
- `STREAM` / `CHANNEL` are the long-connection contract entrypoints; multi-message directions generate one discriminated union, while legacy `WS().RECV().SEND()` is outside the 1.0 mainline.
- The default HTTP/Wails runtimes fully support only `ConnectionScope.SESSION`; `APP` / `TOPIC` broadcast or topic routing can be added through a custom connection hub / manager.
- `examples/golang/server/views/routes/api/demo/impl.go` hand-writes a minimal `STREAM` / `CHANNEL` usage example that demonstrates `Open()`, `Send()`, `Recv()`, typed `Close()`, and exceptional `Abort()`.
- The Go HTTP adapter respects responses already written by Gin handlers, which fits small HTTP-only raw callbacks.
- AI agents and maintainers should query ContractGraph on demand with `api-gen inspect routes/route/files/schema/errors` first; `route` / `schema` accept multiple queries, and `files` / `errors` accept repeated `--route`, so agents can avoid restarting the command for related endpoints. Then read lightweight `api-blueprint.index.json` for the service / route / target catalog and follow its `queries` commands for batched route, schema, error, or generated file details. Full `contract.json` is generated only by explicit `formats = ["json"]` or `api-gen manifest --profile full`, and is mainly for diffs, archiving, and exhaustive fallback inspection; `agent.json`, `agent.md`, and `contract.d/` are mainly for offline navigation bundles and archives.
- ContractGraph normalizes `Blueprint(errors=...)` and route `.ERR(...)` into a language-agnostic error catalog, with `message` plus `toast.key/default/level` for each error. Generated code does not embed locale tables; business i18n resolves the current language by toast key, and client helpers fall back through `toast.text`, external i18n, `toast.default`, then `message`. Go client, TypeScript, Kotlin, and Python client/server split runtime error types/helpers from static catalog data into separate generated files; Go server emits runtime types plus grouped error values only, avoiding a duplicate root catalog. Business wrapper codes are not automatically converted into thrown exceptions.
- `[[targets]]` is the canonical config entrypoint; shortcut tables such as `[[contract]]`, `[[go.server]]`, `[[go.client]]`, `[[python.server]]`, `[[transport.http]]`, `[[grpc.proto]]`, `[[grpc.go]]`, and `[[grpc.python]]` are normalized into targets when loading config. In shortcut tables, Python `module` maps to `python_package_root`, Kotlin `module` maps to `package`, and `[[grpc.python]] module` also maps to `python_package_root`.
- gRPC proto can be emitted by the `grpc-proto` target from ContractGraph. `[[targets.proto_files]]` or the shortcut `[[grpc.proto.proto_files]]` maps DSL modules/routes to proto file/package/go_package/service. The DSL mainline only expresses generic contracts: `field(1, String(...), optional=True)` is a stable field identity, `choice="..."` is a mutually exclusive choice, and `DateTime`, `JSONValue`, and `AnyValue` are semantic value types. `grpc-go` / `grpc-python` can also omit `proto` and compile handwritten proto files directly with `source_root` / `files`.

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
