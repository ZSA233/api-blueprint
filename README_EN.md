# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL, then generates documentation services and multi-language code from the same protocol source of truth. It is built for maintaining HTTP APIs, `STREAM` / `CHANNEL` messages, binary request / response bodies, media uploads / raw responses, and gRPC proto in one checkable, generatable, regression-friendly workflow.

The core flow is:

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## When To Use

- Backend, web, Flutter, iOS Swift, Kotlin, and script clients need to share one API contract.
- You want to generate a Go server first, then TypeScript, Flutter, Swift, Kotlin, Java, Go, or Python clients, or generate Kotlin/Python server scaffolds and Java Spring controller/delegate entrypoints.
- You need documentation, contract checks, generated snapshots, and end-to-end examples to move together.
- You need Markdown Binary Schema, typed binary responses, multipart uploads, raw bytes/file/stream responses, Wails, or gRPC in the same generation flow.
- You need `OneOf` / `LegacyStringID` to bring legacy fields with multiple JSON shapes or string/int ID drift into the contract instead of leaving them as broad `JSONValue`.

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

`root` is the URL prefix. When several top-level URL namespaces belong to one generated root, use `Blueprint(name="app", root="")` and define paths in groups such as `group("/account")` and `group("/room")`. `name` is the logical protocol identity used by route IDs, services/modules, and generated directories.

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
| Go server | Available | Generate Go routes, providers, long-connection message helpers, HTTP/Wails adapters, multipart/raw media, binary schema requests/responses, and runtime |
| TypeScript client | Preview | Generate transport-neutral clients, long-connection message helpers, HTTP multipart/raw adapters, binary schema response decoding, and Wails facades |
| Flutter client | Preview | Generate a pure Dart package, DTOs, typed errors, binary codecs, HTTP multipart/raw/binary response clients, and SSE/WebSocket clients |
| Swift client | Preview | Generate an iOS Swift Package multi-target SDK, short module stem, root routes modules, DTOs, typed errors, field-level binary codecs, shared URLSession HTTP/SSE/WebSocket transport with validation/limit knobs, and multipart/raw/binary response clients, without UI, auth, cache, or a session engine |
| Kotlin client/server | Preview | Generate OkHttp HTTP/SSE/WebSocket clients, Ktor HTTP/SSE/WebSocket server scaffolds, multipart/raw/binary request/response adapters, models, and long-connection message helpers |
| Java client/server | Preview | Generate Java 17 HttpClient clients plus strongly constrained Spring MVC `Gen...Controller`, `Gen...Delegate`, JavaBean request/response types, adapter helpers, and runtime contract assertions; Spring policy is driven by DSL providers plus Java mappings |
| Go client / Python client | Preview | Generate non-server clients for scripts, tools, or services; the Python client uses recursive dataclass DTOs, shared runtime codecs, multipart/raw support, transport-neutral long-connection message helpers, processor/channel scaffolds, and binary writers/response codecs |
| Python server | Preview | Generate FastAPI HTTP/SSE/WebSocket server scaffolds, multipart/raw/binary request/response adapters, typed service contracts, and long-connection message helpers |
| Wails v2/v3 | Preview / Experimental | Generate Go + TypeScript overlays; file/stream-style capabilities are modeled with Wails RPC descriptors or STREAM/CHANNEL chunks |
| gRPC proto / stubs | Available | Emit proto from ContractGraph and generate Go/Python stubs; bytes/file/stream-style capabilities are modeled with protobuf bytes or streaming chunks |
| IR plugin | Preview | Let project plugins read ContractGraph, route selection, and target options to generate project-owned artifacts; it does not provide a host runtime engine |

See [Generators and output layout](docs/en/generators.md) for generated ownership, per-request options, stream/file paths, server-adapter safety defaults, and production escape hatches. See [Configuration](docs/en/configuration.md) for IR plugin config, options, and metadata constraints. Default adapters are protocol bridges rather than complete production runtimes; production projects should prefer narrow route/client/router entrypoints and use native clients, custom transports, service implementations, middleware, or app shells for auth, rate limits, cookies, TLS/proxy, retry, and file permission policy. `include` / `exclude` is the stable generation-time trim boundary; unused imports or narrow products are language toolchain optimizations, not a cross-language struct-level dead-strip contract.

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

Common development commands:

```sh
make
make test
make example-compile-check
make example-validation
make example-conformance
make benchmark-list
make example-golang-suite
make example-java-suite
make example-java-spring-server
make example-java-spring-server-benchmark
```

`make example-conformance` starts with a real Go HTTP server by default; use `EXAMPLE_CONFORMANCE_SERVERS`, `EXAMPLE_CONFORMANCE_CLIENTS`, `EXAMPLE_CONFORMANCE_SCENARIOS`, and `EXAMPLE_CONFORMANCE_SWIFT_RUNTIME_PROFILE` to select the matrix, or set `EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all` for the full matrix (Swift scenarios require an available Swift toolchain). Benchmarks are opt-in trend tools, not default CI gates; generated client SDK smoke, Swift runtime microbenchmarks, and Java Spring controller/delegate microbenchmarks are available alongside binary / protocol benchmarks in [Benchmarks](docs/en/benchmarks.md). `example-golang-suite` remains a manual end-to-end validation aid; `example-java-suite` is a Java Spring generated-artifact compile/smoke check; `example-java-spring-server` validates a real Spring Boot host example. See [Release Process](docs/release-process.md) for versioning, build, install, and GitHub Release flow.
