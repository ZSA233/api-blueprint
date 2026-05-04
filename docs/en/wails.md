# Wails

`api-gen-wails` generates Wails API artifacts. It does not generate a full Wails scaffold and does not call the Wails CLI to generate JS bindings.

In this repository, the Wails CLI is used to build and package handwritten harnesses such as `examples/wails-harness/{v2,v3}`. It is not an input to `api-gen-wails`.

## Target Config

```toml
[[wails.targets]]
id = "wails.v3"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

- `id`: used by `--target`, `--list-targets`, and `--explain-target`.
- `version`: supports `v3` and `v2`.
- `overlay_name`: defaults to `wailsv3` / `wailsv2` and must be unique.
- `frontend_mode`: defaults to `external`; `none` skips the Wails TypeScript overlay.
- `include` / `exclude`: trim only the Wails overlay, not the shared Go / TypeScript contract layers.

## Go Output Layout

Wails Go overlays are generated next to the shared `[golang]` output tree:

```text
views/
  _wailsv3/runtime/gen_runtime.go
  api/
    _wailsv3/
      gen_overlay.go
      gen_service.go
      bindings/
        gen_service.go
        impl_service.go
    demo/
      _wailsv3/
        gen_overlay.go
        gen_service.go
        bindings/
          gen_service.go
          impl_service.go
```

Every Go `_...` directory is a generator-reserved namespace. `bindings/impl_service.go` is a user-owned bootstrap constructor entry and is preserved across regeneration.

## TypeScript Output Layout

Wails TypeScript overlays are generated inside the shared `[typescript]` output tree:

```text
api/
  (shared)/
    gen_client.ts
    gen_factory.ts
    (wailsv3)/gen_transport.ts
  demo/
    gen_client.ts
    (wailsv3)/gen_client.ts
  (wailsv3)/gen_factory.ts
```

Every TypeScript `(...)` directory is a generator-reserved namespace. Wails route overlays expose `createClient(config)` plus the narrow `type <Group>Client`, and the root overlay exposes `createClients(config)`.

## Provider Hooks

Go HTTP and Wails share the generated `RouteExecutor` provider pipeline. Wails services run `req/auth/handle/rsp` and WS preflight providers by default, so projects do not need a handwritten per-route adapter just to restore auth/provider behavior.

Long-term ownership boundary:

- `gen_*`: generator-owned and overwritten.
- `impl_auth.go`: user-owned, keeping `AuthContext` and `BuildAuthContext(ctx, req)`.
- `impl_*` helpers: user-owned, but should not retake the provider main flow.
- Wails runtime: generated-only, no `impl_runtime.go`.

`RouteExecutor` is a reusable route-level execution plan. Request-scoped state must live in `Context` or its metadata store, and custom providers should be stateless/reentrant. HTTP-only providers should explicitly import `views/_http` and use adapter helpers such as `httptransport.RequireGin(ctx)` to access Gin context.

HTTP behavior tests should generally live in an external test package, for example `package demo_test`, and import the route-adjacent `_http` adapter. Business handler unit tests can stay in the route package and call handlers directly with typed `ctx/req` values. Use `views/_http.RequireGin(ctx)` only when Gin APIs are actually required; doing so explicitly couples that code to the HTTP adapter.

## TypeScript Transport

The recommended mode is `frontend_mode = "external"`: an existing WebUI keeps the shared TypeScript API source of truth, while each Wails target only keeps an app shell, build config, and project-owned transport shim.

An external frontend must load the Wails runtime before mounting the app or creating clients. The generated Wails transport exports `ensureWailsRuntime()` as the minimal bootstrap helper:

```ts
import { ensureWailsRuntime } from "./api/(shared)/(wailsv3)/transport";
import { createClients } from "./api/(wailsv3)/factory";
import { WailsV3Transport } from "./api/(shared)/(wailsv3)/transport";

await ensureWailsRuntime();

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

The Wails v3 helper checks and loads `/wails/runtime.js` when needed. The Wails v2 helper checks and loads `/wails/ipc.js` plus `/wails/runtime.js` when needed. The transport also performs a lazy runtime check on first use, but explicit bootstrap is recommended so the UI framework does not mount before the runtime is ready.

The shared factory works for HTTP and Wails:

```ts
import { createClients } from "./api/(wailsv3)/factory";
import { WailsV3Transport } from "./api/(shared)/(wailsv3)/transport";

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

The Wails v3 transport uses the official runtime `Call.ByName(...)` contract and a generated binding manifest; projects do not need to hand-code Go binding package paths. The Wails v2 transport continues to use the official `window.go.<package>.<service>.<method>` runtime shape.

## Wails-only App

`api-blueprint` can be used in a Wails app that does not start an HTTP server. `api-gen-wails` still generates the shared Go / TypeScript contract layers; when `[golang].transport_adapters = ["wails"]`, it does not generate the Gin HTTP adapter. The Wails app shell only needs to register generated bindings. It does not need to import the `_http` adapter or start a Gin/HTTP listener.

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "golang"
module = "example.com/myapp/generated"
transport_adapters = ["wails"]

[typescript]
codegen_output = "typescript"

[[wails.targets]]
id = "desktop.v3"
version = "v3"
frontend_mode = "external"
```

```sh
mkdir -p golang typescript
uv run api-gen-wails -c api-blueprint.toml --target desktop.v3
cd app
wails3 doctor
wails3 build
```

`transport_adapters = ["wails"]` marks the Go core as consumed by Wails targets but skips the Gin HTTP adapter; when the Wails app imports only generated bindings, its build graph does not need Gin. If one project needs both HTTP and Wails, use `transport_adapters = ["http", "wails"]` and configure `[[wails.targets]]`. The `wails` marker does not replace Wails targets; if it is listed, at least one target must also be configured. See `examples/wails-hello` for the complete minimal example.

Shortcut for manually starting `examples/wails-hello`:

```sh
make wails-hello-dev
```

This regenerates the hello overlay first, then runs `wails3 task dev` under `examples/wails-hello/app`; that task uses `build/config.yml` to start the frontend dev server, build the Go binary, and run the Wails app. Shortcuts for automated validation:

```sh
make wails-hello-check
make wails-hello-compile-check
```

`wails-hello-check` is strict and checks snapshot drift; `wails-hello-compile-check` only validates regenerated TypeScript, Go, and Wails v3 build output, which is useful during development.

## Socket Bridge

Wails TypeScript does not expose raw WebSocket. It uses `ApiSocketBridge<ServerMessage, ClientMessage>` instead.

```ts
const bridge = demoClient.connectWs({ query, headers });
await bridge.ready;

const offMessage = bridge.onMessage((message) => {
    console.log(message);
});

await bridge.send(payload);
await bridge.close(1000, "done");
offMessage();
```

The HTTP shared client still keeps `connect<Route>Raw()` as the native WebSocket escape hatch.

## Harness Examples

`examples/wails-harness/v2` and `examples/wails-harness/v3` are repo-owned minimal runnable examples. Their app shells are handwritten, but they directly consume Go bind wrappers and TypeScript API artifacts from the shared trees.

`examples/wails-hello` is a standalone Wails v3 hello world example with its own Blueprint, generated snapshots, and handwritten app shell. It demonstrates the minimal `Go handler -> generated Wails binding -> generated TypeScript client -> GUI dialog` loop.
