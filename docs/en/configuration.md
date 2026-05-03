# Configuration

`api-blueprint.toml` is the main config file for generators and the documentation service. See [`examples/api-blueprint.toml`](../../examples/api-blueprint.toml) for a complete example.

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
```

- `docs_server`: listen address for `api-doc-server`.
- `docs_domain`: displayed docs domain, can be empty.
- `entrypoints`: Python objects to load, using module path plus object name.

`Blueprint(app=None)` shares the global FastAPI app by default. Pass `app` explicitly when you need separate documentation apps.

## golang

```toml
[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
module = ""
provider_package = "provider"
```

- `codegen_output`: Go output directory.
- `upstream`: backend address used by generated wrappers.
- `module`: optional Go module override; usually leave it empty and let the tool resolve it.
- `provider_package`: shared Go runtime/provider package name used by both HTTP and Wails; defaults to `provider` and cannot start with `_`.

## typescript

```toml
[typescript]
codegen_output = "typescript"
upstream = "http://localhost:2333"
base_url = "http://localhost:2333"
# base_url_expr = "import.meta.env.VITE_API_BASE_URL"
```

- `codegen_output`: TypeScript output directory.
- `upstream`: compatibility default address source.
- `base_url`: literal base URL.
- `base_url_expr`: expression emitted verbatim into TypeScript.

`base_url_expr` and `base_url` are mutually exclusive. Resolution order is `base_url_expr -> base_url -> upstream -> ""`.

## kotlin

```toml
[kotlin]
codegen_output = "kotlin"
package = "com.example.apiblueprint"
base_url = "http://localhost:2333"
include = ["tag:api"]
exclude = ["path:/static/**"]
```

Kotlin generates an OkHttp + kotlinx.serialization Android client. The current version targets JSON REST routes and does not cover WebSocket, form, or binary routes yet.

`include` / `exclude` support `path:`, `tag:`, `group:`, `method:`, and `name:` rules.

## wails

```toml
[[wails.targets]]
id = "wails.v3"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

A Wails target needs at least `id` and `version`. `version` supports `v3` and `v2`.

- `overlay_name`: defaults to `wailsv3` / `wailsv2` and must be unique across targets.
- `frontend_mode`: defaults to `external`; `none` generates only the Go Wails overlay and skips the Wails TypeScript overlay.
- `include` / `exclude`: trim only the Wails overlay, not the shared Go / TypeScript contract layers.

See [Wails](wails.md) for detailed layout and hooks.

## grpc

```toml
[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["commonpb/common.proto", "greeterpb/greeter.proto"]

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "grpc/python"
files = ["**/*.proto"]
python_package_root = "examplegrpc_pb"
```

gRPC targets compile existing `.proto` trees. They do not derive proto/service definitions from the Blueprint DSL.

See [gRPC](grpc.md) for target behavior.
