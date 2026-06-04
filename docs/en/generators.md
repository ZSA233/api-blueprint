# Generators

This page covers the main non-Wails, non-gRPC generators. See [Wails](wails.md) for Wails and [gRPC](grpc.md) for gRPC.

## Shared Planning And Capabilities

`api-gen check`, contract / agent artifact projection, and language writers use the same planner / capability metadata. Before generation, target dependencies, route kinds, request kinds, and response envelopes are validated consistently, avoiding cases where check passes and a writer later discovers unsupported input.

Generator status and path conventions are part of the shared planning surface. Go server is available; Go client, Flutter, Swift, Kotlin, Java, and Python targets are preview surfaces. Go server / Go client / Wails Go contract and agent artifact paths use Go-safe route package segments, for example `/api-v1` -> `api_v1` and `/admin/v1` -> `admin_v1`. Flutter / Swift / Kotlin / Java / Python artifact paths follow their language-specific route output layout, for example `routes/api/demo`.

The generated root comes from the Blueprint logical identity slug, not directly from the URL `root` fallback. `Blueprint(root="/api")` still generates the `api` root by default. `Blueprint(name="legacy", root="")` uses `legacy` as the root-level package/module/directory/proto identity in Go, TypeScript, Flutter, Swift, Kotlin, Java, Python, Wails, and gRPC, while route URLs remain real paths such as `/account/profile` and `/room/list`. This lets one SDK / app root own several top-level URL namespaces without inventing a shared URL prefix.

Markdown Binary Schema generated names use the same collision policy across targets: packet entry names remain packet-based, while schema-internal struct / enum / bitflags / state / helper symbols are scoped by packet name. Packet names that normalize to the same generated symbol are rejected during generation. Public binary packet fields follow target-language conventions: Go / Kotlin / Java / Flutter / Swift use exported or camelCase field names, while TypeScript / Python keep snake_case fields close to the JSON / wire names.

HTTP body / response kind is also part of shared planning. Request bodies are recorded as `none`, `json`, `urlencoded`, `multipart`, `binary_schema`, or `raw_bytes`, and responses are recorded as `json`, `xml`, `text`, `binary_schema`, `bytes`, `file`, or `byte_stream`. HTTP generators support multipart, raw media responses, and binary schema request/response handling for Go server/client, TypeScript client, Flutter client, Swift client, Kotlin client/server, Java client/server, and Python server/client.

### Legacy JSON Compatibility

`OneOf(...)` and `CoerceString(...)` are legacy compatibility features. They do not change the existing behavior of ordinary `String`, `Int`, `Array`, or `Map` fields. In ContractGraph, `OneOf` emits `{"type": "one_of", "variants": [...]}` with recursive field manifests for variants; `CoerceString` emits `{"type": "coerce_string", "canonical": {"type": "string"}, "accepts": [...]}`.

Targets project them as follows:

- TypeScript emits native unions such as `string | Array<string>`; nested arrays become shapes such as `Array<string | number>`.
- Python emits annotations such as `str | list[str]`; the generated codec decodes `OneOf` in declaration order and normalizes integer wire values from `LegacyStringID` to `str`.
- Swift emits named enum wrappers for `OneOf` and custom `Codable` where needed; `CoerceString` fields remain public `String` values, decode string or integer JSON numbers, and encode as string.
- Go / Flutter / Kotlin / Java preview targets initially place `OneOf` in the language's JSON/any/JsonNode carrier type; `CoerceString` remains ordinary string and uses a restricted decode helper.
- gRPC proto maps `CoerceString` to protobuf `string`; `OneOf` is not automatically projected as a proto union, so `api-gen check` reports unsupported and points to protobuf-native `oneof` or `JSONValue`.

`CoerceString` accepts only string and integer wire types. Bool, object, array, fractional numbers, and values beyond a target language's integer capability should not be treated as a long-term protocol shape. In particular, TypeScript cannot losslessly recover JSON numbers beyond JavaScript's safe integer range, so legacy ID fields should converge to string over time.
`LegacyStringID` is the recommended shortcut for `CoerceString(accepts=(String, Int))`; `StringOrIntAsString` remains only as a deprecated compatibility alias.

### HTTP Raw Media And Non-HTTP Transports

`multipart`, `Content-Disposition`, HTTP status/header, MIME download, and HTTP byte stream semantics belong to HTTP transports. Wails and gRPC do not project these routes into pseudo HTTP responses; `api-gen check` reports an explicit unsupported contract error for HTTP raw media / binary schema body/response and points to the transport-native modeling path.

For gRPC, use protobuf-native models: small bytes or typed binary packets belong in a `bytes` field; when the exact Markdown Binary Schema wire format must be preserved, place the encoded packet in a `bytes payload` instead of expanding it into proto fields; file downloads should use server-streaming `FileChunk`, with `filename`, `content_type`, `size`, and `sha256` in metadata or the first message and later chunks carrying `bytes data`; file uploads should use client-streaming `UploadChunk`; normal form fields should become explicit request message fields; MJPEG or byte streams should use server-streaming chunk messages, not HTTP multipart boundaries.

For Wails, use IPC / app-runtime models: small bytes or typed binary packets can return base64, number arrays, or a project-owned `Uint8Array` adapter; file downloads should return an app-local file descriptor such as `path`, `filename`, `contentType`, and `size`, with the app shell handling save/open dialogs and filesystem permissions; byte streams should reuse `STREAM` / `CHANNEL` chunks and close payloads; large files should prefer an app-managed temp file/cache.

### Client Request Options

Generated client RPC methods expose per-call request options in the target language's normal style. TypeScript and Wails TypeScript use an `ApiRequestOptions` object with `headers`, `timeoutMs`, and HTTP-only `init`; Flutter, Kotlin, and Swift use `ApiRequestOptions(headers, timeout)`; Java uses `GenApiRequestOptions` overloads; Python uses keyword-only `headers` and `timeout`; Go uses `context.Context` for timeout/deadline and variadic `runtime.RequestOption` helpers such as `runtime.WithHeader(...)`.

HTTP transports merge default headers from config first, then per-call headers, then protocol-required headers such as `Content-Type` when encoding JSON, form, multipart, or binary bodies. Per-call timeout overrides transport config timeout and then falls back to the native client default. STREAM and CHANNEL lifecycle timeout stays separate and is controlled by context cancellation, close APIs, WebSocket/SSE runtime behavior, or application policy.

### Production Boundaries And Narrow Entrypoints

Default HTTP/Wails adapters are protocol bridges and development validation entrypoints, not complete production runtimes. They provide safety defaults, typed errors, request options, raw responses, and SSE/WebSocket/Wails bridge keyframes, but auth, rate limits, cookies, TLS/proxy policy, retry, connection orchestration, file permissions, audit logging, and complex backpressure should live in the host application through middleware/plugins/filters, native clients, custom transports, service implementations, or app shells.

Production projects should prefer narrow imports: a concrete route client, a concrete HTTP/Wails factory, or a concrete server group router instead of a root barrel or aggregate facade. Aggregate entrypoints are useful for examples, discovery, and quick starts; narrow entrypoints improve tree-shaking, dependency audit scope, and the minimum exposed surface. `include` / `exclude` is the stable cross-target generation-time trim boundary; unused imports, dead-code elimination, and Swift narrow products are language toolchain optimizations and are not a cross-language struct-level dead-strip contract.

Server adapters now use finite resource defaults that the host can explicitly relax: Go `httptransport.ServerConfig` defaults request bodies to `16 MiB`, multipart memory to `8 MiB`, single files to `32 MiB`, decompressed binary bodies to `16 MiB`, WebSocket origin checks on, and compression off; Java Spring `GenSpringServerConfig` defaults SSE timeout to `30s`, WebSocket allowed origins to an empty list, inbound queue capacity to `256`, multipart single files to `32 MiB`, and decompressed binary bodies to `16 MiB`; Kotlin `ApiServerConfig` defaults multipart files to `32 MiB`, binary bodies and decompressed binary bodies to `16 MiB`, and WebSocket messages to `1 MiB`; Python `ApiServerConfig` defaults bodies and decompressed binary bodies to `16 MiB`, multipart file/part to `32 MiB`, SSE queue capacity to `256`, and WebSocket messages to `1 MiB`.

Multipart file part runtime types prefer streams or file descriptors. Bytes helpers are still available for small files and tests, but large file paths should use Java `InputStream`/`Path`, Kotlin `fromPath`, Flutter `fromStream`, Python path-like/file-like inputs, or the host framework's spool/temp-file policy instead of relying on `readAllBytes()` as a production default.

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

The Go generator emits:

- Route interfaces and default `impl.go`.
- Request / response / context structures.
- Provider runtime and response envelope codecs.
- Transport-neutral Go core.
- Optional HTTP/Gin adapter with multipart binding, binary schema request decoding, binary schema response encoding, and raw bytes/file/stream response writers.

Source files overwritten by generators must be named `gen_*` / `Gen*`, or live under `_gen_*`, and keep a `Code generated ... DO NOT EDIT` header; manifests whose contents are determined by target/module lists, such as Swift `Package.swift`, may be managed as generated manifests. `impl_*` and non-`gen_` / non-`Gen` files are user-owned extension points, created only when missing, preserved during regeneration, and written without a generated header. Flutter uses Dart-style `gen_*.dart`; Swift uses `Gen*.swift`; Kotlin generator-owned files are named `Gen*.kt` while public declarations keep Kotlin-style names; Java generator-owned files and public types use `Gen*`.

`go-server` owns only the Go server core. `out_dir` is the generated package root; projects that want `views` in import paths should include `views` in `out_dir`. HTTP / Wails output is attached explicitly by `http-transport` / `wails-transport` targets through `server = "go.server"`. The HTTP entrypoint is generated under `<out_dir>/transports/http/<go-root-segment>`, for example `transports/http/api.NewBlueprint(engine)`.

Go route core is generated under `<out_dir>/routes/<go-root-segment>/**`, provider runtime under `<out_dir>/providers`, transport adapters under `<out_dir>/transports/**`, and typed error runtime under `<out_dir>/runtime/errors/**`. Go-safe segments replace non-`[0-9A-Za-z_]` characters with `_`, trim leading/trailing `_`, prefix digit-leading names with `p_`, and suffix Go keywords with `_pkg`; URLs, route paths, and selection/filter semantics stay unchanged, so Go directories do not guarantee one directory per URL slash segment. If you want the import path to include `/views`, set `out_dir = ".../views"` explicitly.

`providers` is a global transport-neutral runtime under the generated package root and is not split per blueprint root. TypeScript's per-root `runtime` mainly isolates model and client names; it is not the same responsibility as Go provider hooks.

When a provider implementation must vary by root, route, or transport, do not parse the request path. The generator writes `RouteInfo` into every route executor and exposes it through `Context.Route` and `ProviderSpec.Route`. HTTP-only route metadata is grouped under `RouteInfo.HTTP`, including the binary request `Content-Encoding` whitelist, the `HTTP_RAW_RESPONSE()` manual response flag, and the file response default download name:

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

The HTTP server adapter emits `transports/http/gen_config.go` with `httptransport.DefaultServerConfig()`, `httptransport.SetServerConfig(config)`, and `httptransport.ActiveServerConfig()`. Request body, multipart, decompressed binary, and WebSocket origin/compression defaults are intentionally tightened; applications can call `SetServerConfig` at startup to relax limits, configure `WebSocketOriginPatterns`, or register extra binary request `Content-Encoding` decoders through `BinaryContentDecoders`.

For new routes that return bounded typed binary packets, bytes, files, or byte streams, prefer `RSP_BINARY_SCHEMA(...)`, `RSP_BYTES(...)`, `RSP_FILE(...)`, or `RSP_BYTE_STREAM(...)` so the success response enters ContractGraph and can be recognized by client generators. `HTTP_RAW_RESPONSE()` remains a legacy HTTP adapter escape hatch, but it is not a cross-language contract and does not generate a typed raw-response client surface.

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

TypeScript, Flutter, Swift, Python, Kotlin, and Java use language-native lightweight helpers instead of copying the Go visitor shape. TypeScript emits `XxxMessageVariants.variant(data)`, `dispatchXxxMessage(message, handlers)`, and typed unknown-message dispatch errors. Flutter emits Dart 3 `sealed class XxxMessage`, final variant classes, `XxxMessageVariants.variant(data)`, and `dispatchXxxMessage(...)`. Swift emits associated-value enums, variant constructors, and custom `Codable` codecs. Python emits dataclass `XxxMessage`, `XxxMessageVariants`, `XxxMessageHandlers`, `dispatch_xxx_message(...)`, and `XxxMessageDispatchError` in route `gen_types.py` for both client and server output. Kotlin emits `@Serializable data class XxxMessage(type, data)`, `object XxxMessageVariants`, `XxxMessageHandlers<R>`, `dispatchXxxMessage(...)`, and `XxxMessageDispatchException`; the runtime exposes `ApiJson` for generated encode/decode. Java emits nested `record XxxMessage(String type, JsonNode data)`, variants, handlers, dispatch, and dispatch exception helpers inside the route `Gen<Group>Types.java`, with `GenApiJson.MAPPER` as the shared Jackson holder. These helpers support constructing `CHANNEL` client messages and dispatching server pushes, but they still do not implement the host application's connection session engine.

Go server also creates three user-owned scaffold files the first time it sees a `CHANNEL` with a named client message: `<leaf>_session.go`, `<leaf>_processor.go`, and `<leaf>_error.go`. These files do not carry a `Code generated` marker, and later generations create them only when missing instead of overwriting user edits. The default shell gives humans and AI agents stable places for the route handler, `Recv` loop, `VisitXxxMessage(...)`, `OnXxx` processor methods, and message error policy; it is still an editable starting point, not a generator-owned session engine, and it does not bind the route to appkit, a hub, middleware, or a close policy.

Non-scaffold generated connection handlers still default to `not implemented`, so example business logic is not written into every user project. The repository example keeps the `STREAM` usage in the user-owned `examples/golang/server/views/routes/api/demo/impl.go`, showing `Open()`, message constructors, context-aware `Send(...)`, and typed `Close(...)`; the `CHANNEL` example lives in `assistant_session_session.go`, `assistant_session_processor.go`, and `assistant_session_error.go`, where `OnXxx` methods use the scaffold scope's `Context`, route `CTX_*`, and channel.

### Typed Errors

ContractGraph collects `Blueprint(errors=...)` and route `.ERR(...)` declarations into language-agnostic typed errors. Manifest `2.0` keeps a global `errors` definition table and writes compact route-local refs (`id/group/key/code/message/toast`) into `routes[].errors`, so generated clients and `api-gen inspect errors --route ...` can show the error surface from the route being called. `id` is the public protocol error identity; `code` is only a business code and may be reused across groups or routes. `ResponseEnvelope` decides the wire shape: the default `CodeMessageDataEnvelope` uses `{ code, message, data, error? }`, strict `{ code, message, data }` output can opt into `LegacyCodeMessageDataEnvelope`, and `{ ok, data/error }` is available only when selecting `OkDataErrorEnvelope`.

Generated runtime APIs use user-facing, language-native names such as `ApiError`, `ApiErrors`, `ApiErrorsByID`, `lookupApiError`, and `isApiError`; Java generator-owned error types follow the ownership rule and use `GenApiError`, `GenApiErrors`, `GenApiErrorPayload`, and related `Gen*` names. Catalog dictionaries are internal indexes rather than the primary surface. Default Go, TypeScript, Flutter, Swift, Python, Kotlin, and Java client transports unwrap by the route envelope spec, resolve the payload by `id`, then by `(route_id, code)`, then by global code fallback, and throw or return a typed error; Java returns `GenApiError`. Go server grouped errors under packages such as `runtime/errors/common_err` return typed `ApiError` values; `WithToast(...)` returns an immutable override copy for request-language, tenant, or rollout-specific dynamic `toast.text`. Business i18n resolves the current language by toast key, and client helpers resolve display text in the order `toast.text`, external i18n, `toast.default`, then `message`. HTTP status remains transport state and is not derived from business error codes.

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

`gen_*.go` files are generator-owned and overwritten; `client.go` façades are user-owned and preserved. The recommended entrypoint is `apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})`, then route calls such as `api.Demo.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "token"}, runtime.WithHeader("X-Trace-Id", traceID))`. Route/runtime clients depend only on the transport abstraction, while `base_url` / `base_url_expr` are written only to the HTTP transport config. The default HTTP adapter implements RPC query/json/urlencoded/multipart/binary_schema requests and uses `runtime.MultipartFile` for multipart file parts; `Reader` inputs are sent as streaming multipart bodies, while `Bytes` is for small files and tests. It decodes binary schema success responses into typed packets, returns `runtime.RawResponse` for bytes/file raw responses, and returns true streaming `runtime.StreamResponse` values for byte streams, which callers must close. Request deadlines and cancellation use `context.Context`; per-call request options carry headers and future request-level flags. STREAM and CHANNEL methods are generated, but the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.

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

The HTTP transport supports JSON, urlencoded, multipart, and binary_schema requests. Route RPC methods accept `ApiRequestOptions` as the second argument, so a call can pass headers, `timeoutMs`, and native `RequestInit` without changing the route contract. Multipart DTO file fields use `ApiFilePart = File | Blob | { blob: Blob; filename?: string; contentType?: string }`. Binary schema success responses request HTTP bytes and decode them through the route-local packet codec. Raw bytes/file responses return `ApiRawResponse<Blob>` or `ApiRawResponse<ArrayBuffer>` with `body`, `headers`, `status`, `contentType`, `contentDisposition`, and `filename` parsed from the actual `Content-Disposition` response header. The client does not synthesize a filename from an `RSP_FILE(default_filename=...)` contract default. Byte stream routes use `responseType: "stream"`, with the concrete readable stream type depending on the runtime Fetch API.

`STREAM` / `CHANNEL` generate `ApiStreamBridge<Recv, Close>` and `ApiChannelBridge<Recv, Send, Close>`. Single-message directions use the model type directly; multi-message directions generate discriminated union types such as `{ type: "progress"; data: TaskProgress }`. The HTTP transport stream bridge uses SSE, the channel bridge uses WebSocket with an internal envelope to distinguish normal messages from close lifecycle payloads, and the Wails transport uses generated runtime events without exposing event names to business clients.

Markdown Binary Schema helpers are route-local `gen_binary.ts` implementation files and are re-exported through `types.ts`. Route clients import packet helpers from the route types surface.

## Flutter Client

```sh
api-gen generate -c api-blueprint.toml --target flutter.client
```

The Flutter client target emits a pure Dart package that Flutter Android/iOS apps can depend on directly. The generated package does not generate Flutter UI, app lifecycle, state management, auth, retry, cache, or a session engine.

A typical output layout is:

- `lib/<package>.dart`
- `lib/gen_<package>.dart`
- `lib/<root>.dart`
- `lib/gen_<root>.dart`
- `lib/src/<root>/<root>.dart`
- `lib/src/<root>/gen_<root>.dart`
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

`gen_*.dart` files are overwritten by the generator. Public entries, `api_client.dart`, `api_json_codecs.dart`, `http_api_client.dart`, route façades, type façades, and `binary.dart` are created only when missing, written without a generated header, and then owned by the user. The `ApiJsonCodec<T>` registry in `api_json_codecs.dart` lets projects plug in `build_runner` or handwritten codecs; without an override, generated manual `fromJson` / `toJson` code is used.

Runtime entrypoints include the aggregate `ApiClient` façade, route clients such as `DemoApi`, DTO `fromJson` / `toJson`, `ApiError`, `lookupApiError`, `ApiTransport`, `ApiRequestOptions`, `ApiStreamBridge`, `ApiChannelBridge`, and binary `Uint8List` codecs. The default HTTP transport uses `package:http` for RPC query/json/urlencoded/multipart/binary_schema requests, applies per-call `ApiRequestOptions.headers` and `ApiRequestOptions.timeout`, decodes binary_schema success responses into typed packets, returns `ApiRawResponse<Uint8List>` for bytes/file raw responses, returns true streaming `ApiStreamResponse.body: Stream<List<int>>` for byte streams, uses SSE for STREAM bridges, and uses `web_socket_channel` for CHANNEL bridges. Raw response filenames are parsed only from the actual `Content-Disposition` header. `base_url` / `base_url_expr` are written to HTTP config, not route/runtime clients.

Markdown Binary Schema helpers live in route-local `gen_binary.dart`; the shared binary reader/writer runtime lives in `runtime/binary/gen_binary_runtime.dart`. Dart public fields use lowerCamelCase while diagnostics keep the schema's original field names.

## Swift Client

```sh
api-gen generate -c api-blueprint.toml --target swift.client
```

The Swift client target emits an iOS Swift Package Manager SDK. The output is a protocol DTO/client and transport keyframe layer; it does not generate UI, app lifecycle, auth, signing, 401 handling, environment selection, retry, cache, token storage, a session owner, or singleton app state.

A typical config is:

```toml
[[swift.client]]
id = "swift.client"
out_dir = "swift"
package = "ApiBlueprintExampleClient"
module = "ABClient"
base_url = "http://localhost:2333"
runtime_profile = "modern"
```

A typical output layout is:

- `Package.swift`
- `Sources/<module>/<module>.swift`
- `Sources/<module>/Gen<module>.swift`
- `Sources/<module>/Transports/HTTP/HTTPAPIClient.swift`
- `Sources/<module>Runtime/GenAPITransport.swift`
- `Sources/<module>Runtime/GenAPIClient.swift`
- `Sources/<module>Runtime/GenAPITypes.swift`
- `Sources/<module>Runtime/GenAPIErrors.swift`
- `Sources/<module>Runtime/GenAPIErrorLookup.swift`
- `Sources/<module>Runtime/APICoding.swift`
- `Sources/<module>Runtime/Binary/GenBinaryRuntime.swift`
- `Sources/<module>Runtime/Transports/HTTP/GenHTTPAPIConfig.swift`
- `Sources/<module>Runtime/Transports/HTTP/GenURLSessionAPITransport.swift`
- `Sources/<module>Runtime/Transports/HTTP/GenHTTPConnection.swift`
- `Sources/<module><Root>Routes/<root>/<root>RootClient.swift`
- `Sources/<module><Root>Routes/<root>/Gen<root>RootClient.swift`
- `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/Gen<Group>API.swift`
- `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/Gen<Group>Types.swift`
- `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/GenBinary.swift`
- `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/<Group>API.swift`
- `Sources/<module><Root>Routes/<root>/Routes/<root>/<group...>/<Group>Types.swift`

`Package.swift` and `Gen*.swift` files are overwritten by the generator and carry the `// Code generated by api-blueprint (Swift client); DO NOT EDIT.` header (`Package.swift` still keeps the SwiftPM tools-version line first). Package/root façades, route façades, type façades, `APICoding.swift`, and `HTTPAPIClient.swift` are preserved user files: they are created only when missing, later generations do not overwrite user edits, and they do not carry the generated header. `package` is the SwiftPM package identity; `module` is the Swift module stem and defaults to `package` when omitted. The Swift package uses one `<module>` aggregate module, one shared `<module>Runtime` runtime module, and one independent `<module><Root>Routes` module per blueprint root; for example, a `/runtime` root emits `<module>RuntimeRoutes` and does not occupy the shared runtime module.

Apps can import the aggregate module for the quick-start client entrypoint; production code that wants the smallest dependency surface should link only `<module>Runtime` plus the specific `<module><Root>Routes` products it uses and construct the root client directly. When code references DTOs or route clients from a specific root directly, import the matching `<module><Root>Routes` module explicitly. The generator does not use `@_exported import`.

`module` only affects SwiftPM target/product/module/file/type stems; it does not affect the wire protocol, DTO shape, route id, route path, typed errors, or `runtime_profile`. `base_url` / `base_url_expr` are written only to `HTTPAPIConfig`, not to transport-neutral route/runtime clients. `runtime_profile` is a runtime code generation compatibility setting, not a protocol compatibility switch: the default `modern` profile emits `.iOS(.v15)` and uses modern `URLSession` async APIs; explicit `ios14-compat` emits `.iOS(.v14)` and uses continuation/delegate-compatible HTTP transport code for data tasks, byte streams, SSE, and WebSocket bridges. Both profiles keep the same DTOs, route names, wire shape, typed errors, binary schema surface, and public async API. `examples/swift` commits only the modern snapshot; compat validation generates a temporary package so the repository does not carry duplicate Swift snapshots.

Runtime entrypoints include the package aggregate façade, root client such as `client.api`, route clients such as `HelloAPI`, DTOs, `APITransport`, `APIRequestOptions`, `APIRequest<Response>`, `APITransportError`, `APIError`, `lookupAPIError`, `APIRawResponse`, `APIStreamResponse`, `APIFilePart`, `APIBinaryPayload`, `APIJSONValue`, `APICodingConfig`, `HTTPAPIConfig`, `APIStreamBridge`, `APIChannelBridge`, `APIBinaryReader`, and `APIBinaryWriter`. DTOs are `public struct ...: Codable, Sendable`; required fields are non-optional, optional / omitempty fields are optional, and `CodingKeys` preserve wire field names. String and integer enums use raw-value `Codable`, and multi-variant STREAM/CHANNEL messages use associated-value enums with custom codecs. Markdown Binary Schema helpers are route-local `GenBinary.swift` files that generate field-level packet structs, value constants, and encode/decode codecs. The codec preserves the Markdown schema's byte layout and validates const, range, sizeof, assert, reserved bytes, and reserved bit rules before packets cross the transport boundary.

The default URLSession transport implements RPC query/json/urlencoded/multipart/binary_schema requests, binary_schema/bytes/file/byte_stream success responses, response envelope unwrapping, typed error restoration, SSE-backed STREAM bridges, and WebSocket-backed CHANNEL bridges. RPC route methods accept `APIRequestOptions(headers:timeout:)` for per-call customization; STREAM / CHANNEL route methods are `throws` so URL construction, header, payload limit, and configuration failures surface as errors instead of crashes. `HTTPAPIConfig` is immutable runtime configuration for base URL, default headers, timeout, `URLSession`, `APICodingConfig`, byte stream chunk size, error body/SSE/WebSocket payload limits, stream buffer limit, and multipart memory threshold. JSON bodies and JSON responses use typed encoder/decoder closures instead of converting successful responses through `Any`; byte streams are chunked and `APIStreamResponse.cancel()` closes an early-stopped response stream; SSE/WebSocket bridges use finite buffers and per-message size limits; multipart validates CR/LF, escapes quoted headers, and uses a temporary request-body stream when fileURL parts or threshold-sized bodies are present. Raw response filenames are parsed only from the actual `Content-Disposition` header. The built-in connection bridge handles protocol message/close payloads; reconnect, auth refresh, complex backpressure, and session policy remain host-application responsibilities through a custom `APITransport` or wrapper.

Typical usage looks like this:

```swift
import ABClient
import ABClientRuntime
import ABClientAPIRoutes
import ABClientRuntimeRoutes
import Foundation

let client = HTTPAPIClient.create(
    baseURL: URL(string: "http://localhost:2333")!
)

let response = try await client.api.hello.abc(
    query: HelloAbcQuery(arg1: true, type_: .ping),
    options: APIRequestOptions(headers: ["X-Trace-Id": traceID])
)
```

For iOS app architectures, put the generated SDK under Core Networking as the protocol DTO/client layer. The app-owned `APIClient` should wrap or inject the generated `APITransport` and own auth/signing, 401 handling, environment switching, retry, cache, session ownership, token storage, logging, and monitoring. Multi-root projects are isolated as multiple root modules in the same Swift package by default; host applications explicitly import the root modules they depend on.

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

Kotlin generator-owned files are named `Gen*.kt`, for example `routes/api/demo/GenDemoApi.kt`, `routes/api/demo/GenDemoTypes.kt`, and `runtime/GenApiClient.kt`, and include a generated header. Non-`Gen*` façade files such as `DemoApi.kt`, `runtime/ApiClient.kt`, and `transports/http/HttpApiClient.kt` are preserved user extension points.

Route DTOs are written to `Gen<Group>Types.kt`, while public DTO / helper declaration names remain unchanged. Markdown Binary Schema helpers are route-local packet / wire helper types in `GenBinaryTypes.kt` in the same package as the route API.

Through the transport abstraction, Kotlin generates `rpc`, `stream`, and `channel` route surfaces, and supports query/json/urlencoded/multipart/binary_schema/open request kinds plus `none` / `code_message_data` / `ok_data_error` response envelopes. RPC route methods accept `ApiRequestOptions(headers, timeout)` for per-call request customization. The built-in OkHttp adapter covers RPC query/json/urlencoded/multipart/binary_schema requests, applies per-call headers and call timeout, decodes binary_schema success responses into typed packets, returns `ApiRawResponse` for bytes/file raw responses, returns true streaming closeable `ApiStreamResponse` / `InputStream` values for byte streams, and provides `readChunk()` / `readAllBytes()` convenience methods; raw response filenames come only from the actual `Content-Disposition` header. It uses SSE for `STREAM` bridges and OkHttp WebSocket for `CHANNEL` bridges, and implements protocol transport only, not the host application's session engine, retry, cache, or connection orchestration.

`base_url` / `base_url_expr` are written into the generated `transports/http/HttpApiConfig.kt` default, not into the transport-neutral runtime client.

### Kotlin Server

```sh
api-gen generate -c api-blueprint.toml --target kotlin.server
```

The Kotlin server target emits a Ktor-oriented scaffold:

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Types.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Service.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>ServiceStub.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>Service.kt`
- `<package>/<root>/transports/ktor/<root>/<group...>/Gen<Group>KtorRoutes.kt`

`Gen<Group>Service.kt`, `Gen<Group>ServiceStub.kt`, `Gen<Group>Types.kt`, runtime `Gen*.kt` files, and `Gen<Group>KtorRoutes.kt` are generator-owned. `<Group>Service.kt` is a preserved user file and defaults to extending the generated stub.

RPC Ktor routes decode query/json/urlencoded/multipart/binary_schema inputs, call the generated service interface, and wrap JSON success values or generated `ApiError` values through the route response envelope. Each generated Ktor route owns a small route-local HTTP metadata value, so binary `Content-Encoding` whitelists, raw response kind/media type, and file default download names are read by helper functions instead of being threaded through growing helper parameter lists. binary_schema requests validate the route schema `Content-Encoding` whitelist, decode built-in `identity` / `gzip`, and can use `ApiServerConfig.binaryContentDecoders` for extensions such as `br`. binary_schema, bytes, file, and byte_stream success responses bypass the JSON envelope; the adapter writes raw bytes, `Content-Type`, and download headers, and byte_stream is written in chunks through Ktor's streaming writer. `STREAM` routes generate an SSE bridge, and `CHANNEL` routes generate a Ktor WebSocket bridge; open payloads are decoded from query parameters, and message/close/client message payloads use the generated serializers. `register*Routes` accepts `ApiServerConfig`, which limits multipart files, binary bodies, decompressed binary bodies, and WebSocket message sizes by default. This is only protocol bridging and keyframes; it does not generate the host application's session engine, auth, retry, cache, room management, or connection orchestration.

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

Route DTOs are emitted as `Gen<Group>Types.java`. Markdown Binary Schema typed packets and wire helpers are also folded into that route types container, for example `GenBinaryTypes.DemoPacket` / `GenBinaryTypes.DemoPacketWire`.

The Java client emits transport-neutral route surfaces, `GenApiTransport`, the default JDK HTTP adapter, and `GenApiClient`. Preserved user files are `runtime/ApiClient.java`, `routes/<root>/<group...>/<Group>Api.java`, and `transports/http/HttpApiClient.java`; other `Gen*.java` files are overwritten. The recommended entrypoint is `HttpApiClient.create(baseUrl)`, with public DTOs such as `GenDemoTypes.ErrorDemoQuery` / `GenDemoTypes.ErrorDemoResponse`. RPC route methods provide `GenApiRequestOptions` overloads for per-call headers and timeout. Generated route clients build `GenApiRequest` with nested body/response specs, so custom transports read request kind, response kind, media type, binary decoder, and envelope behavior from the request object instead of a widening transport method signature. The default HTTP adapter implements RPC query/json/urlencoded/multipart/binary_schema requests, decodes binary_schema success responses into typed packets, returns `GenApiRawResponse` for bytes/file raw responses, returns true streaming `GenApiStreamResponse` / `InputStream` / `AutoCloseable` values for byte streams, and keeps `readAllBytes()` as a convenience method; raw response filenames come only from the actual `Content-Disposition` header. STREAM and CHANNEL default to explicit unsupported errors.

The Java server emits route service interfaces, public stubs, runtime, route types, `GenSpringServerConfig`, and Spring controllers. Each generated controller carries route-local `HttpRouteInfo` metadata for binary request encodings, raw/manual response behavior, response media type, and file default download name. For `.REQ_BINARY_SCHEMA(...)`, the generated Spring controller validates the route schema `Content-Encoding` whitelist, decodes built-in `identity` / `gzip` or registered `binaryContentDecoders`, then parses request bytes into the generated typed packet before calling the service; multipart routes decode file parts into `GenApiFilePart`; binary_schema, bytes, file, and byte_stream success responses bypass the JSON envelope and the controller writes raw bytes, `Content-Type`, and download headers; byte_stream is written through a Spring streaming response instead of being forced into a byte array. `STREAM` routes use a Spring `SseEmitter` bridge, and `CHANNEL` routes generate a WebSocket handler/config compatible with the `{type:"message",data}` / `{type:"close",data}` wire shape. `GenSpringServerConfig` defaults to a bounded WebSocket inbound queue, empty allowed origins, replaceable executor, multipart file limit, decompressed binary limit, and an empty binary decoder registry; projects can provide a custom bean/constructor argument to override it. The preserved user file is `routes/<root>/<group...>/<Group>Service.java`; `Gen<Group>Types.java`, `Gen<Group>ServiceStub.java`, `Gen<Group>Service.java`, and `transports/http/<root>/<group...>/Gen<Group>Controller.java` are generator-owned. Connection output provides only protocol bridging; it does not generate a host session engine, auth, retry, cache, or room management.

DTOs use Java 17 `record`; fields use Jackson `@JsonProperty`; enums use `@JsonCreator` / `@JsonValue` to preserve wire values. `module` is only a shortcut-table alias normalized to `package`; no JPMS `module-info.java` is generated.

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client uses `python_package_root` as its package root and emits an async-first HTTP client:

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`gen_client.py` / `client.py` at the root provide the aggregate facade, and the recommended entrypoint is `async with create_client(base_url) as api`. Route method public facades use typed dataclass DTOs and keyword-only `headers` / `timeout` request options, and no longer expose `Mapping[str, Any]` as the normal request entrypoint; use the transport directly when a raw dict/body escape hatch is needed. `routes/<root>/<group...>/gen_client.py` is the generated route client, `routes/<root>/<group...>/gen_types.py` is the route DTO and binary public export surface, `routes/<root>/<group...>/client.py` is the preserved passthrough entrypoint, `runtime/gen_codecs.py` contains shared decode/encode helpers, and `transports/http/gen_client.py` provides the default httpx adapter. Root-level routes are emitted directly under `routes/<root>`, not `routes/root`. Generated route clients build an `ApiRequest` dataclass with method/path, body variant, response metadata, headers, and timeout; custom transports implement `request(ApiRequest)` instead of a widening positional signature. The default httpx adapter implements JSON, urlencoded, multipart, and binary_schema RPC requests; multipart files may be bytes, path-like values, file-like values, or tuples/dicts carrying filename/content_type, binary_schema success responses decode to typed packets, bytes/file raw responses return `ApiRawResponse[bytes]`, and byte stream responses return an async context manager. Raw response filenames are parsed only from the actual `Content-Disposition` header. STREAM/CHANNEL bridge interfaces are generated, but connection transports need project-specific customization or later extension. `base_url` / `base_url_expr` are used by the HTTP transport adapter.

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

`routes/<root>/<group...>/gen_service.py` is the generated typed service contract, `routes/<root>/<group...>/service.py` is the user-maintained stub entrypoint, and `transports/http/gen_server.py` plus `server.py` provide the FastAPI HTTP adapter scaffold. Root-level routes are emitted directly under `routes/<root>`. The FastAPI adapter decodes query/json/urlencoded/multipart/open dicts recursively into route DTOs before calling the service, uses `UploadFile = File(...)` and ordinary `Form(...)` fields to assemble multipart DTOs, and recursively encodes returned DTO/scalar/list/map values back to JSON; response envelopes and typed error wrapping are still handled by the adapter. Generated handlers reference route-local `HttpRouteInfo` values so binary request encodings and raw response kind/media/default filename metadata stay grouped with the route instead of being passed as loose helper arguments. Binary schema requests validate the route schema `Content-Encoding` whitelist, decode built-in `identity` / `gzip` or registered `binary_content_decoders`, parse the decoded body into the generated typed packet, and then call the service. Binary schema success responses encode typed packet return values into HTTP bytes. Raw bytes/file/byte_stream success responses use `Response`, `FileResponse`, or `StreamingResponse` respectively and are not wrapped in a JSON envelope; typed errors still use the JSON envelope. `STREAM` routes get `StreamingResponse` SSE bridges, and `CHANNEL` routes get WebSocket bridges with generated DTO codecs for message and close payloads. `ApiServerConfig` limits request bodies, decompressed binary bodies, multipart file/part sizes, SSE queues, and WebSocket message sizes; `create_<group>_router(..., config=...)` is the narrow router entrypoint while `create_router(..., config=...)` remains the aggregate entrypoint. Malformed JSON or binary input is treated as a transport input error and returns HTTP 400 rather than a business envelope. The Python server WebSocket runtime needs `websockets` or an equivalent uvicorn WebSocket backend. As a preview target, Python server output should be included in the consuming project's type checks, lint, and install smoke tests.

## Example Snapshots

`examples/golang/server/`, `examples/golang/client/`, `examples/typescript/`, `examples/flutter/`, `examples/swift/`, `examples/kotlin/client`, `examples/kotlin/server`, `examples/java/client` / `examples/java/server`, and `examples/python/` are generated snapshots, not business sources; `examples/java/suite` is a handwritten runtime validation project. `examples/golang/conformance/`, `examples/typescript/conformance.ts`, `examples/kotlin/conformance/`, `examples/java/conformance/`, `examples/python/conformance/`, `examples/flutter/test/conformance_test.dart`, and `examples/swift/Conformance/` are preserved conformance files whose job is to call each language's generated artifacts against real Go / Java / Kotlin / Python servers, covering RPC, urlencoded, multipart media, binary_schema, request options headers/timeouts, typed errors, naming conflicts, bytes/file/byte_stream raw responses, media filename edge cases, raw media typed errors, XML/static/header/scalar/enum/map/deprecated/audit-binary routes, single-model channels, and supported SSE/WebSocket interoperability. `examples/swift/Narrow/` is a preserved SwiftPM smoke package that depends only on `ABClientRuntime` and one root routes product, proving the intended narrow-entrypoint shape without importing the aggregate module. Regeneration must not overwrite these files. Go server / Go client / Wails Go contract / agent artifact indexes use Go-safe route package segments, while Flutter / Swift / Kotlin / Java / Python artifact indexes keep their language-specific route output paths. To accept intentional generation changes, use:

```sh
make example-refresh
```
