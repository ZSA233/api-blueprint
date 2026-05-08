# Generators

This page covers the main non-Wails, non-gRPC generators. See [Wails](wails.md) for Wails and [gRPC](grpc.md) for gRPC.

## Shared Planning And Capabilities

`api-gen check`, contract / agent artifact projection, and language writers use the same planner / capability metadata. Before generation, target dependencies, route kinds, request kinds, and response wrappers are validated consistently, avoiding cases where check passes and a writer later discovers unsupported input.

Go client, Kotlin, and Python are newly implemented generator surfaces and should currently be treated as preview. Their contract / agent artifact paths point to outputs that mirror the full route path, for example `routes/api/demo`; Python no longer uses a `routes/root` sentinel.

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

The Go generator emits:

- Route interfaces and default `impl.go`.
- Request / response / context structures.
- Provider runtime and wrappers.
- Transport-neutral Go core.
- Optional HTTP/Gin adapter.

`gen_*` files are generator-owned and overwritten during regeneration. `impl_*` and non-`gen_*` files are user-owned extension points and are preserved. Kotlin follows the same ownership model with `Gen*.kt` as generator-owned files and non-`Gen*` façade / extension files as user-owned files.

`go-server` owns only the Go server core. Its `out_dir` is the generated package root and no longer appends `views` implicitly. HTTP / Wails output is attached explicitly by `http-transport` / `wails-transport` targets through `server = "go.server"`. The HTTP entrypoint is generated under `<out_dir>/transports/http/<root>`, for example `transports/http/api.NewBlueprint(engine)`.

Go route core is generated under `<out_dir>/routes/**`, provider runtime under `<out_dir>/providers`, transport adapters under `<out_dir>/transports/**`, and error catalog implementations under `<out_dir>/runtime/errors/**`. If you want the import path to include `/views`, set `out_dir = ".../views"` explicitly.

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

Register provider factories during application startup or package `init()`. The provider sequence is parsed only when the executor is created, and factories also run only at creation time. The high-concurrency request path only executes cached provider instances. If a project needs selection logic without the global registry, implement `SelectProvider(spec, handler)` in the user-owned `providers/impl_provider.go`; the old `Select(key, value, handler)` hook has been removed.

The HTTP adapter imports the blueprint root router only when the root has direct routes. If a handler has already written a Gin response, the adapter does not append an automatic response; otherwise routes without an `rsp` provider keep the existing behavior where the adapter writes the handler return value.

Use `HTTP_RAW_RESPONSE()` when the handler fully owns the successful HTTP response. This affects only the HTTP adapter: success does not write an automatic response, and errors return 500 only when the Gin writer has not written yet. It is not a shared provider and does not change Wails overlays.

### Long-Connection Contracts

Go core generates transport-neutral handler interfaces for `STREAM` / `CHANNEL`. Business code does not directly depend on SSE, WebSocket, or Wails event names:

```go
Events(
	ctx *CTX_Events,
	stream providers.Stream[OPEN_Events, TaskStreamMessage, CLOSE_Events],
) error
Chat(
	ctx *CTX_Chat,
	channel providers.Channel[OPEN_Chat, AssistantServerMessage, AssistantClientMessage, CLOSE_Chat],
) error
```

In the HTTP transport, `STREAM` generates an SSE adapter and `CHANNEL` generates a WebSocket adapter. In the Wails transport, both are backed by session-scoped runtime events by default. Multi-message variants generate one shared union schema with a `type` discriminator; do not split variants into multiple transport events. `.CLOSE(Model)` is part of the Go handler generic and the TypeScript `onClose` type; server business closures use `Close(&CLOSE_...{...})`, while exceptional or protocol failures use `Abort(code, reason)`.

The default HTTP/Wails runtimes fully implement only `ConnectionScope.SESSION`. `APP` / `TOPIC` remain in the route contract and can be implemented later through a custom connection hub / manager for broadcast or topic routing; the generator does not bake in business fan-out policy.

Generated connection handlers still default to `not implemented`, so example business logic is not written into every user project. The repository example hand-writes the minimal usage in the user-owned `examples/golang/server/views/routes/api/demo/impl.go`: `STREAM` shows `Open()`, server message construction, `Send()`, and typed `Close()`; `CHANNEL` also shows `Recv(ctx)` for client messages.

### Error Catalog

ContractGraph collects `Blueprint(errors=...)` and route `.ERR(...)` declarations into a language-agnostic error catalog. `message` is the protocol-level default description, while `toast.key/default/level` is the user-facing fallback surface; generators do not emit built-in locale tables or `locales/*.json`. Go client, TypeScript, Kotlin, and Python client/server split runtime error types/helpers from static catalog data into separate generated files such as `gen_error_catalog.*` or `GenApiErrorCatalog.kt`; Go server emits runtime types under `runtime/errors` and grouped error values under packages such as `runtime/errors/common_err`, avoiding a duplicate root catalog. Business i18n resolves the current language by toast key, and client helpers resolve display text in the order `toast.text`, external i18n, `toast.default`, then `message`. Generated group errors implement `CodeError`, and `WithToast(...)` returns an immutable override copy for request-language, tenant, or rollout-specific dynamic `toast.text`. The HTTP transport still represents transport failures separately, and business wrapper codes are not automatically converted into thrown exceptions.

## Go Client

```sh
api-gen generate -c api-blueprint.toml --target go.client
```

The Go client target emits a preview HTTP client:

- `runtime/gen_*.go`
- `routes/<root>/<group...>/gen_client.go`
- `routes/<root>/<group...>/gen_models.go`
- `routes/<root>/<group...>/client.go`
- `transports/http/gen_config.go`
- `transports/http/gen_transport.go`
- `transports/http/client.go`

`gen_*.go` files are generator-owned and overwritten; `client.go` façades are user-owned and preserved. Route/runtime clients depend only on the transport abstraction, while `base_url` / `base_url_expr` are written only to the HTTP transport config. The default HTTP adapter implements RPC query/json/form/binary requests. Legacy WS / STREAM / CHANNEL methods are generated, but the default HTTP adapter returns an explicit unsupported error so projects can swap in a custom transport.

## TypeScript

```sh
api-gen generate -c api-blueprint.toml --target typescript.client
```

The TypeScript client target emits:

- `models.ts` / `gen_models.ts`.
- Request client classes.
- Transport-neutral `ApiClientConfig`.
- `createClients(config)` facades injected by transport targets.
- User-owned passthrough files such as `client.ts`, `transport.ts`, and `factory.ts`.

`base_url` / `base_url_expr` are owned by generated HTTP transport facades, not route/runtime clients. `base_url_expr` is emitted verbatim into generated code, which fits runtime configuration in Vite, Next.js, and similar projects. It is mutually exclusive with `base_url`.

`STREAM` / `CHANNEL` generate `ApiStreamBridge<Recv, Close>` and `ApiChannelBridge<Recv, Send, Close>`. Single-message directions use the model type directly; multi-message directions generate discriminated union types such as `{ type: "progress"; data: TaskProgress }`. The HTTP transport stream bridge uses SSE, the channel bridge uses WebSocket with an internal envelope to distinguish normal messages from close lifecycle payloads, and the Wails transport uses generated runtime events without exposing event names to business clients.

## Kotlin Android

```sh
api-gen generate -c api-blueprint.toml --target kotlin.client
```

The Kotlin target emits an OkHttp + kotlinx.serialization Android client.

Kotlin emits a package-first layout whose route directory mirrors the full route path:

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

This is a breaking layout change from the old `<package>/ApiClient.kt`, `endpoints/`, `models/`, and `internal/` layout. Regeneration cleans up the old layout, so business code should import types from `<package>.<root>.runtime`, `<package>.<root>.routes...`, and `<package>.<root>.transports.http`.

Kotlin generator-owned files are named `Gen*.kt`, for example `routes/api/demo/GenDemoApi.kt` and `runtime/GenApiClient.kt`, and include a generated header. Non-`Gen*` façade files such as `DemoApi.kt`, `runtime/ApiClient.kt`, and `transports/http/HttpApiClient.kt` are preserved user extension points.

Through the transport abstraction, Kotlin generates `rpc`, `legacy_ws`, `stream`, and `channel` route surfaces, and supports query/json/form/binary/open request kinds plus none/general/custom response wrappers. The built-in OkHttp adapter is RPC-first; long-connection bridges are preview/custom transport surfaces, so validate with `api-gen check` and target-platform smoke tests before putting them on a production call path.

`base_url` / `base_url_expr` are written into the generated `transports/http/HttpApiConfig.kt` default, not into the transport-neutral runtime client.

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client uses `python_package_root` as its package root and emits an async-first HTTP client:

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_client.py` is the generated route client, `routes/<root>/<group...>/client.py` is the preserved passthrough entrypoint, and `transports/http/gen_client.py` provides the default httpx adapter. Root-level routes are emitted directly under `routes/<root>`, not `routes/root`. That adapter implements RPC requests; WS/STREAM/CHANNEL bridge interfaces are generated, but connection transports need project-specific customization or later extension. `base_url` / `base_url_expr` are used by the HTTP transport adapter.

## Python Server

```sh
api-gen generate -c api-blueprint.toml --target python.server
```

Python server also uses `python_package_root` as its package root and emits route service contracts/stubs plus a FastAPI HTTP adapter scaffold:

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_service.py` is the generated service contract, `routes/<root>/<group...>/service.py` is the user-maintained stub entrypoint, and `transports/http/gen_server.py` plus `server.py` provide the FastAPI HTTP adapter scaffold. Root-level routes are emitted directly under `routes/<root>`, not `routes/root`. This target is a newly implemented surface, so include generated output in the consuming project's type checks, lint, and install smoke tests.

## Example Snapshots

`examples/golang/server/`, `examples/golang/client/`, `examples/typescript/`, and `examples/kotlin/` are generated snapshots, not business sources. Go client and Kotlin/Python contract / agent artifact indexes use the new route output paths. To accept intentional generation changes, use:

```sh
make example-refresh
```
