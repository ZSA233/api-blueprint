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
```

- `codegen_output`: Go output directory.
- `upstream`: backend address used by generated wrappers.
- `module`: optional Go module override; usually leave it empty and let the tool resolve it.

Go core is always generated under `views/routes/**` and contains route interfaces, models, and user `impl.go` files. The provider runtime is fixed under `views/providers`. Concrete HTTP / Wails outputs are controlled by `[[transport.targets]]`.

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

## transport

```toml
[[transport.targets]]
id = "http"
kind = "http"

[[transport.targets]]
id = "desktop.v3"
kind = "wails"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

When no `[[transport.targets]]` are declared, the generator emits a default HTTP target. Once targets are declared explicitly, only the listed transports are generated.

- `kind = "http"`: emits the Gin HTTP adapter under `views/transports/http/<root>`, for example `views/transports/http/api.NewBlueprint(engine)`.
- `kind = "wails"`: emits a Wails target; it needs at least `id`, `kind`, and `version`. `version` supports `v3` and `v2`.

- `overlay_name`: defaults to `wailsv3` / `wailsv2` and must be unique across targets.
- `frontend_mode`: defaults to `external`; `none` generates only the Go Wails overlay and skips the Wails TypeScript overlay.
- `include` / `exclude`: trim the Wails target overlay / facade; roots with no selected routes do not get `transports/<overlay_name>` output, while the shared Go / TypeScript contract layers are still generated in full.

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
