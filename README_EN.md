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

- Backend, web, Android, and script clients need to share one API contract.
- You want to generate a Go server first, then TypeScript, Kotlin, Java, Go, or Python clients.
- You need documentation, contract checks, generated snapshots, and end-to-end examples to move together.
- You need Markdown Binary Schema, Wails, or gRPC in the same generation flow.

## Installation

The stable installation entrypoint points to the GitHub `stable` branch:

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

When developing this repository, use:

```sh
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

For fuller project layout, config fields, DSL, generator output, typed errors, Response Envelopes, Markdown Binary Schema, Wails, and gRPC, see [Getting Started](docs/en/getting-started.md), [Configuration](docs/en/configuration.md), and the topic documents below.

## Common Targets

| Target | Status | Purpose |
|:---|:---:|:---|
| Contract / inspect | Available | Emit a contract index and query route, schema, error, or file ownership details |
| Go server | Available | Generate Go routes, providers, long-connection message helpers, HTTP/Wails adapters, and runtime |
| TypeScript client | Preview | Generate transport-neutral clients, long-connection message helpers, HTTP adapters, and Wails facades |
| Kotlin Android client | Preview | Generate OkHttp clients, models, binary writers, and route facades |
| Java client/server | Preview | Generate Java 17 HttpClient clients, Spring MVC server scaffolds, record DTOs, and HTTP adapters |
| Go / Python client | Preview | Generate non-server clients for scripts, tools, or services |
| Python server | Preview | Generate FastAPI server scaffolds and service contracts |
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
make test
make example-compile-check
make example-validation
make example-golang-suite
make example-java-suite
```

`example-golang-suite` and `example-java-suite` are manual end-to-end validation aids; they are not part of default tests, release preflight, or CI. See [Release Process](docs/release-process.md) for versioning, build, install, and GitHub Release flow.
