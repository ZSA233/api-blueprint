# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL, then generates documentation services and multi-language code from the same protocol source of truth. It is built for maintaining HTTP APIs, long-connection messages, binary request bodies, and gRPC proto in one checkable, generatable, regression-friendly workflow.

The core flow is:

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## When To Use

- Backend, web, Flutter, Kotlin, and script clients need to share one API contract.
- You want to generate a Go server first, then TypeScript, Flutter, Kotlin, Java, Go, or Python clients, or generate Kotlin/Java/Python server scaffolds.
- You need documentation, contract checks, generated snapshots, and end-to-end examples to move together.
- You need Markdown Binary Schema, Wails, or gRPC in the same generation flow.

## Installation

The stable installation entrypoint points to the GitHub `stable` branch:

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
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
api-doc-server --version
api-gen --version
api-doc-server -c api-blueprint.toml
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

For fuller project layout, config fields, DSL, generator output, typed errors, Response Envelopes, Markdown Binary Schema, Wails, and gRPC, see [Getting Started](docs/en/getting-started.md), [Configuration](docs/en/configuration.md), and the topic documents below.

## Common Targets

| Target | Status | Purpose |
|:---|:---:|:---|
| Contract / inspect | Available | Emit a contract index and query route, schema, error, or file ownership details |
| Go server | Available | Generate Go routes, providers, long-connection message helpers, HTTP/Wails adapters, and runtime |
| TypeScript client | Preview | Generate transport-neutral clients, long-connection message helpers, HTTP adapters, and Wails facades |
| Flutter client | Preview | Generate a pure Dart package, DTOs, typed errors, binary codecs, and HTTP/SSE/WebSocket clients |
| Kotlin client/server | Preview | Generate OkHttp HTTP/SSE/WebSocket clients, Ktor HTTP/SSE/WebSocket server scaffolds, models, long-connection message helpers, and binary writers |
| Java client/server | Preview | Generate Java 17 HttpClient clients, Spring MVC/SSE/WebSocket server scaffolds, record DTOs, long-connection message helpers, binary packet helpers, and HTTP adapters |
| Go / Python client | Preview | Generate non-server clients for scripts, tools, or services; the Python client uses recursive dataclass DTOs, shared runtime codecs, long-connection message helpers, and binary writers |
| Python server | Preview | Generate FastAPI HTTP/SSE/WebSocket server scaffolds, typed service contracts, and long-connection message helpers |
| Wails v2/v3 | Preview / Experimental | Generate Go + TypeScript overlays for desktop GUIs |
| gRPC proto / stubs | Available | Emit proto from ContractGraph and generate Go/Python stubs |

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
| Release process | [docs/release-process.md](docs/release-process.md) |

## Development And Release

Common development commands:

```sh
make
make test
make example-compile-check
make example-validation
make example-conformance
make example-golang-suite
make example-java-suite
```

`make example-conformance` starts with a real Go HTTP server by default; use `EXAMPLE_CONFORMANCE_SERVERS`, `EXAMPLE_CONFORMANCE_CLIENTS`, and `EXAMPLE_CONFORMANCE_SCENARIOS` to select the matrix, or set `EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all` for the full matrix. `example-golang-suite` and `example-java-suite` remain manual end-to-end validation aids. See [Release Process](docs/release-process.md) for versioning, build, install, and GitHub Release flow.
