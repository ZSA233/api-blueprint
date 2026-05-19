# Wails

`api-gen generate --target <wails-target>` generates Wails API artifacts. It does not generate a full Wails scaffold and does not call the Wails CLI to generate JS bindings.

In this repository, the Wails CLI is used to build and package handwritten harnesses such as `examples/wails-harness/{v2,v3}`. It is not an input to the Wails target.

## Target Config

```toml
[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

- `id`: used by `api-gen generate --target`, `list-targets`, and `explain-target`.
- `kind`: Wails targets use `wails-transport`.
- `version`: supports `v3` and `v2`.
- `server`: references a `go-server` target.
- `clients`: references one or more client targets; the Wails TypeScript facade uses `typescript-client`.
- `overlay_name`: defaults to `wailsv3` / `wailsv2` and must be unique.
- `frontend_mode`: defaults to `external`; `none` skips the Wails TypeScript overlay.
- `include` / `exclude`: trim the Wails target overlay / facade. Roots with no selected routes do not get `transports/<overlay_name>` output; the shared Go / TypeScript contract layers are still generated in full.

## Go Output Layout

Wails Go overlays are generated under the transport target directory inside the Go target output tree referenced by `server`:

```text
routes/
  api/
    demo/
      gen_interface.go
      impl.go
providers/
  gen_context.go
runtime/
  errors/
    gen_errors.go
transports/
  wailsv3/
    gen_runtime.go
    api/
      demo/
        gen_overlay.go
        gen_service.go
        impl_service.go
```

`routes/<go-root-segment>/<go-group-segment>` is the transport-neutral core; `providers` is the shared provider runtime; `runtime/errors` is the generated typed error runtime; `transports/<overlay_name>/<go-root-segment>/<go-group-segment>` is the Wails Go target. Go-safe segments write `/api-v1` as `api_v1` and `/admin/v1` as the single segment `admin_v1`, so Go directories do not guarantee one directory per URL slash segment. The route-local `impl_service.go` is a user-owned bootstrap constructor entry and is preserved across regeneration. If you want a `views/...` package path, configure the referenced Go server target with `out_dir = ".../views"`; Wails does not append it implicitly.

## TypeScript Output Layout

Wails TypeScript overlays are generated inside the TypeScript target output tree referenced by `clients`:

```text
api/
  runtime/
    gen_client.ts
    gen_types.ts
  routes/
    api/
      demo/gen_client.ts
  transports/
    gen_clients.ts
    clients.ts
    http/
      gen_transport.ts        # only when an HTTP target is also declared
      api/gen_factory.ts
    wailsv3/
      gen_transport.ts
      api/
        gen_factory.ts
        demo/gen_client.ts
```

`api/runtime` is the shared transport-neutral runtime; `api/routes/<root>` contains route core clients; `api/transports/http/<root>` and `api/transports/<overlay_name>/<root>` are scenario facades. Wails route overlays expose `createClient(config)` plus the narrow `type <Group>Client`, and the root overlay exposes `createClients(config)`.

When the same TypeScript output tree has both HTTP and Wails transports, `api/transports/clients` exports a stable aggregate entrypoint: `createHttpClients`, `createWailsV3Clients` / `createWailsV2Clients`, each transport's `GeneratedClients` type alias, and `CommonGeneratedClients`, the client subset shared by all generated transports. `createClientsForTransport({ transport })` creates only that common subset, which is useful for a project-owned GUI/Web client wrapper. Routes excluded from the Wails target by `include` / `exclude` do not appear in the common subset. Use the transport-specific `api/transports/http/<root>` or `api/transports/<overlay_name>/<root>` factory when a full transport-specific client set is needed.

## Provider Hooks

Go HTTP and Wails share the generated `RouteExecutor` provider pipeline. Wails services run `req/auth/handle/rsp` and connection preflight providers by default, so projects do not need a handwritten per-route adapter just to restore auth/provider behavior.

Long-term ownership boundary:

- `gen_*`: generator-owned and overwritten.
- `impl_auth.go`: user-owned, keeping `AuthContext` and `BuildAuthContext(ctx, req)`.
- `impl_*` helpers: user-owned, but should not retake the provider main flow.
- Wails runtime: generated-only, no `impl_runtime.go`.

`RouteExecutor` is a reusable route-level execution plan and carries `RouteInfo`. Request-scoped state must live in `Context` or its metadata store, and custom providers should be stateless/reentrant. When a provider implementation must vary by Wails / HTTP or by root/route, use `providers.RegisterProviderFactory` and inspect `ProviderSpec.Route`; selection happens when the executor is created and does not enter the request hot path. HTTP-only providers should explicitly import `transports/http` under the generated package root and use adapter helpers such as `httptransport.RequireGin(ctx)` to access Gin context.

HTTP behavior tests should generally live in an external test package, for example `package demo_test`, and import the `transports/http/<root>/<group>` adapter under the generated package root. Business handler unit tests can stay in the route package and call handlers directly with typed `ctx/req` values. Use `transports/http.RequireGin(ctx)` only when Gin APIs are actually required; doing so explicitly couples that code to the HTTP adapter.

## TypeScript Transport

The recommended mode is `frontend_mode = "external"`: an existing WebUI keeps the shared TypeScript API source of truth, while each Wails target only keeps an app shell, build config, and project-owned transport shim.

An external frontend must load the Wails runtime before mounting the app or creating clients. The generated Wails transport exports `ensureWailsRuntime()` as the minimal bootstrap helper:

```ts
import { ensureWailsRuntime, WailsV3Transport } from "./api/transports/wailsv3/transport";
import { createClients } from "./api/transports/wailsv3/api";

await ensureWailsRuntime();

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

The Wails v3 helper checks and loads `/wails/runtime.js` when needed. The Wails v2 helper checks and loads `/wails/ipc.js` plus `/wails/runtime.js` when needed. The transport also performs a lazy runtime check on first use, but explicit bootstrap is recommended so the UI framework does not mount before the runtime is ready.

The Wails facade reuses the shared core clients and injects the Wails transport by default:

```ts
import { createClients } from "./api/transports/wailsv3/api";
import { WailsV3Transport } from "./api/transports/wailsv3/transport";

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

Projects that run both HTTP and Wails can import the common factory and type from one path, then keep auth, error handling, or specific client overrides in their own wrapper:

```ts
import {
    createClientsForTransport,
    type CommonGeneratedClients,
} from "./api/transports/clients";
import { WailsV3Transport } from "./api/transports/wailsv3/transport";

const transport = new WailsV3Transport();
const clients: CommonGeneratedClients = createClientsForTransport({ transport });
```

The Wails v3 transport uses the official runtime `Call.ByName(...)` contract and a generated binding manifest; Go import paths in that binding manifest use the same Go-safe segments, so projects do not need to hand-code Go service package paths. The Wails v2 transport continues to use the official `window.go.<package>.<service>.<method>` runtime shape.

## Wails-only App

`api-blueprint` can be used in a Wails app that does not start an HTTP server. `api-gen generate --target desktop.v3` first ensures the dependent Go / TypeScript targets are generated, then writes the Wails overlay; without an `http-transport` target it does not generate the Gin HTTP adapter. The Wails app shell only needs to register generated services. It does not need to import the HTTP adapter or start a Gin/HTTP listener.

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/myapp/generated"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"

[[targets]]
id = "desktop.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"
```

```sh
mkdir -p golang typescript
uv run api-gen generate -c api-blueprint.toml --target desktop.v3
cd app
wails3 doctor
wails3 build
```

When only a Wails target is declared, the Wails app imports only generated services and its build graph does not need Gin. If one project needs both HTTP and Wails, add another `[[targets]]` with `kind = "http-transport"`. See `examples/wails-hello` for the complete minimal example.

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

## Long-Connection Bridge

Wails TypeScript does not expose raw WebSocket and does not require business code to hand-write runtime event names. In the default Wails transport, `STREAM` / `CHANNEL` map to session-scoped runtime events, and event names exist only inside the generated Go runtime and generated TypeScript transport. Connection setup uses a client-allocated `session_id`: the generated TypeScript bridge computes deterministic per-session event names, subscribes first, and then sends the connect RPC so ordered delivery cannot miss `seq=1`. The generated service still exposes a lightweight `ConnectionHub` replacement point; custom hubs receive `Open(ConnectionOpenSpec)` and must return a descriptor that preserves the generated event naming contract. The default hub fully supports only `ConnectionScope.SESSION`, and `APP` / `TOPIC` broadcast or topic routing policy still belongs in a custom hub.

Generated Wails `STREAM` / `CHANNEL` delivery is ordered-async by default: the Go runtime adds per-session `seq` envelopes, and the generated TypeScript bridge reorders messages before business `onMessage` / `onClose`. This is intentionally different from HTTP, where `STREAM`/`CHANNEL` already rely on native per-connection SSE / WebSocket ordering and do not add the Wails seq/reorder overlay. Routes can opt into `delivery=ConnectionDelivery.UNORDERED` for telemetry-style flows where arrival order is not worth the buffering cost; that opt-out has transport-specific meaning mainly on Wails.

Ordered delivery is fail-fast rather than loss-tolerant. If an ordered route sees a `seq` gap that does not drain within the generated timeout, receives an invalid ordered envelope, or exceeds the pending reorder buffer, the bridge closes locally with structured `onClose` info such as `error: "ordered_delivery_gap"`, `error: "ordered_delivery_protocol_error"`, or `error: "ordered_delivery_buffer_overflow"`. The generated transport does not auto-reconnect; applications that want retry should reopen the stream or channel from their own `onClose` policy.

### Compatibility

Custom Wails hubs must implement `ConnectionHub.Open(ConnectionOpenSpec)`, consume the requested `session_id`, and reuse the generated descriptor/event-name helper logic. Hub signatures based on positional route/event arguments are migration entrypoints, not the recommended long-term interface.

`STREAM` returns `ApiStreamBridge<ServerMessage, CloseMessage>`:

```ts
const stream = demoClient.subscribeEvents({ open, headers });
await stream.ready;

const offMessage = stream.onMessage((message) => {
    console.log(message);
});

const offClose = stream.onClose((info) => {
    console.log(info.reason);
});

await stream.close(1000, "done");
offMessage();
offClose();
```

`onClose` receives the typed close payload generated from `.CLOSE(Model)`. On ordered routes, transport-level fail-fast errors are surfaced through the same callback, so application code can inspect `info.error` and decide whether to reopen. Client-side `close(code, reason)` is only an active close request; model business cancellation through a `CHANNEL` `CLIENT_MESSAGE(cancel=...)`.

`CHANNEL` returns `ApiChannelBridge<ServerMessage, ClientMessage, CloseMessage>`:

```ts
const bridge = demoClient.openSession({ open, headers });
await bridge.ready;

const offMessage = bridge.onMessage((message) => {
    console.log(message);
});

await bridge.send(payload);
await bridge.close(1000, "done");
offMessage();
```

`WS().RECV().SEND()` has been removed from the blueprint DSL. Use `CHANNEL` for bidirectional WebSocket-style contracts and `STREAM` for server-only event streams.

## Harness Examples

`examples/wails-harness/v2` and `examples/wails-harness/v3` are repo-owned minimal runnable examples. Their app shells are handwritten, but they directly consume Go bind wrappers and TypeScript API artifacts from the shared trees.

`examples/wails-hello` is a standalone Wails v3 hello world example with its own Blueprint, generated snapshots, and handwritten app shell. It demonstrates the minimal `Go handler -> generated Wails binding -> generated TypeScript client -> GUI dialog` loop.
