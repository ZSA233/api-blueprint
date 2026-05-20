# Generators

This page covers the main non-Wails, non-gRPC generators. See [Wails](wails.md) for Wails and [gRPC](grpc.md) for gRPC.

## Shared Planning And Capabilities

`api-gen check`, contract / agent artifact projection, and language writers use the same planner / capability metadata. Before generation, target dependencies, route kinds, request kinds, and response envelopes are validated consistently, avoiding cases where check passes and a writer later discovers unsupported input.

Generator status and path conventions are part of the shared planning surface. Go server is available; Go client, Flutter, Kotlin, Java, and Python targets are preview surfaces. Go server / Go client / Wails Go contract and agent artifact paths use Go-safe route package segments, for example `/api-v1` -> `api_v1` and `/admin/v1` -> `admin_v1`. Flutter / Kotlin / Java / Python artifact paths follow their language-specific route output layout, for example `routes/api/demo`.

Markdown Binary Schema generated names use the same collision policy across targets: packet entry names remain packet-based, while schema-internal struct / enum / bitflags / state / helper symbols are scoped by packet name. Packet names that normalize to the same generated symbol are rejected during generation. Public binary packet fields follow target-language conventions: Go / Kotlin / Java / Flutter use exported or camelCase field names, while TypeScript / Python keep snake_case fields close to the JSON / wire names.

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

The Go generator emits:

- Route interfaces and default `impl.go`.
- Request / response / context structures.
- Provider runtime and response envelope codecs.
- Transport-neutral Go core.
- Optional HTTP/Gin adapter.

`gen_*` files are generator-owned and overwritten during regeneration. `impl_*` and non-`gen_*` files are user-owned extension points and are preserved. Flutter uses Dart-style `gen_*.dart` for generator-owned files and keeps non-`gen_` façade / extension files user-owned; Kotlin / Java follow the same ownership model with `Gen*.kt` and `Gen*.java` plus runtime generated files.

`go-server` owns only the Go server core. `out_dir` is the generated package root; projects that want `views` in import paths should include `views` in `out_dir`. HTTP / Wails output is attached explicitly by `http-transport` / `wails-transport` targets through `server = "go.server"`. The HTTP entrypoint is generated under `<out_dir>/transports/http/<go-root-segment>`, for example `transports/http/api.NewBlueprint(engine)`.

Go route core is generated under `<out_dir>/routes/<go-root-segment>/**`, provider runtime under `<out_dir>/providers`, transport adapters under `<out_dir>/transports/**`, and typed error runtime under `<out_dir>/runtime/errors/**`. Go-safe segments replace non-`[0-9A-Za-z_]` characters with `_`, trim leading/trailing `_`, prefix digit-leading names with `p_`, and suffix Go keywords with `_pkg`; URLs, route paths, and selection/filter semantics stay unchanged, so Go directories do not guarantee one directory per URL slash segment. If you want the import path to include `/views`, set `out_dir = ".../views"` explicitly.

`providers` is a global transport-neutral runtime under the generated package root and is not split per blueprint root. TypeScript's per-root `runtime` mainly isolates model and client names; it is not the same responsibility as Go provider hooks.

When a provider implementation must vary by root, route, or transport, do not parse the request path. The generator writes `RouteInfo` into every route executor and exposes it through `Context.Route` and `ProviderSpec.Route`:

```go
providers.RegisterProviderFactory(providers.PROV_RSP, func(spec providers.ProviderSpec) providers.Provider {
	if spec.Route.Root != "static" {
		return nil
	}
	// Optional: spec.Handler is the current route's typed handler and can be type-asserted when needed.
	return NewCachedRspProvider(spec.Data)
})
```

Custom providers can be inserted into the pipeline from the DSL with `provider.Custom(name, data)`:

```python
from api_blueprint.engine import Blueprint, provider

bp = Blueprint(
    root="/static",
    providers=[
        provider.Req(),
        provider.Custom("cache", "ttl=60s"),
        provider.Handle(),
        provider.Rsp(),
    ],
)
```

Register provider factories during application startup or package `init()`. The provider sequence is parsed only when the executor is created, and factories also run only at creation time. The high-concurrency request path only executes cached provider instances. If a project needs selection logic without the global registry, implement `SelectProvider(spec, handler)` in the user-owned `providers/impl_provider.go`.

#### Compatibility

Projects using the older `Select(key, value, handler)` provider hook should migrate that logic to `SelectProvider(spec, handler)` so route metadata stays explicit.

The HTTP adapter imports the blueprint root router only when the root has direct routes. If a handler has already written a Gin response, the adapter does not append an automatic response; otherwise routes without an `rsp` provider keep the existing behavior where the adapter writes the handler return value.

Use `HTTP_RAW_RESPONSE()` when the handler fully owns the successful HTTP response. This affects only the HTTP adapter: success does not write an automatic response, and errors return 500 only when the Gin writer has not written yet. It is not a shared provider and does not change Wails overlays.

### Long-Connection Contracts

Go core generates transport-neutral handler interfaces for `STREAM` / `CHANNEL`. Business code does not directly depend on SSE, WebSocket, or Wails event names:

```go
Events(
	ctx *CTX_Events,
	stream STREAM_Events,
) error
Chat(
	ctx *CTX_Chat,
	channel CHANNEL_Chat,
) error
```

In the HTTP transport, `STREAM` generates an SSE adapter and `CHANNEL` generates a WebSocket adapter. In the Wails transport, both are backed by session-scoped runtime events by default. Multi-message variants generate one shared union schema with a `type` discriminator; do not split variants into multiple transport events. `.CLOSE(Model)` is part of the Go handler generic and the TypeScript `onClose` type; server business writes and closures are context-first (`Send(ctx, msg)`, `Close(ctx, close)`, `Abort(ctx, code, reason)`).

The default HTTP/Wails runtimes fully implement only `ConnectionScope.SESSION`. `APP` / `TOPIC` remain in the route contract and can be implemented later through a custom connection hub / manager for broadcast or topic routing; the generator does not bake in business fan-out policy.

Named variant-union messages generate stable helpers while keeping the same `{ type, data }` wire shape. Go server and Go client output place message unions, `NewXxxMessageVariant(...)`, and `DecodeVariant()` in `gen_messages.go`; message keyframes live in `gen_message_cases.go`: `XxxMessageProcessor[C]`, `VisitXxxMessage(ctx, message, processor)`, lazy `XxxMessageVariantCase.Decode()`, and typed helpers such as `AsXxxMessageError(...)` / `IsXxxMessageErrorKind(...)`. The visitor handles only one message and does not own the `Recv` loop, middleware, close/abort decisions, write path, or error policy; applications keep those runtime decisions in their route/app layer.

TypeScript, Flutter, Python, Kotlin, and Java use language-native lightweight helpers instead of copying the Go visitor shape. TypeScript emits `XxxMessageVariants.variant(data)`, `dispatchXxxMessage(message, handlers)`, and typed unknown-message dispatch errors. Flutter emits Dart 3 `sealed class XxxMessage`, final variant classes, `XxxMessageVariants.variant(data)`, and `dispatchXxxMessage(...)`. Python emits dataclass `XxxMessage`, `XxxMessageVariants`, `XxxMessageHandlers`, `dispatch_xxx_message(...)`, and `XxxMessageDispatchError` in route `gen_types.py` for both client and server output. Kotlin emits `@Serializable data class XxxMessage(type, data)`, `object XxxMessageVariants`, `XxxMessageHandlers<R>`, `dispatchXxxMessage(...)`, and `XxxMessageDispatchException`; the runtime exposes `ApiJson` for generated encode/decode. Java emits nested `record XxxMessage(String type, JsonNode data)`, variants, handlers, dispatch, and dispatch exception helpers inside the route `<Group>Types.java`, with `ApiJson.MAPPER` as the shared Jackson holder. These helpers support constructing `CHANNEL` client messages and dispatching server pushes, but they still do not implement the host application's connection session engine.

Go server also creates three user-owned scaffold files the first time it sees a `CHANNEL` with a named client message: `<leaf>_session.go`, `<leaf>_processor.go`, and `<leaf>_error.go`. These files do not carry a `Code generated` marker, and later generations create them only when missing instead of overwriting user edits. The default shell gives humans and AI agents stable places for the route handler, `Recv` loop, `VisitXxxMessage(...)`, `OnXxx` processor methods, and message error policy; it is still an editable starting point, not a generator-owned session engine, and it does not bind the route to appkit, a hub, middleware, or a close policy.

Non-scaffold generated connection handlers still default to `not implemented`, so example business logic is not written into every user project. The repository example keeps the `STREAM` usage in the user-owned `examples/golang/server/views/routes/api/demo/impl.go`, showing `Open()`, message constructors, context-aware `Send(...)`, and typed `Close(...)`; the `CHANNEL` example lives in `assistant_session_session.go`, `assistant_session_processor.go`, and `assistant_session_error.go`, where `OnXxx` methods use the scaffold scope's `Context`, route `CTX_*`, and channel.

### Typed Errors

ContractGraph collects `Blueprint(errors=...)` and route `.ERR(...)` declarations into language-agnostic typed errors. Manifest `2.0` keeps a global `errors` definition table and writes compact route-local refs (`id/group/key/code/message/toast`) into `routes[].errors`, so generated clients and `api-gen inspect errors --route ...` can show the error surface from the route being called. `id` is the public protocol error identity; `code` is only a business code and may be reused across groups or routes. `ResponseEnvelope` decides the wire shape: the default `CodeMessageDataEnvelope` uses `{ code, message, data, error? }`, strict `{ code, message, data }` output can opt into `LegacyCodeMessageDataEnvelope`, and `{ ok, data/error }` is available only when selecting `OkDataErrorEnvelope`.

Generated runtime APIs use user-facing names such as `ApiError`, `ApiErrors`, `ApiErrorsByID`, `lookupApiError`, and `isApiError`; catalog dictionaries are internal indexes rather than the primary surface. Default Go, TypeScript, Flutter, Python, Kotlin, and Java client transports unwrap by the route envelope spec, resolve the payload by `id`, then by `(route_id, code)`, then by global code fallback, and throw or return a typed `ApiError`. Go server grouped errors under packages such as `runtime/errors/common_err` return typed `ApiError` values; `WithToast(...)` returns an immutable override copy for request-language, tenant, or rollout-specific dynamic `toast.text`. Business i18n resolves the current language by toast key, and client helpers resolve display text in the order `toast.text`, external i18n, `toast.default`, then `message`. HTTP status remains transport state and is not derived from business error codes.

A Go server handler can return generated typed errors directly, or return an undeclared business code to exercise client unknown fallback:

```go
switch req.Q.Mode {
case "token":
    return nil, common_err.TOKEN_EXPIRE
case "rate_limit":
    return nil, demo_err.RATE_LIMITED.WithToast(apperrors.ToastPayload{
        Key: "demo.rate_limited", Level: "warning",
        Default: "Too many requests. Please try again later.", Text: "Please retry in 30 seconds.",
    })
case "unknown":
    return nil, apperrors.New(70001, "example undefined business error")
}
```

The TypeScript client throws `ApiError` from the default HTTP transport. Business code usually checks the type, branches by `id/code`, and uses the toast helper to resolve display text:

```ts
try {
  await demoClient.errorDemo({ query: { mode: "rate_limit" } });
} catch (error) {
  if (isApiError(error) && error.id === "DemoErr.RATE_LIMITED") {
    const text = resolveApiToast(error.toast, translate, error.message);
    showToast(text);
  }
}
```

Kotlin has generated snapshots and compile validation. The catch shape is the same as other clients:

```kotlin
try {
    apiClient.demo.errorDemo(DemoErrorDemoQuery(mode = "rate_limit"))
} catch (error: ApiError) {
    if (error.id == "DemoErr.RATE_LIMITED") {
        val text = resolveApiToast(error.toast, translate = ::translate, fallbackMessage = error.message.orEmpty())
        showToast(text)
    }
}
```

The repository’s `/api/demo/error-demo` example and Go / TypeScript / Kotlin / Flutter / Python / Java validation cover declared errors, route-local errors, dynamic `toast.text`, and fallback for undeclared error codes.

## Go Client

```sh
api-gen generate -c api-blueprint.toml --target go.client
```

The Go client target emits a preview HTTP client:

- `runtime/gen_*.go`
- `runtime/gen_types.go`
- `runtime/binary/gen_runtime.go`
- `gen_client.go` / `client.go` at the target root for the aggregate public facade
- `routes/<go-root-segment>/<go-group-segment>/gen_client.go`
- `routes/<go-root-segment>/<go-group-segment>/gen_types.go`
- `routes/<go-root-segment>/<go-group-segment>/gen_binary.go`, generated only for binary schema route groups
- `routes/<go-root-segment>/<go-group-segment>/client.go`
- `transports/http/gen_config.go`
- `transports/http/gen_transport.go`
- `transports/http/client.go`

`gen_*.go` files are generator-owned and overwritten; `client.go` façades are user-owned and preserved. The recommended entrypoint is `apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})`, then route calls such as `api.Demo.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "token"})`. Route/runtime clients depend only on the transport abstraction, while `base_url` / `base_url_expr` are written only to the HTTP transport config. The default HTTP adapter implements RPC query/json/form/binary requests. STREAM and CHANNEL methods are generated, but the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.

## TypeScript

```sh
api-gen generate -c api-blueprint.toml --target typescript.client
```

The TypeScript client target emits:

- `types.ts` / `gen_types.ts`.
- Request client classes.
- Transport-neutral `ApiClientConfig`.
- `createClients(config)` facades injected by transport targets.
- The `api/transports/clients` aggregate entrypoint; when multiple transports are generated it exports the shared client subset as `CommonGeneratedClients` plus `createClientsForTransport({ transport })`.
- User-owned passthrough files such as `client.ts`, `transport.ts`, and `factory.ts`.

`base_url` / `base_url_expr` are owned by generated HTTP transport facades, not route/runtime clients. `base_url_expr` is emitted verbatim into generated code, which fits runtime configuration in Vite, Next.js, and similar projects. It is mutually exclusive with `base_url`.

`STREAM` / `CHANNEL` generate `ApiStreamBridge<Recv, Close>` and `ApiChannelBridge<Recv, Send, Close>`. Single-message directions use the model type directly; multi-message directions generate discriminated union types such as `{ type: "progress"; data: TaskProgress }`. The HTTP transport stream bridge uses SSE, the channel bridge uses WebSocket with an internal envelope to distinguish normal messages from close lifecycle payloads, and the Wails transport uses generated runtime events without exposing event names to business clients.

Markdown Binary Schema helpers are route-local `gen_binary.ts` implementation files and are re-exported through `types.ts`. Route clients import packet helpers from the route types surface.

## Flutter Client

```sh
api-gen generate -c api-blueprint.toml --target flutter.client
```

The Flutter client target emits a pure Dart package that Flutter Android/iOS apps can depend on directly. The generated package does not generate Flutter UI, app lifecycle, state management, auth, retry, cache, or a session engine.

A typical output layout is:

- `lib/<package>.dart`
- `lib/src/<root>/<root>.dart`
- `lib/src/<root>/runtime/gen_api_transport.dart`
- `lib/src/<root>/runtime/gen_api_client.dart`
- `lib/src/<root>/runtime/gen_api_errors.dart`
- `lib/src/<root>/runtime/gen_api_error_lookup.dart`
- `lib/src/<root>/runtime/gen_api_types.dart`
- `lib/src/<root>/runtime/binary/gen_binary_runtime.dart`
- `lib/src/<root>/runtime/api_client.dart`
- `lib/src/<root>/runtime/api_json_codecs.dart`
- `lib/src/<root>/routes/<root>/<group...>/gen_<group>_api.dart`
- `lib/src/<root>/routes/<root>/<group...>/gen_<group>_types.dart`
- `lib/src/<root>/routes/<root>/<group...>/gen_binary.dart`
- `lib/src/<root>/routes/<root>/<group...>/<group>_api.dart`
- `lib/src/<root>/routes/<root>/<group...>/<group>_types.dart`
- `lib/src/<root>/routes/<root>/<group...>/binary.dart`
- `lib/src/<root>/transports/http/gen_http_api_config.dart`
- `lib/src/<root>/transports/http/gen_http_api_transport.dart`
- `lib/src/<root>/transports/http/gen_http_connection.dart`
- `lib/src/<root>/transports/http/http_api_client.dart`

`gen_*.dart` files are overwritten by the generator. `api_client.dart`, `api_json_codecs.dart`, `http_api_client.dart`, route façades, type façades, and `binary.dart` are created only when missing and then owned by the user. The `ApiJsonCodec<T>` registry in `api_json_codecs.dart` lets projects plug in `build_runner` or handwritten codecs; without an override, generated manual `fromJson` / `toJson` code is used.

Runtime entrypoints include the aggregate `ApiClient` façade, route clients such as `DemoApi`, DTO `fromJson` / `toJson`, `ApiError`, `lookupApiError`, `ApiTransport`, `ApiStreamBridge`, `ApiChannelBridge`, and binary `Uint8List` codecs. The default HTTP transport uses `package:http` for RPC query/json/form/binary requests, SSE for STREAM bridges, and `web_socket_channel` for CHANNEL bridges. `base_url` / `base_url_expr` are written to HTTP config, not route/runtime clients.

Markdown Binary Schema helpers live in route-local `gen_binary.dart`; the shared binary reader/writer runtime lives in `runtime/binary/gen_binary_runtime.dart`. Dart public fields use lowerCamelCase while diagnostics keep the schema's original field names.

## Kotlin Client / Server

Kotlin targets are preview surfaces and use kotlinx.serialization for DTOs, typed errors, and message keyframe helpers. `kotlin-client` focuses on the OkHttp client path; `kotlin-server` focuses on a Ktor HTTP RPC adapter and service scaffold.

### Kotlin Client

```sh
api-gen generate -c api-blueprint.toml --target kotlin.client
```

The Kotlin client target emits an OkHttp + kotlinx.serialization client.

Kotlin emits a package-first layout whose route directory mirrors the full route path:

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

Kotlin generator-owned files are named `Gen*.kt`, for example `routes/api/demo/GenDemoApi.kt` and `runtime/GenApiClient.kt`, and include a generated header. Non-`Gen*` façade files such as `DemoApi.kt`, `runtime/ApiClient.kt`, and `transports/http/HttpApiClient.kt` are preserved user extension points.

Route DTOs are emitted as `<Group>Types.kt`. Markdown Binary Schema helpers are route-local packet / wire helper types in `BinaryTypes.kt` in the same package as the route API.

Through the transport abstraction, Kotlin generates `rpc`, `stream`, and `channel` route surfaces, and supports query/json/form/binary/open request kinds plus `none` / `code_message_data` / `ok_data_error` response envelopes. The built-in OkHttp adapter covers RPC query/json/form/binary requests, uses SSE for `STREAM` bridges, and uses OkHttp WebSocket for `CHANNEL` bridges; it implements protocol transport only, not the host application's session engine, retry, cache, or connection orchestration.

`base_url` / `base_url_expr` are written into the generated `transports/http/HttpApiConfig.kt` default, not into the transport-neutral runtime client.

### Kotlin Server

```sh
api-gen generate -c api-blueprint.toml --target kotlin.server
```

The Kotlin server target emits a Ktor-oriented scaffold:

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/<Group>Types.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Service.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>ServiceStub.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>Service.kt`
- `<package>/<root>/transports/ktor/<root>/<group...>/Gen<Group>KtorRoutes.kt`

`Gen<Group>Service.kt`, `<Group>ServiceStub.kt`, `<Group>Types.kt`, runtime `Gen*.kt` files, and `Gen<Group>KtorRoutes.kt` are generator-owned. `<Group>Service.kt` is a preserved user file and defaults to extending the generated stub.

RPC Ktor routes decode query/json/form/binary inputs, call the generated service interface, and wrap success or generated `ApiError` values through the route response envelope. `STREAM` routes generate an SSE bridge, and `CHANNEL` routes generate a Ktor WebSocket bridge; open payloads are decoded from query parameters, and message/close/client message payloads use the generated serializers. This is only protocol bridging and keyframes; it does not generate the host application's session engine, auth, retry, cache, room management, or connection orchestration.

### Kotlin Compatibility

Projects using the earlier `<package>/ApiClient.kt`, `endpoints/`, `models/`, and `internal/` layout should import from `<package>.<root>.runtime`, `<package>.<root>.routes...`, and `<package>.<root>.transports.http` after regeneration.

## Java Client / Server

```sh
api-gen generate -c api-blueprint.toml --target http.java
```

Java targets are preview. `java-client` uses Java 17 `java.net.http.HttpClient` plus Jackson; `java-server` uses Spring MVC plus Jackson. Generated sources do not include Gradle/Maven project files, and `out_dir` is the package root without an appended `src/main/java`. The repository example provides `make example-java-suite` to run a real Spring Boot server and generated Java client core round-trip.

Java client/server use a package-first layout whose route directory mirrors the full route path:

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

Route DTOs are emitted as `<Group>Types.java`. Markdown Binary Schema typed packets and wire helpers are also folded into that route types container, for example `BinaryTypes.DemoPacket` / `BinaryTypes.DemoPacketWire`.

The Java client emits transport-neutral route surfaces, `ApiTransport`, the default JDK HTTP adapter, and `GenApiClient`. Preserved user files are `runtime/ApiClient.java`, `routes/<root>/<group...>/<Group>Api.java`, and `transports/http/HttpApiClient.java`; other `Gen*.java` and runtime generated files are overwritten. The recommended entrypoint is `HttpApiClient.create(baseUrl)`, with public DTOs such as `DemoTypes.ErrorDemoQuery` / `DemoTypes.ErrorDemoResponse`. The default HTTP adapter implements RPC query/json/form/binary/binary-schema requests, while STREAM and CHANNEL default to explicit unsupported errors.

The Java server emits route service interfaces, public stubs, runtime, route types, and Spring controllers. For `.REQ_BINARY(...)`, the generated Spring controller parses request bytes into the generated typed packet before calling the service. `STREAM` routes use a Spring `SseEmitter` bridge, and `CHANNEL` routes generate a WebSocket handler/config compatible with the `{type:"message",data}` / `{type:"close",data}` wire shape. The preserved user file is `routes/<root>/<group...>/<Group>Service.java`; `<Group>Types.java`, `<Group>ServiceStub.java`, `Gen<Group>Service.java`, and `transports/http/<root>/<group...>/Gen<Group>Controller.java` are generator-owned. Connection output provides only protocol bridging; it does not generate a host session engine, auth, retry, cache, or room management.

DTOs use Java 17 `record`; fields use Jackson `@JsonProperty`; enums use `@JsonCreator` / `@JsonValue` to preserve wire values. `module` is only a shortcut-table alias normalized to `package`; no JPMS `module-info.java` is generated.

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client uses `python_package_root` as its package root and emits an async-first HTTP client:

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`gen_client.py` / `client.py` at the root provide the aggregate facade, and the recommended entrypoint is `async with create_client(base_url) as api`. Route method public facades use typed dataclass DTOs and no longer expose `Mapping[str, Any]` as the normal request entrypoint; use the transport directly when a raw dict/body escape hatch is needed. `routes/<root>/<group...>/gen_client.py` is the generated route client, `routes/<root>/<group...>/gen_types.py` is the route DTO and binary public export surface, `routes/<root>/<group...>/client.py` is the preserved passthrough entrypoint, `runtime/gen_codecs.py` contains shared decode/encode helpers, and `transports/http/gen_client.py` provides the default httpx adapter. Root-level routes are emitted directly under `routes/<root>`, not `routes/root`. That adapter implements RPC requests; STREAM/CHANNEL bridge interfaces are generated, but connection transports need project-specific customization or later extension. `base_url` / `base_url_expr` are used by the HTTP transport adapter.

Python DTOs use `@dataclass(kw_only=True)`, Python `Enum` / `StrEnum` / `IntEnum`, and generated codecs. Explicit nested models, arrays, maps, and enum key/value positions are generated and decoded recursively, so a response field such as `dict[str, NestedItem]` is restored as `NestedItem` instances rather than raw dicts. Each DTO emits `from_mapping()`, `from_value()`, and `to_mapping()`; missing required fields, wrong field types, or invalid enum values raise `ValueError` / `TypeError` with a field path. Field attributes are Python-safe names, while JSON/query/form wire names are preserved by the codec.

Markdown Binary Schema codecs are route-local `gen_binary.py` implementation modules; public packet and writer helpers are re-exported from `gen_types.py`.

## Python Server

```sh
api-gen generate -c api-blueprint.toml --target python.server
```

Python server also uses `python_package_root` as its package root and emits route service contracts/stubs plus a FastAPI HTTP adapter scaffold:

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_service.py` is the generated typed service contract, `routes/<root>/<group...>/service.py` is the user-maintained stub entrypoint, and `transports/http/gen_server.py` plus `server.py` provide the FastAPI HTTP adapter scaffold. Root-level routes are emitted directly under `routes/<root>`. The FastAPI adapter decodes query/json/form/open dicts recursively into route DTOs before calling the service, and recursively encodes returned DTO/scalar/list/map values back to JSON; response envelopes and typed error wrapping are still handled by the adapter. `STREAM` routes get `StreamingResponse` SSE bridges, and `CHANNEL` routes get WebSocket bridges with generated DTO codecs for message and close payloads. The Python server `.REQ_BINARY` service boundary receives raw `bytes` and does not generate a server-side binary schema parser, so business code can parse the body as needed. Malformed JSON is treated as a transport input error and returns HTTP 400 rather than a business envelope. The Python server WebSocket runtime needs `websockets` or an equivalent uvicorn WebSocket backend. As a preview target, Python server output should be included in the consuming project's type checks, lint, and install smoke tests.

## Example Snapshots

`examples/golang/server/`, `examples/golang/client/`, `examples/typescript/`, `examples/flutter/`, `examples/kotlin/client`, `examples/kotlin/server`, `examples/java/client` / `examples/java/server`, and `examples/python/` are generated snapshots, not business sources; `examples/java/suite` is a handwritten runtime validation project. `examples/golang/conformance/`, `examples/typescript/conformance.ts`, `examples/kotlin/conformance/`, `examples/java/conformance/`, `examples/python/conformance/`, and `examples/flutter/test/conformance_test.dart` are preserved conformance files whose job is to call each language's generated artifacts against real Go / Java / Kotlin / Python servers, covering RPC, form, binary, typed errors, naming conflicts, and supported SSE/WebSocket interoperability; regeneration must not overwrite them. Go server / Go client / Wails Go contract / agent artifact indexes use Go-safe route package segments, while Flutter / Kotlin / Java / Python artifact indexes keep their language-specific route output paths. To accept intentional generation changes, use:

```sh
make example-refresh
```
