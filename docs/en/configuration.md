# Configuration

`api-blueprint.toml` is the main config file for the documentation service and the unified generator. The generation flow is `Blueprint -> ContractGraph -> targets`; `[[targets]]` is the canonical entrypoint, and shortcut tables such as `[[contract]]`, `[[go.server]]`, `[[go.client]]`, `[[typescript.client]]`, `[[flutter.client]]`, `[[swift.client]]`, `[[kotlin.client]]`, `[[java.server]]`, `[[java.client]]`, `[[python.server]]`, `[[transport.http]]`, `[[grpc.proto]]`, and `[[grpc.go]]` are normalized into the same target list when config is loaded. Extension targets without shortcut tables, such as `ir-plugin`, use the canonical `[[targets]]` form.

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
protocol_docs_plugins = ["project.docs.protocol:plugin"]
```

- `docs_server`: listen address for `api-doc-server`. `host:0` is allowed; the server binds an OS-assigned free port and prints the effective docs or hub URL after startup.
- `docs_domain`: displayed docs domain, can be empty.
- `entrypoints`: Python objects to load, using `module.path:attribute` or `module.path:*`.
- `protocol_docs_plugins`: optional message protocol documentation projection plugins. The built-in metadata interaction plugin reads `message_variant(..., interaction="...", role="request|response|error|push", op=..., name=..., description=..., auth=..., example=...)` and groups `CHANNEL` / `STREAM` messages into request/response interactions for Protocol UI. Projects can add plugins that map custom op/message metadata into the same interaction catalog. Plugins only control documentation relationships; upstream connection, auth, frame codec, and online try-out remain project-owned.

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

[[flutter.client]]
id = "flutter.client"
out_dir = "flutter"
package = "api_blueprint_example"
base_url = "http://localhost:2333"

[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
base_url = "http://localhost:2333"
runtime_profile = "modern"

[[kotlin.client]]
id = "kotlin.client"
out_dir = "kotlin"
module = "com.example.apiblueprint"

[[java.server]]
id = "java.server"
out_dir = "java/server"
module = "com.example.apiblueprint"
exclude = ["kind:stream", "kind:channel"]
spring_contract_mode = "strict"
spring_public_paths = ["/api/**", "/legacy/**", "/runtime/**", "/static/**"]

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
clients = ["go.client", "typescript.client", "flutter.client", "swift.client", "kotlin.client", "python.client"]

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

[[targets]]
id = "demo.plugin"
kind = "ir-plugin"
plugin = "plugins.summary"
out_dir = "generated/plugin"
include = ["kind:channel"]

[targets.options]
package = "demo"
```

Common fields:

- `id`: unique target identifier used by dependencies and `--target`.
- `kind`: target type.
- `out_dir`: generated output directory. For Go server it is the generated package root; transport targets usually do not need one.

Shortcut tables infer `kind`, so they must not include an explicit `kind`. `id` is still required. In shortcut tables, Go `module` remains the Go module; Python `module` maps to `python_package_root`; Flutter / Kotlin / Java `module` maps to `package`, and explicit `package` is still accepted; Swift `package` is the required SwiftPM package identity, while Swift `module` is an optional Swift module stem that defaults to `package` and is no longer aliased into `package`; Flutter and Java use `package` as the canonical field, Java does not generate a JPMS `module-info.java`; `[[grpc.python]] module` also maps to `python_package_root`.

Core targets:

- `contract`: when `formats` is omitted, emits only lightweight `api-blueprint.index.json` with the service / route / target catalog plus recommended `api-gen inspect` query commands. It does not inline schemas, typed error refs, route artifacts, or shard details. `formats = ["json"]` emits full `api-blueprint.contract.json` for diffs, archiving, or exhaustive fallback inspection; `markdown`, `agent-*`, and `shards` are useful for offline navigation bundles, archives, or shard snapshots.
- `go-server`: emits Go server core. `out_dir` is the package root; route/provider/transport/error artifacts live under `routes`, `providers`, `transports`, and `runtime/errors`. Markdown Binary Schema parsers live in route-group-local `routes/<root>/<group...>/_gen_binary` packages, with shared binary runtime helpers in `runtime/binary`. Projects that want `/views` in the package path should set `out_dir` explicitly to `.../views`. Advanced `options.emit_contract_metadata = true` also emits route-package-sharded contract metadata plus the top-level `routes.ContractRoutes()` aggregate.
- `go-client`: emits a preview Go client. RPC/query/json/urlencoded/multipart/binary_schema HTTP calls are usable; `apiclient.NewHTTP(...)` is the recommended root facade, route calls accept variadic `runtime.RequestOption` helpers for per-call headers, binary schema writers live in the route package as `gen_binary.go`, binary_schema success responses return typed packets, bytes/file raw responses return `RawResponse`, byte streams return true streaming `StreamResponse` values that callers must close, STREAM and CHANNEL generate transport-neutral surfaces, and the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.
- `typescript-client`: emits TypeScript client core that depends only on `ApiTransport`; route DTOs use `types.ts` / `gen_types.ts`, route RPC calls accept `ApiRequestOptions` for per-call headers, timeout, and native HTTP init, binary schema helpers are route-local `gen_binary.ts` implementation files re-exported through the types surface, and `base_url` / `base_url_expr` are injected by transport facades.
- `flutter-client`: emits a pure Dart package that Flutter apps can depend on without binding the generated SDK to the Flutter SDK. Public entries `lib/<package>.dart` / `lib/<root>.dart` and `lib/src/<root>/<root>.dart` are preserved facades that export the matching `gen_*.dart` files; implementation lives under `lib/src/<root>/runtime`, `routes`, and `transports/http`. Route DTOs use manual generated `fromJson` / `toJson`, with a preserved `api_json_codecs.dart` `ApiJsonCodec<T>` override registry. The default HTTP adapter uses `package:http` for RPC query/json/urlencoded/multipart/binary_schema/open, supports per-call `ApiRequestOptions`, returns typed packets for binary_schema success responses, returns `ApiRawResponse<Uint8List>` for bytes/file raw responses, returns true streaming `ApiStreamResponse.body: Stream<List<int>>` for byte streams, uses SSE for STREAM, and uses `web_socket_channel` for CHANNEL.
- `swift-client`: emits an iOS Swift Package Manager multi-target SDK. `package` is the required SwiftPM package identity; `module` is an optional Swift module stem that defaults to `package`, producing the `<module>` aggregate, shared `<module>Runtime`, and one `<module><Root>Routes` module per root. `base_url` / `base_url_expr` are written only to `HTTPAPIConfig` in the shared runtime module, while route/runtime clients depend on `APITransport`. The default `runtime_profile = "modern"` emits `.iOS(.v15)` and uses modern `URLSession` async APIs; explicit `runtime_profile = "ios14-compat"` emits `.iOS(.v14)` and swaps only the HTTP transport for continuation/delegate-based compatibility code, including ordinary byte streams, SSE, and WebSocket bridges, without changing the wire protocol, DTOs, route names, or typed error contracts. DTOs are `Codable, Sendable`; route-local Markdown Binary Schema helpers generate field-level packet structs and `APIBinaryReader` / `APIBinaryWriter` codecs. The default URLSession transport supports query/json/urlencoded/multipart/binary_schema/open requests, binary_schema/bytes/file/byte_stream responses, typed errors, SSE STREAM bridges, and WebSocket CHANNEL bridges. `HTTPAPIConfig` accepts coding factories, chunk size, error body/SSE/WebSocket payload limits, stream buffer size, and multipart memory threshold; URL/header/multipart/payload failures throw `APITransportError`. The generator does not emit UI, auth, signing, 401 handling, environment selection, cache, retry, token storage, a session owner, or singleton app state.
- `kotlin-client`: emits an OkHttp + kotlinx.serialization client. Through the shared transport abstraction it generates RPC, STREAM, and CHANNEL route surfaces, and supports query/json/urlencoded/multipart/binary_schema/open request kinds plus `none` / `code_message_data` / `ok_data_error` response envelopes. Route DTOs are written to `Gen<Group>Types.kt` while Kotlin public declaration names stay unchanged; binary schema helpers are route-local packet / wire helper types in `GenBinaryTypes.kt`. `base_url` / `base_url_expr` are used by the generated OkHttp HTTP adapter config, while route/runtime clients stay transport-neutral. The built-in OkHttp adapter covers RPC query/json/urlencoded/multipart/binary_schema requests, supports per-call `ApiRequestOptions`, returns typed packets for binary_schema success responses, returns `ApiRawResponse` for bytes/file raw responses, returns true streaming closeable `ApiStreamResponse` / `InputStream` values for byte streams, uses SSE for STREAM, and uses OkHttp WebSocket for CHANNEL.
- `kotlin-server`: emits a preview Ktor server scaffold with route service interfaces, stubs, runtime, and Ktor route registration. Route DTOs and binary schema helpers use the same Kotlin serialization model as the client. RPC HTTP adapters cover query/json/urlencoded/multipart/binary_schema inputs; binary_schema, bytes, file, and byte_stream success responses bypass the JSON envelope, and byte_stream is written through Ktor's streaming writer; STREAM routes generate SSE bridges and CHANNEL routes generate Ktor WebSocket bridges, without generating a host session engine, auth, retry, cache, room management, or connection orchestration.
- `java-client`: emits a preview Java 17 client using `java.net.http.HttpClient` and Jackson, with transport-neutral route surfaces and a default JDK HTTP adapter. RPC query/json/urlencoded/multipart/binary_schema calls are usable; route methods expose `GenApiRequestOptions` overloads for per-call headers and timeout; binary_schema success responses return typed packets, bytes/file raw responses return `GenApiRawResponse`, byte streams return true streaming `GenApiStreamResponse` / `InputStream` / `AutoCloseable` values, route DTOs and binary schema helper records live in `Gen<Group>Types.java`; STREAM and CHANNEL default to explicit unsupported errors so projects can swap in custom transports.
- `java-server`: emits preview Spring MVC controller/delegate artifacts: root-level `annotations/ApiBlueprintOperation.java`, route-local generated Spring Controllers under `routes/<root>/<group...>/controllers/`, business delegate interfaces under `routes/<root>/<group...>/delegates/`, JavaBean request/response types under `routes/<root>/<group...>/types/`, conversion helpers under `routes/<root>/<group...>/adapters/`, and `spring/GenSpringMvcContractAssertions`. It does not generate Services, Stubs, `GenSpringServerConfig`, SSE/WebSocket bridges, or a standalone HTTP server adapter. Business code implements the generated delegates; public Spring mappings are owned by generated Controllers, and tests inject Spring `RequestMappingHandlerMapping` for runtime contract assertions.
- `python-server`: emits Python route service contracts/stubs and a FastAPI HTTP adapter scaffold. `python_package_root` controls the generated package root. The FastAPI adapter covers query/json/urlencoded/multipart/binary_schema, raw responses, response envelopes, typed errors, SSE, and WebSocket protocol bridging.
- `python-client`: emits an async-first Python HTTP client. `python_package_root` controls the generated package root, `create_client(base_url)` is the recommended aggregate facade, route DTOs use `gen_types.py`, route RPC methods accept keyword-only `headers` and `timeout`, binary schema codecs use route-local `gen_binary.py` and are re-exported through `gen_types.py`, and `base_url` / `base_url_expr` are used by the HTTP transport adapter. The default httpx adapter implements RPC query/json/urlencoded/multipart/binary_schema requests, binary_schema success responses, bytes/file raw responses, and byte stream responses; STREAM/CHANNEL connection transports are preview/custom extension points.
- `grpc-proto`: emits `.proto` files and service definitions from ContractGraph. `[[targets.proto_files]]` or the `[[grpc.proto.proto_files]]` shortcut can map DSL schema module/name plus route path/id/service to a specific proto file/package/go_package/service. HTTP raw media routes are not projected into gRPC automatically; model equivalent capabilities as protobuf `bytes` fields or streaming chunk messages.
- `grpc-go`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` to generate Go protobuf/gRPC stubs.
- `grpc-python`: consumes a `grpc-proto` target in the same config, or handwritten proto files directly, and calls `grpcio-tools` to generate Python protobuf/gRPC stubs. `python_package_root` places generated files under a package root and rewrites generated imports.
- `ir-plugin`: calls a host-maintained Python plugin to read ContractGraph, route selection, and target options, then generate project-owned artifacts. It must use canonical `[[targets]]` with `kind = "ir-plugin"`, `plugin`, and `out_dir`. `plugin` is an importable Python module that exposes `generate(context)`; `include` / `exclude` trim the selected routes passed to the plugin, and `[targets.options]` is plugin-defined configuration.

Flutter / Swift / Kotlin / Java / Python client/server, `api-gen check`, and contract / agent artifact projection use the same planner / capability metadata. If a target capability does not support a route, request kind, or response envelope, generation should fail before writing a partial output tree. Wails/gRPC keep HTTP multipart, `Content-Disposition`, HTTP status/header, MIME download, and HTTP byte stream semantics explicitly unsupported, and errors point to native equivalents such as Wails RPC descriptors/STREAM chunks or protobuf bytes/streaming chunks.

`ir-plugin` options, `Blueprint.EXPORT_MODELS(..., **metadata)`, and `message_variant(..., **metadata)` enter the ContractGraph manifest, so they must use JSON-safe string, number, boolean, array, object, or null values; do not pass Python paths, date/time values, class instances, functions, or similar objects.

## Runtime Production Configuration

`api-blueprint.toml` defines protocol and generation targets; it does not directly own host-application production runtime policy. Timeouts, headers, cookies, proxy/TLS, connection pools, retry, auth, rate limits, logging, tracing, file permissions, and complex backpressure should be configured through generated request options, transport config, native HTTP/gRPC clients, service implementations, middleware/plugins/filters, or the Wails app shell.

HTTP server adapters generate finite safety defaults so the default public surface does not read unbounded request bodies or long-connection queues:

- Go: `httptransport.ServerConfig` / `DefaultServerConfig()` / `SetServerConfig(...)`, defaulting request bodies to `16 MiB`, multipart memory to `8 MiB`, single files to `32 MiB`, decompressed binary bodies to `16 MiB`, WebSocket origin checks on, and compression off.
- Kotlin: `ApiServerConfig`, passed as `register*Routes(..., config = ApiServerConfig())`, defaulting multipart files to `32 MiB`, binary bodies to `16 MiB`, and WebSocket messages to `1 MiB`.
- Python: `ApiServerConfig`, accepted by `create_router(..., config=None)` and `create_<group>_router(..., config=None)`, defaulting bodies to `16 MiB`, multipart file/part to `32 MiB`, SSE queue capacity to `256`, and WebSocket messages to `1 MiB`.

The Java `java-server` target emits Spring MVC Controllers but not a standalone HTTP server adapter, so it has no generated server resource-limit config. The host Spring application continues to own MVC setup, filters, interceptors, AOP, request-size limits, and deployment-layer guards. Generated `GenSpringMvcContractAssertions` checks public routes, duplicate/manual public mappings, operation markers, policy annotations, and delegate/request/response boundaries.

These settings are a floor for generated adapters, not a replacement for reverse proxies, framework-level request size settings, application auth, or deployment resource limits. Production projects should prefer concrete route clients, concrete transport factories, or concrete group routers, keeping aggregate facades for development and examples.

ContractGraph collects language-agnostic typed errors from `Blueprint(errors=...)` and route `.ERR(...)`. Manifest `2.0` keeps the global `errors` table for complete definitions and writes compact route-local refs (`id/group/key/code/message/toast`) into `routes[].errors`, so callers can inspect the error surface from the route they are invoking. `id` is the public protocol error identity; `code` is a business code and may be reused across groups or routes. `ResponseEnvelope` decides the wire shape, and manifest writes `name/kind/error_identity/success_code/success_message/fields` under `response.envelope`. The default `CodeMessageDataEnvelope` returns `{ code: 0, message: "ok", data }` on success and `{ code, message, data: null, error: { id, group, key, toast } }` on failure; strict `{ code, message, data }` output uses `LegacyCodeMessageDataEnvelope` without `id`; choose `OkDataErrorEnvelope` explicitly for `{ ok, data/error }`. Main generators expose language-native typed error helpers; Java generator-owned error types use `GenApiError`, `GenApiErrors`, `GenApiErrorPayload`, and related `Gen*` names. Default Go, TypeScript, Flutter, Swift, Python, Kotlin, and Java client transports restore typed errors from the envelope spec. Business i18n resolves the current language by toast key, and client helpers fall back through `toast.text`, external i18n, `toast.default`, then `message`. Business error codes are not forced to equal HTTP status codes.

The Kotlin client/server output layout is `<package>/<root>/runtime/*`, `<package>/<root>/routes/<root>/<group...>/*`, and `<package>/<root>/transports/http/*`. `Gen*.kt` files are generator-owned; non-`Gen*` façade / extension files are user-owned. The client preserves route façade and HTTP client façade files; the server preserves `<Group>Service.kt` implementations.

The Go client output layout is `runtime/*`, `routes/<root>/<group...>/*`, and `transports/http/*`. `gen_*.go` files are generator-owned, while `client.go` façades are user-owned and preserved during regeneration. `base_url` / `base_url_expr` are written only to the HTTP transport config, not route/runtime clients.

The Flutter client output layout is `lib/<package>.dart`, `lib/gen_<package>.dart`, `lib/<root>.dart`, `lib/gen_<root>.dart`, `lib/src/<root>/<root>.dart`, `lib/src/<root>/gen_<root>.dart`, `lib/src/<root>/runtime/*`, `lib/src/<root>/routes/<root>/<group...>/*`, and `lib/src/<root>/transports/http/*`. `gen_*.dart` files are generator-owned; public entries, `api_client.dart`, `api_json_codecs.dart`, `http_api_client.dart`, route façades, type façades, and `binary.dart` are preserved user files. `package` is normalized to a Dart package name, and `base_url` / `base_url_expr` are written only to the HTTP transport config.

The Swift client output layout is `Package.swift`, `Sources/<module>/<module>.swift`, `Sources/<module>/Gen<module>.swift`, `Sources/<module>/Transports/HTTP/HTTPAPIClient.swift`, `Sources/<module>Runtime/*`, `Sources/<module>Runtime/Transports/HTTP/*`, `Sources/<module><Root>Routes/<root>/<root>RootClient.swift`, `Sources/<module><Root>Routes/<root>/Gen<root>RootClient.swift`, and `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/*`. `Package.swift` and `Gen*.swift` files are generator-owned and carry the `Code generated` header; `Package.swift` is rewritten to match the current SwiftPM aggregate/runtime/root target list, with `Package(name:)` using `package` and products/targets using names derived from `module`. Package/root façades, route façades, type façades, `APICoding.swift`, and `HTTPAPIClient.swift` are created only when missing, then owned by the user and written without the generated header. `runtime_profile` is a runtime code generation compatibility switch, not a protocol compatibility switch; set it to `ios14-compat` explicitly when iOS 14 runtime support is required. Multi-root projects emit one `<module>` aggregate module, one shared `<module>Runtime` runtime module, and one `<module><Root>Routes` module per root, so a `/runtime` root emits `<module>RuntimeRoutes` instead of occupying the shared runtime module.

For host architectures such as an iOS app shell, put the generated Swift SDK under Core Networking as the protocol DTO/client layer. The app-owned `APIClient` should wrap or inject `APITransport` and own environment selection, auth/signing, 401 handling, retry, cache, session ownership, token storage, logging, and monitoring. Generated stream/channel route methods now expose URL or configuration failures with `throws`; reconnect, foreground/background lifecycle, and session policy still belong to the host app. The generator provides protocol boundaries and keyframes only; it does not own those runtime policies.

The Java client output layout is `<package>/<root>/runtime/*`, `<package>/<root>/routes/<root>/<group...>/*`, and `<package>/<root>/transports/http/*`. `out_dir` is the package root and does not include `src/main/java`. The client preserves `ApiClient.java`, `<Group>Api.java`, and `HttpApiClient.java`; other generated Java files and public types use `Gen*`. DTOs use Java 17 `record`, fields use Jackson `@JsonProperty`, and enums use `@JsonCreator` / `@JsonValue` to preserve wire values.

The Java server output layout is `<package>/<root>/runtime/*`, `<package>/<root>/annotations/ApiBlueprintOperation.java`, `<package>/<root>/routes/<root>/<group...>/{controllers,delegates,types,adapters}/*`, and `<package>/<root>/spring/*`. `Gen*.java` files are generator-owned; project policy annotations, delegate implementations, legacy DTO/VO classes, and services remain host-owned. Protocol policy semantics such as signing or auth belong in DSL providers; Java target `spring_policy_mappings` only maps provider names to host Spring annotation classes.

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

- `http-transport`: declares an HTTP server/client combination. `server` can reference a `go-server`, `kotlin-server`, or `python-server`; `clients` can reference Go, TypeScript, Flutter, Swift, Kotlin, Java, or Python clients. Java `java-server` is a Spring controller/delegate target, not an HTTP server adapter target.
- `wails-transport`: declares a Wails overlay and must set `version`, `server`, and `clients`. Wails remains Go + TypeScript only and does not attach Flutter / Kotlin / Java / Python clients. HTTP raw media routes are not projected into Wails automatically; model equivalent capabilities as normal RPC payloads, app-local file descriptors, STREAM/CHANNEL chunks, or app-managed temp files/caches.
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
