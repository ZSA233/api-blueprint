# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

Language: [中文](README.md) | English

## Overview

`api-blueprint` defines API contracts with a Python DSL and generates a documentation service, Go, TypeScript, Kotlin Android, Wails v2/v3 overlays, and gRPC artifacts for existing `.proto` trees from the same contract.

This README keeps only the onboarding path. See [Learn More](#learn-more) for full configuration, Wails, gRPC, DSL, and examples validation docs.

## Supported Outputs

| Target | Status | Command | Example |
|:---|:---:|:---|:---|
| Go | Available | `api-gen-golang` | `examples/golang` |
| TypeScript | Preview | `api-gen-typescript` | `examples/typescript` |
| Wails v3 | Experimental | `api-gen-wails` | `examples/{golang,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | Preview | `api-gen-wails` | `examples/{golang,typescript,wails-harness/v2}` |
| Kotlin Android | Preview | `api-gen-kotlin` | `examples/kotlin` |
| gRPC | Available | `api-gen-grpc` | `examples/grpc/{go,python}` |


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

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"

[typescript]
codegen_output = "typescript"
base_url = "http://localhost:2333"
```

```sh
api-doc-server -c api-blueprint.toml
api-gen-golang -c api-blueprint.toml
api-gen-typescript -c api-blueprint.toml
```

## Minimal Configuration

The following is a common multi-target config skeleton. See [Configuration](docs/en/configuration.md) for all fields.

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
provider_package = "provider"
transport_adapters = ["http", "wails"]

[typescript]
codegen_output = "typescript"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "wails.v3"
version = "v3"
frontend_mode = "external"

[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["greeterpb/greeter.proto"]
```

## Common Commands

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen-golang -c examples/api-blueprint.toml
api-gen-typescript -c examples/api-blueprint.toml
api-gen-kotlin -c examples/api-blueprint.toml
api-gen-wails -c examples/api-blueprint.toml --list-targets
api-gen-wails -c examples/api-blueprint.toml --target wails.v3
api-gen-grpc -c examples/api-blueprint.toml --list-targets
api-gen-grpc -c examples/api-blueprint.toml --target go.*
```

## Generated Artifacts And User Files

- `examples/blueprints/` and `examples/grpc/protos/` are example sources of truth.
- `examples/golang/`, `examples/typescript/`, `examples/kotlin/`, `examples/grpc/go/`, and `examples/grpc/python/` are generated snapshots.
- `examples/wails-hello/` is a standalone Wails v3 hello world example that demonstrates a GUI loop without starting an HTTP server.
- `gen_*` files are generator-owned and overwritten during regeneration.
- `impl_*` and non-`gen_*` passthrough files are user-owned extension points and are preserved during regeneration.
- Wails overlays are generated into reserved sibling directories inside the shared Go / TypeScript output trees; `api-gen-wails` does not generate a full Wails app shell, and external frontends must load the Wails runtime first.
- The Go HTTP adapter respects responses already written by Gin handlers, which fits small HTTP-only raw callbacks.
- Wails-only projects should set `[golang].transport_adapters` to `["wails"]` to generate only Go core plus Wails overlays and skip the Gin HTTP adapter; `[]` remains available for advanced core-only output.
- gRPC only compiles existing `.proto` trees and does not derive proto/service definitions from the Blueprint DSL.

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
