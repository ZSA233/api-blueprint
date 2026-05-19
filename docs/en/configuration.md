# Configuration

`api-blueprint.toml` is the main config file for the documentation service and the unified generator. The generation flow is `Blueprint -> ContractGraph -> targets`; `[[targets]]` is the canonical entrypoint, and shortcut tables such as `[[contract]]`, `[[go.server]]`, `[[go.client]]`, `[[java.server]]`, `[[java.client]]`, `[[python.server]]`, `[[transport.http]]`, `[[grpc.proto]]`, and `[[grpc.go]]` are normalized into the same target list when config is loaded.

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
```

- `docs_server`: listen address for `api-doc-server`. `host:0` is allowed; the server binds an OS-assigned free port and prints the effective docs or hub URL after startup.
- `docs_domain`: displayed docs domain, can be empty.
- `entrypoints`: Python objects to load, using `module.path:attribute` or `module.path:*`.

`Blueprint(app=None)` shares the global FastAPI app by default. Pass `app` explicitly when you need separate documentation apps.

## targets

```toml
[[contract]]
id = "contract"
out_dir = "."

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
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

[[java.server]]
id = "java.server"
out_dir = "java/server"
module = "com.example.apiblueprint"

[[java.client]]
id = "java.client"
out_dir = "java/client"
module = "com.example.apiblueprint"
base_url = "http://localhost:2333"

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

[[transport.http]]
id = "http.java"
server = "java.server"
clients = ["java.client"]

[[transport.wails]]
id = "wails.v3"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

[[grpc.proto]]
id = "grpc.proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[grpc.proto.proto_files]]
file = "api/demo/v1/demo.proto"
package = "example.api.demo.v1"
go_package = "example.com/project/grpc/go/api/demo/v1;demopb"
schema_modules = ["blueprints.api.demo"]
route_paths = ["/api/demo/v1/**"]
service = "DemoService"

[[grpc.go]]
id = "grpc.go"
proto = "grpc.proto"
out_dir = "grpc/go"
module = "example.com/project/grpc/go"
files = ["api/**/*.proto"]

[[grpc.python]]
id = "grpc.python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
module = "pb"
```

Common fields:

- `id`: unique target identifier used by dependencies and `--target`.
- `kind`: target type.
- `out_dir`: generated output directory. For Go server it is the generated package root; transport targets usually do not need one.

Shortcut tables infer `kind`, so they must not include an explicit `kind`. `id` is still required. In shortcut tables, Go `module` remains the Go module; Python `module` maps to `python_package_root`; Kotlin / Java `module` maps to `package`, and explicit `package` is still accepted; Java does not generate a JPMS `module-info.java`, and the canonical field is `package`; `[[grpc.python]] module` also maps to `python_package_root`.

Core targets:

- `contract`: when `formats` is omitted, emits only lightweight `api-blueprint.index.json` with the service / route / target catalog plus recommended `api-gen inspect` query commands. It does not inline schemas, typed error refs, route artifacts, or shard details. `formats = ["json"]` emits full `api-blueprint.contract.json` for diffs, archiving, or exhaustive fallback inspection; `markdown`, `agent-*`, and `shards` are useful for offline navigation bundles, archives, or shard snapshots.
- `go-server`: emits Go server core. `out_dir` is the package root; route/provider/transport/error artifacts live under `routes`, `providers`, `transports`, and `runtime/errors`. Markdown Binary Schema parsers live in route-group-local `routes/<root>/<group...>/_gen_binary` packages, with shared binary runtime helpers in `runtime/binary`. Projects that want `/views` in the package path should set `out_dir` explicitly to `.../views`.
- `go-client`: emits a preview Go client. RPC/query/json/form/binary HTTP calls are usable; `apiclient.NewHTTP(...)` is the recommended root facade, binary schema writers live in the route package as `gen_binary.go`, STREAM and CHANNEL generate transport-neutral surfaces, and the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.
- `typescript-client`: emits TypeScript client core that depends only on `ApiTransport`; route DTOs use `types.ts` / `gen_types.ts`, binary schema helpers are route-local `gen_binary.ts` implementation files re-exported through the types surface, and `base_url` / `base_url_expr` are injected by transport facades.
- `kotlin-client`: emits an OkHttp + kotlinx.serialization client. Through the shared transport abstraction it generates RPC, STREAM, and CHANNEL route surfaces, and supports query/json/form/binary/open request kinds plus `none` / `code_message_data` / `ok_data_error` response envelopes. Route DTOs use `<Group>Types.kt`; binary schema helpers are route-local packet / wire helper types in `BinaryTypes.kt`. `base_url` / `base_url_expr` are used by the generated OkHttp HTTP adapter config, while route/runtime clients stay transport-neutral. The built-in OkHttp adapter is RPC-first; long-connection bridges are preview/custom transport surfaces.
- `kotlin-server`: emits a preview Ktor server scaffold with route service interfaces, stubs, runtime, and Ktor route registration. Route DTOs and binary schema helpers use the same Kotlin serialization model as the client. RPC HTTP adapters are usable; connection routes keep the service surface and protocol keyframe helpers while the Ktor adapter returns explicit 501 responses.
- `java-client`: emits a preview Java 17 client using `java.net.http.HttpClient` and Jackson, with transport-neutral route surfaces and a default JDK HTTP adapter. RPC query/json/form/binary/binary-schema calls are usable; route DTOs and binary schema helper records live in `<Group>Types.java`; STREAM and CHANNEL default to explicit unsupported errors so projects can swap in custom transports.
- `java-server`: emits a preview Spring MVC server scaffold with route service interfaces, stubs, runtime, and Spring controllers. Route DTOs and binary schema helper records live in `<Group>Types.java`. RPC HTTP controllers are usable; non-RPC connection routes keep the service surface while the HTTP adapter returns explicit 501 responses.
- `python-server`: emits Python route service contracts/stubs and a FastAPI HTTP adapter scaffold. `python_package_root` controls the generated package root.
- `python-client`: emits an async-first Python HTTP client. `python_package_root` controls the generated package root, `create_client(base_url)` is the recommended aggregate facade, route DTOs use `gen_types.py`, binary schema codecs use route-local `gen_binary.py` and are re-exported through `gen_types.py`, and `base_url` / `base_url_expr` are used by the HTTP transport adapter. The default httpx adapter implements RPC requests; STREAM/CHANNEL connection transports are preview/custom extension points.
- `grpc-proto`: emits `.proto` files and service definitions from ContractGraph. `[[targets.proto_files]]` or the `[[grpc.proto.proto_files]]` shortcut can map DSL schema module/name plus route path/id/service to a specific proto file/package/go_package/service.
- `grpc-go`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` to generate Go protobuf/gRPC stubs.
- `grpc-python`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `grpcio-tools` to generate Python protobuf/gRPC stubs. `python_package_root` places generated files under a package root and rewrites generated imports.

Kotlin / Java / Python client/server, `api-gen check`, and contract / agent artifact projection use the same planner / capability metadata. If a target capability does not support a route, request kind, or response envelope, generation should fail before writing a partial output tree.

ContractGraph collects language-agnostic typed errors from `Blueprint(errors=...)` and route `.ERR(...)`. Manifest `2.0` keeps the global `errors` table for complete definitions and writes compact route-local refs (`id/group/key/code/message/toast`) into `routes[].errors`, so callers can inspect the error surface from the route they are invoking. `id` is the public protocol error identity; `code` is a business code and may be reused across groups or routes. `ResponseEnvelope` decides the wire shape, and manifest writes `name/kind/error_identity/success_code/success_message/fields` under `response.envelope`. The default `CodeMessageDataEnvelope` returns `{ code: 0, message: "ok", data }` on success and `{ code, message, data: null, error: { id, group, key, toast } }` on failure; strict `{ code, message, data }` output uses `LegacyCodeMessageDataEnvelope` without `id`; choose `OkDataErrorEnvelope` explicitly for `{ ok, data/error }`. Main generators expose `ApiError`, `ApiErrors`, and route-aware `lookupApiError` helpers; default Go, TypeScript, Python, Kotlin, and Java client transports restore typed errors from the envelope spec. Business i18n resolves the current language by toast key, and client helpers fall back through `toast.text`, external i18n, `toast.default`, then `message`. Business error codes are not forced to equal HTTP status codes.

The Kotlin client/server output layout is `<package>/<root>/runtime/*`, `<package>/<root>/routes/<root>/<group...>/*`, and `<package>/<root>/transports/http/*`. `Gen*.kt` files are generator-owned; non-`Gen*` façade / extension files are user-owned. The client preserves route façade and HTTP client façade files; the server preserves `<Group>Service.kt` implementations.

The Go client output layout is `runtime/*`, `routes/<root>/<group...>/*`, and `transports/http/*`. `gen_*.go` files are generator-owned, while `client.go` façades are user-owned and preserved during regeneration. `base_url` / `base_url_expr` are written only to the HTTP transport config, not route/runtime clients.

The Java client/server output layout is `<package>/<root>/runtime/*`, `<package>/<root>/routes/<root>/<group...>/*`, and `<package>/<root>/transports/http/*`. `out_dir` is the package root and does not include `src/main/java`. The client preserves `ApiClient.java`, `<Group>Api.java`, and `HttpApiClient.java`; the server preserves `<Group>Service.java`. DTOs use Java 17 `record`, fields use Jackson `@JsonProperty`, and enums use `@JsonCreator` / `@JsonValue` to preserve wire values.

The Python client/server output layout is `<python_package_root>/<root>/runtime/*`, `<python_package_root>/<root>/routes/<root>/<group...>/*`, and `<python_package_root>/<root>/transports/http/*`. Root-level routes are emitted under `routes/<root>`. If `python_package_root` is omitted, the generator uses its default package root.

gRPC stub target fields:

- `proto`: optional. When set, it references a `grpc-proto` target and stubs are generated after proto generation.
- `source_root`: required when `proto` is omitted and handwritten proto files are compiled directly. It makes `files` relative to this directory and uses it as the `protoc` working directory.
- `files`: glob list relative to the proto target `out_dir` or `source_root`, for example `api/**/*.proto`.
- `import_roots`: extra proto include roots; the proto target `out_dir` is included automatically.
- `module`: optional for `grpc-go`; when set, Go import-path output mode is used and generated files are split by `option go_package`.
- `python_package_root`: used by `python-client`, `python-server`, and `grpc-python`, for example `api_client`, `generated.server`, `pb`, or `generated.pb`; shortcut tables may write `module`.
- `proto_files`: used only by `grpc-proto`; each rule supports `file`, `package`, `go_package`, `schema_modules`, `schema_names`, `route_paths`, `route_ids`, `service_ids`, and `service`; the shortcut form is `[[grpc.proto.proto_files]]`.

Transport targets:

- `http-transport`: declares an HTTP server/client combination. `server` can reference a `go-server`, `java-server`, or `python-server`; `clients` can reference Go, TypeScript, Kotlin, Java, or Python clients.
- `wails-transport`: declares a Wails overlay and must set `version`, `server`, and `clients`. Wails remains Go + TypeScript only and does not attach Kotlin / Java / Python clients.
- `frontend_mode = "external"` emits Wails TypeScript facades for external frontends; `none` emits only the Go overlay.
- `include` / `exclude` can trim the Wails target overlay / facade.

## CLI

```sh
api-gen list-targets -c api-blueprint.toml
api-gen explain-target -c api-blueprint.toml --target go.server
api-gen inspect routes -c api-blueprint.toml
api-gen inspect route api.demo.post.testpost api.demo.channel.assistantsession -c api-blueprint.toml
api-gen inspect files -c api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession --target go.server
api-gen inspect schema ApiDemoA RSP_TestPost -c api-blueprint.toml
api-gen inspect errors -c api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession
api-gen manifest -c api-blueprint.toml --out api-blueprint.index.json
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen inspect` loads Blueprint from config and builds ContractGraph directly, so agents can query by route, schema, error, or target file index without generating `contract.d` first or opening generated source. The `route` / `schema` subcommands accept multiple queries, while `files` / `errors` accept repeated `--route`, so an agent can retrieve details for related endpoints in one command. `inspect` returns only live ContractGraph query results, does not imply shard files exist, and does not return a default shard path; generate `api-blueprint.agent.json` or `api-blueprint.contract.d` explicitly when offline shard navigation is needed. `api-gen explain-target` prints the effective target summary instead of a raw TOML fragment; it shows the key fields and key effective values for the selected target kind. For example, a contract target with omitted `formats` still shows `formats = ["index"]`, and a Wails target shows `version`, `overlay_name`, `frontend_mode`, `include`, and `exclude`. `api-gen manifest` defaults to the catalog-only lightweight index; `--profile full` emits the full manifest; `--profile agent` emits the compact agent manifest; `--shards-dir` emits service / route / schema shards. `manifest.version` is the manifest schema compatibility version and is `2.0`; `manifest.generator.version` comes from the package version source of truth. `api-gen check` builds ContractGraph first, then uses shared planner / capability metadata to validate target dependencies, routes, request kinds, and response envelopes. Failing before generation is easier to maintain than writing a partial output tree.
