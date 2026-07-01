# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL and generates documentation services, contract indexes, and multi-language code from the same protocol source of truth.

It keeps HTTP APIs, `STREAM` / `CHANNEL` messages, binary protocols, media uploads, raw responses, Wails, and gRPC in one checkable, generatable, regression-friendly workflow.

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## When To Use

- Multiple platforms need to share one API contract.
- You want one protocol source to generate server scaffolds, client SDKs, docs, and snapshot tests.
- You need legacy JSON shape drift, typed errors, binary schema, stream/channel, or similar protocol details in the contract.
- You want AI or human review to start from a contract index instead of generated artifacts.

## Installation

The stable installation entrypoint points to the GitHub `stable` branch:

```sh
uv tool install "git+https://github.com/zsa233/api-blueprint@stable"
```

When developing this repository, use:

```sh
make
make sync
```

## 30-Second Example

Define a Blueprint:

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class PingResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/ping").RSP(PingResponse)
```

Create `api-blueprint.toml`:

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
module = "example.com/project/golang/server"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["typescript.client"]
```

Start the docs server, check the contract, and generate code:

```sh
api-doc-server -c api-blueprint.toml
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

By default, `/` and `/docs` both serve the api-blueprint docs center. The full OpenAPI document remains available at `/openapi.json`, and message protocols are available through interaction-aware `/docs/protocol` and `/docs/asyncapi`.

## Common Targets

| Target | Status | Purpose |
|:---|:---:|:---|
| Contract / inspect | Available | Emit and query the protocol index |
| Go server | Available | Generate Go providers, HTTP/Wails adapters, WebSocket channel entrypoints, and server-side DTOs |
| Go client / Python client | Preview | Generate clients for scripts, tools, or services |
| TypeScript client | Preview | Generate transport-neutral clients and HTTP/Wails facades |
| Flutter client | Preview | Generate a pure Dart package and HTTP/SSE/WebSocket clients |
| Swift client | Preview | Generate a Swift Package SDK |
| Kotlin client/server | Preview | Generate OkHttp clients and Ktor server scaffolds |
| Java client/server | Preview | Generate Java HttpClient clients and Spring MVC contract entrypoints |
| Python server | Preview | Generate FastAPI server scaffolds |
| Wails v2/v3 | Preview / Experimental | Generate Go + TypeScript overlays |
| gRPC proto / stubs | Available | Generate proto plus Go/Python gRPC stubs |
| IR plugin | Preview | Let project plugins consume ContractGraph and generate owned artifacts |

## Next Steps

| Topic | Documentation |
|:---|:---|
| Getting started | [docs/en/getting-started.md](docs/en/getting-started.md) |
| Config fields | [docs/en/configuration.md](docs/en/configuration.md) |
| Blueprint DSL | [docs/en/blueprint-dsl.md](docs/en/blueprint-dsl.md) |
| Markdown Binary Schema | [docs/en/binary-schema.md](docs/en/binary-schema.md) |
| Generators and output layout | [docs/en/generators.md](docs/en/generators.md) |
| Wails | [docs/en/wails.md](docs/en/wails.md) |
| gRPC | [docs/en/grpc.md](docs/en/grpc.md) |
| Examples validation | [docs/en/examples-validation.md](docs/en/examples-validation.md) |
| Benchmarks | [docs/en/benchmarks.md](docs/en/benchmarks.md) |
| Release process | [docs/release-process.md](docs/release-process.md) |

## Development And Release

Common local commands:

```sh
make test-fast
make example-validation
make example-conformance
make release-preflight RELEASE_TAG=vX.Y.Z
```

See the topic documents above for the full development, example validation, benchmark, and release workflow.
