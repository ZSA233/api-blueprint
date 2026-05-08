# Getting Started

This guide is for first-time `api-blueprint` users. It walks from a Python Blueprint to generated Go, TypeScript, and a documentation service.

## Installation

The stable installation entrypoint currently points to the GitHub `stable` branch:

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

When developing this repository, use:

```sh
make sync
```

## Suggested Layout

A minimal project usually contains:

```text
your-project/
  api-blueprint.toml
  blueprints/
    __init__.py
    app.py
  golang/
    server/
    client/
  typescript/
```

`blueprints/` is the API contract source of truth. `golang/server`, `golang/client`, and `typescript/` are generated artifact directories.

## Define A Blueprint

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class HelloResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(HelloResponse)
```

## Write Minimal Config

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[go.server]]
id = "go.server"
out_dir = "golang/server"

[[go.client]]
id = "go.client"
out_dir = "golang/client"
base_url = "http://localhost:2333"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client"]
```

## Start The Docs Server

```sh
api-doc-server -c api-blueprint.toml
```

The docs server loads `[blueprint].entrypoints` and builds FastAPI/OpenAPI output.

## Generate Code

```sh
api-gen generate -c api-blueprint.toml
```

With the repository example config, you can run:

```sh
api-gen list-targets -c examples/api-blueprint.toml
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
```

## Next Steps

- See [Configuration](configuration.md) for config fields.
- See [Blueprint DSL](blueprint-dsl.md) for DSL usage.
- See [Generators](generators.md) for generator differences.
- See [Wails](wails.md) for Wails integration.
- See [gRPC](grpc.md) for gRPC targets.
