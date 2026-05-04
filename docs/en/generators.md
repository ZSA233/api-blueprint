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

`[golang].provider_package` controls the shared provider/runtime package name and defaults to `provider`.

`[golang].transport_adapters` controls Go transport adapters and defaults to `["http"]`. The HTTP entrypoint is generated under reserved `_http` directories, for example `views/api/_http.NewBlueprint(engine)`; Wails-only projects should use `["wails"]`, and HTTP + Wails projects should use `["http", "wails"]`. `[]` means core-only output for future adapters or advanced integrations.

The HTTP adapter imports the blueprint root router only when the root has direct routes. If a handler has already written a Gin response, the adapter does not append an automatic response; otherwise routes without an `rsp` provider keep the existing behavior where the adapter writes the handler return value.

## TypeScript

```sh
api-gen-typescript -c api-blueprint.toml
```

The TypeScript generator emits:

- `models.ts` / `gen_models.ts`.
- Request client classes.
- Transport-neutral `ApiClientConfig`.
- Shared `createClients(config)` factory.
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
