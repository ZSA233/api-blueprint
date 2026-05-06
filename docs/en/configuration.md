# Configuration

`api-blueprint.toml` is the main config file for the documentation service and the unified generator. The vNext mainline uses only `Blueprint -> ContractGraph -> [[targets]]`.

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
formats = ["json", "markdown"]

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
```

Common fields:

- `id`: unique target identifier used by dependencies and `--target`.
- `kind`: target type.
- `out_dir`: generated output directory; transport targets usually do not need one.

Core targets:

- `contract`: emits `api-blueprint.contract.json` and / or `api-blueprint.contract.md`.
- `go-server`: emits Go server core; Go client is reserved for a future `go-client` target.
- `typescript-client`: emits TypeScript client core that depends only on `ApiTransport`; `base_url` / `base_url_expr` are injected by transport facades.
- `kotlin-client`: initially supports only HTTP JSON RPC. `STREAM` / `CHANNEL`, form, binary, and custom wrappers fail during `api-gen check`.
- `grpc-proto`: emits `.proto` files and service definitions from ContractGraph.

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
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen manifest` emits routes, schemas, connections, stable hashes, the resolved target plan, and the capability registry. `api-gen check` builds ContractGraph first, then validates target dependencies and capabilities. Failing before generation is easier to maintain than writing a partial output tree.
