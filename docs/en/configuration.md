# Configuration

`api-blueprint.toml` is the main config file for the documentation service and the unified generator. The 1.0 mainline uses only `Blueprint -> ContractGraph -> [[targets]]`.

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
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.apiblueprint"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client", "kotlin.client"]

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

Core targets:

- `contract`: emits `api-blueprint.contract.json`, `api-blueprint.contract.md`, `api-blueprint.agent.json`, `api-blueprint.agent.md`, and / or `api-blueprint.contract.d/` shards.
- `go-server`: emits Go server core; Go client is reserved for a future `go-client` target.
- `typescript-client`: emits TypeScript client core that depends only on `ApiTransport`; `base_url` / `base_url_expr` are injected by transport facades.
- `kotlin-client`: initially supports only HTTP JSON RPC. `STREAM` / `CHANNEL`, form, binary, and custom wrappers fail during `api-gen check`.
- `grpc-proto`: emits `.proto` files and service definitions from ContractGraph. `[[targets.proto_files]]` can map DSL schema module/name plus route path/id/service to a specific proto file/package/go_package/service.
- `grpc-go`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` to generate Go protobuf/gRPC stubs.
- `grpc-python`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `grpcio-tools` to generate Python protobuf/gRPC stubs. `python_package_root` places generated files under a package root and rewrites generated imports.

gRPC stub target fields:

- `proto`: optional. When set, it references a `grpc-proto` target and stubs are generated after proto generation.
- `source_root`: required when `proto` is omitted and handwritten proto files are compiled directly. It makes `files` relative to this directory and uses it as the `protoc` working directory.
- `files`: glob list relative to the proto target `out_dir` or `source_root`, for example `api/**/*.proto`.
- `import_roots`: extra proto include roots; the proto target `out_dir` is included automatically.
- `module`: optional for `grpc-go`; when set, Go import-path output mode is used and generated files are split by `option go_package`.
- `python_package_root`: used only by `grpc-python`, for example `pb` or `generated.pb`.
- `proto_files`: used only by `grpc-proto`; each rule supports `file`, `package`, `go_package`, `schema_modules`, `schema_names`, `route_paths`, `route_ids`, `service_ids`, and `service`.

Transport targets:

- `http-transport`: declares an HTTP server/client combination.
- `wails-transport`: declares a Wails overlay and must set `version`, `server`, and `clients`.
- `frontend_mode = "external"` emits Wails TypeScript facades for external frontends; `none` emits only the Go overlay.
- `include` / `exclude` can trim the Wails target overlay / facade.

Reserved targets:

- `python-server`
- `python-client`
- `go-client`

These targets currently exist only in the schema and capability registry and do not generate business code.

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

`api-gen manifest --profile full` emits the full manifest; `--profile agent` emits the compact agent manifest; `--shards-dir` emits service / route / schema shards. `manifest.version` is the manifest schema compatibility version, for example `1.0`; `manifest.generator.version` comes from the package version source of truth. `api-gen check` builds ContractGraph first, then validates target dependencies and capabilities. Failing before generation is easier to maintain than writing a partial output tree.
