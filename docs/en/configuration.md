# Configuration

`api-blueprint.toml` is the main config file for the documentation service and the unified generator. The 1.0 mainline uses `Blueprint -> ContractGraph -> targets`; `[[targets]]` is the canonical entrypoint, and shortcut tables such as `[[go.server]]`, `[[go.client]]`, `[[python.server]]`, and `[[transport.http]]` are normalized into the same target list when config is loaded.

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
```

- `docs_server`: listen address for `api-doc-server`.
- `docs_domain`: displayed docs domain, can be empty.
- `entrypoints`: Python objects to load, using `module.path:attribute` or `module.path:*`.

`Blueprint(app=None)` shares the global FastAPI app by default. Pass `app` explicitly when you need separate documentation apps.

## targets

```toml
[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json", "markdown", "agent-json", "agent-markdown", "shards"]

[[go.server]]
id = "go.server"
out_dir = "golang/server"
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

[[transport.wails]]
id = "wails.v3"
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

[[targets]]
id = "grpc.go"
kind = "grpc-go"
proto = "grpc.proto"
out_dir = "grpc/go"
module = "example.com/project/grpc/go"
files = ["api/**/*.proto"]

[[targets]]
id = "grpc.python"
kind = "grpc-python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
python_package_root = "pb"
```

Common fields:

- `id`: unique target identifier used by dependencies and `--target`.
- `kind`: target type.
- `out_dir`: generated output directory; transport targets usually do not need one.

Shortcut tables infer `kind`, so they must not include an explicit `kind`. `id` is still required. In shortcut tables, Go `module` remains the Go module; Python `module` maps to `python_package_root`; Kotlin `module` maps to `package`, and explicit `package` is still accepted.

Core targets:

- `contract`: emits `api-blueprint.contract.json`, `api-blueprint.contract.md`, `api-blueprint.agent.json`, `api-blueprint.agent.md`, and / or `api-blueprint.contract.d/` shards.
- `go-server`: emits Go server core.
- `go-client`: emits a preview Go client. RPC/query/json/form/binary HTTP calls are usable; legacy WS / STREAM / CHANNEL generate transport-neutral surfaces, and the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.
- `typescript-client`: emits TypeScript client core that depends only on `ApiTransport`; `base_url` / `base_url_expr` are injected by transport facades.
- `kotlin-client`: emits an OkHttp + kotlinx.serialization Android client. Through the shared transport abstraction it generates RPC, legacy WS, STREAM, and CHANNEL route surfaces, and supports query/json/form/binary/open request kinds plus none/general/custom response wrappers. `base_url` / `base_url_expr` are used by the generated OkHttp HTTP adapter config, while route/runtime clients stay transport-neutral. The built-in OkHttp adapter is RPC-first; long-connection bridges are preview/custom transport surfaces.
- `python-server`: emits Python route service contracts/stubs and a FastAPI HTTP adapter scaffold. `python_package_root` controls the generated package root.
- `python-client`: emits an async-first Python HTTP client. `python_package_root` controls the generated package root, and `base_url` / `base_url_expr` are used by the HTTP transport adapter. The default httpx adapter implements RPC requests; WS/STREAM/CHANNEL connection transports are preview/custom extension points.
- `grpc-proto`: emits `.proto` files and service definitions from ContractGraph. `[[targets.proto_files]]` can map DSL schema module/name plus route path/id/service to a specific proto file/package/go_package/service.
- `grpc-go`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` to generate Go protobuf/gRPC stubs.
- `grpc-python`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `grpcio-tools` to generate Python protobuf/gRPC stubs. `python_package_root` places generated files under a package root and rewrites generated imports.

Kotlin / Python client/server, `api-gen check`, and contract / agent artifact projection use the same planner / capability metadata. If a target capability does not support a route, request kind, or wrapper, generation should fail before writing a partial output tree.

The Kotlin client output layout is `<package>/<root>/runtime/*`, `<package>/<root>/routes/<root>/<group...>/*`, and `<package>/<root>/transports/http/*`. `Gen*.kt` files are generator-owned; non-`Gen*` façade / extension files are user-owned. This is a breaking layout change from the old `<package>/ApiClient.kt`, `endpoints/`, `models/`, and `internal/` layout.

The Go client output layout is `runtime/*`, `routes/<root>/<group...>/*`, and `transports/http/*`. `gen_*.go` files are generator-owned, while `client.go` façades are user-owned and preserved during regeneration. `base_url` / `base_url_expr` are written only to the HTTP transport config, not route/runtime clients.

The Python client/server output layout is `<python_package_root>/<root>/runtime/*`, `<python_package_root>/<root>/routes/<root>/<group...>/*`, and `<python_package_root>/<root>/transports/http/*`. Root-level routes are emitted under `routes/<root>`, not `routes/root`. If `python_package_root` is omitted, the generator uses its default package root.

gRPC stub target fields:

- `proto`: optional. When set, it references a `grpc-proto` target and stubs are generated after proto generation.
- `source_root`: required when `proto` is omitted and handwritten proto files are compiled directly. It makes `files` relative to this directory and uses it as the `protoc` working directory.
- `files`: glob list relative to the proto target `out_dir` or `source_root`, for example `api/**/*.proto`.
- `import_roots`: extra proto include roots; the proto target `out_dir` is included automatically.
- `module`: optional for `grpc-go`; when set, Go import-path output mode is used and generated files are split by `option go_package`.
- `python_package_root`: used by `python-client`, `python-server`, and `grpc-python`, for example `api_client`, `generated.server`, `pb`, or `generated.pb`.
- `proto_files`: used only by `grpc-proto`; each rule supports `file`, `package`, `go_package`, `schema_modules`, `schema_names`, `route_paths`, `route_ids`, `service_ids`, and `service`.

Transport targets:

- `http-transport`: declares an HTTP server/client combination. `server` can reference a `go-server` or `python-server`; `clients` can reference Go, TypeScript, Kotlin, or Python clients.
- `wails-transport`: declares a Wails overlay and must set `version`, `server`, and `clients`. Wails remains Go + TypeScript only and does not attach Kotlin / Python clients.
- `frontend_mode = "external"` emits Wails TypeScript facades for external frontends; `none` emits only the Go overlay.
- `include` / `exclude` can trim the Wails target overlay / facade.

## CLI

```sh
api-gen list-targets -c api-blueprint.toml
api-gen explain-target -c api-blueprint.toml --target go.server
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen manifest --profile full` emits the full manifest; `--profile agent` emits the compact agent manifest; `--shards-dir` emits service / route / schema shards. `manifest.version` is the manifest schema compatibility version, for example `1.0`; `manifest.generator.version` comes from the package version source of truth. `api-gen check` builds ContractGraph first, then uses shared planner / capability metadata to validate target dependencies, routes, request kinds, and wrappers. Failing before generation is easier to maintain than writing a partial output tree.
