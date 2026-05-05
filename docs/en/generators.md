# Generators

This page covers the main non-Wails, non-gRPC generators. See [Wails](wails.md) for Wails and [gRPC](grpc.md) for gRPC.

## Go

```sh
api-gen-golang -c api-blueprint.toml
```

The Go generator emits:

- Route interfaces and default `impl.go`.
- Request / response / context structures.
- Provider runtime and wrappers.
- Transport-neutral Go core.
- Optional HTTP/Gin adapter.

`gen_*` files are generator-owned and overwritten during regeneration. `impl_*` and non-`gen_*` files are user-owned extension points and are preserved.

`[[transport.targets]]` controls Go transport output; when no target is declared, a default HTTP target is generated. The HTTP entrypoint is generated under `views/transports/http/<root>`, for example `views/transports/http/api.NewBlueprint(engine)`. Wails-only projects declare only a `kind = "wails"` target, and HTTP + Wails projects declare both `kind = "http"` and `kind = "wails"`.

Go route core is fixed under `views/routes/**`, and the provider runtime is fixed under `views/providers`. These directory names are no longer configurable, so business roots can safely use paths such as `/providers` or `/transports`.

`views/providers` is a global transport-neutral runtime and is not split per blueprint root. TypeScript's per-root `runtime` mainly isolates model and client names; it is not the same responsibility as Go provider hooks.

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

Register provider factories during application startup or package `init()`. The provider sequence is parsed only when the executor is created, and factories also run only at creation time. The high-concurrency request path only executes cached provider instances. If a project needs selection logic without the global registry, implement `SelectProvider(spec, handler)` in the user-owned `views/providers/impl_provider.go`; the old `Select(key, value, handler)` hook has been removed.

The HTTP adapter imports the blueprint root router only when the root has direct routes. If a handler has already written a Gin response, the adapter does not append an automatic response; otherwise routes without an `rsp` provider keep the existing behavior where the adapter writes the handler return value.

Use `HTTP_RAW_RESPONSE()` when the handler fully owns the successful HTTP response. This affects only the HTTP adapter: success does not write an automatic response, and errors return 500 only when the Gin writer has not written yet. It is not a shared provider and does not change Wails overlays.

## TypeScript

```sh
api-gen-typescript -c api-blueprint.toml
```

The TypeScript generator emits:

- `models.ts` / `gen_models.ts`.
- Request client classes.
- Transport-neutral `ApiClientConfig`.
- Transport facade `createClients(config)` factories.
- User-owned passthrough files such as `client.ts`, `transport.ts`, and `factory.ts`.

`base_url_expr` is emitted verbatim into generated code, which fits runtime configuration in Vite, Next.js, and similar projects. It is mutually exclusive with `base_url`.

## Kotlin Android

```sh
api-gen-kotlin -c api-blueprint.toml
```

The Kotlin generator emits an OkHttp + kotlinx.serialization Android client.

The current version mainly covers JSON REST routes. `include` / `exclude` can trim the generated API surface.

## Java

Java is not exposed as a public CLI target yet. It remains an internal extension point only.

## Example Snapshots

`examples/golang/`, `examples/typescript/`, and `examples/kotlin/` are generated snapshots, not business sources. To accept intentional generation changes, use:

```sh
make example-refresh
```
