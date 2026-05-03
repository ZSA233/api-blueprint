# Wails

`api-gen-wails` 生成 Wails API artifacts，不生成完整 Wails scaffold，也不调用 Wails CLI 生成 JS bindings。

Wails CLI 在本仓库中的角色是构建和打包 `examples/wails-harness/{v2,v3}` 这类手写 harness，而不是 `api-gen-wails` 的代码输入。

## Target 配置

```toml
[[wails.targets]]
id = "wails.v3"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

- `id`：供 `--target`、`--list-targets`、`--explain-target` 使用。
- `version`：支持 `v3` 和 `v2`。
- `overlay_name`：默认 `wailsv3` / `wailsv2`，必须唯一。
- `frontend_mode`：默认 `external`；`none` 跳过 Wails TypeScript overlay。
- `include` / `exclude`：只裁剪 Wails overlay，不裁剪共享 Go / TypeScript 主契约层。

## Go 输出布局

Wails Go overlay 生成在共享 `[golang]` 输出树旁边：

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

Go 下所有 `_...` 目录是生成器保留命名空间。`bindings/impl_service.go` 是用户拥有的 bootstrap 构造入口，重生成时保留。

## TypeScript 输出布局

Wails TypeScript overlay 生成在共享 `[typescript]` 输出树中：

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

TypeScript 下所有 `(...)` 目录是生成器保留命名空间。Wails route overlay 暴露 `createClient(config)` 与窄类型 `type <Group>Client`，root overlay 暴露 `createClients(config)`。

## Provider 与 hook

Go HTTP 与 Wails 共用生成的 `RouteExecutor` provider pipeline。Wails service 默认会执行 `req/auth/handle/rsp` 与 WS preflight provider，不需要项目为每个 route 手写 adapter 来补 auth/provider。

长期 ownership 边界：

- `gen_*`：生成器拥有，重生成覆盖。
- `impl_auth.go`：用户拥有，保留 `AuthContext` 与 `BuildAuthContext(ctx, req)`。
- `impl_*` helper：用户拥有，但不应重新承载 provider 主流程。
- Wails runtime：generated-only，不提供 `impl_runtime.go`。

`RouteExecutor` 是 route-level 可复用执行计划。请求级状态必须放入 `Context` 或 metadata store，自定义 provider 应保持 stateless/reentrant。HTTP-only provider 应显式调用 `RequireHTTP()`。

## TypeScript transport

推荐 `frontend_mode = "external"`：已有 WebUI 继续持有共享 TypeScript API 真源，Wails target 只保留 app shell、构建配置和项目自有 transport shim。

external frontend 必须在应用挂载或创建 clients 前加载 Wails runtime。生成的 Wails transport 导出 `ensureWailsRuntime()`，可作为最小 bootstrap：

```ts
import { ensureWailsRuntime } from "./api/(shared)/(wailsv3)/transport";
import { createClients } from "./api/(wailsv3)/factory";
import { WailsV3Transport } from "./api/(shared)/(wailsv3)/transport";

await ensureWailsRuntime();

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

Wails v3 helper 会检测并按需加载 `/wails/runtime.js`；Wails v2 helper 会按需加载 `/wails/ipc.js` 与 `/wails/runtime.js`。transport 首次调用时也会懒检查 runtime，但推荐显式 bootstrap，以避免 UI 框架在 runtime 未就绪时挂载。

共享 factory 可用于 HTTP 和 Wails：

```ts
import { createClients } from "./api/(wailsv3)/factory";
import { WailsV3Transport } from "./api/(shared)/(wailsv3)/transport";

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

Wails v3 transport 使用官方 runtime 的 `Call.ByName(...)` 并由生成器内置 binding manifest；业务项目不需要手写 Go bindings 包路径。Wails v2 transport 继续使用官方 `window.go.<package>.<service>.<method>` 运行时形态。

## Wails-only app

`api-blueprint` 可以用于不启动 HTTP 服务的 Wails app。`api-gen-wails` 仍会生成共享 Go / TypeScript 契约层，但 Wails app shell 只需要注册 generated bindings，不需要调用 `views.NewEngine()`，也不需要启动 Gin/HTTP listener。

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "golang"
module = "example.com/myapp/generated"

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

当前语义是“不开 HTTP 服务”，不是“生成物完全无 HTTP 依赖”：共享 Go 契约层仍包含 HTTP/Gin 注册代码和依赖。完整最小示例见 `examples/wails-hello`。

`examples/wails-hello` 的手动启动短命令：

```sh
make wails-hello-dev
```

等价于先重生成 hello overlay，再在 `examples/wails-hello/app` 下运行 `wails3 task dev`；该任务会通过 `build/config.yml` 启动 frontend dev server、构建 Go binary 并运行 Wails app。自动验证短命令：

```sh
make wails-hello-check
make wails-hello-compile-check
```

`wails-hello-check` 是严格模式，会检查 snapshot drift；`wails-hello-compile-check` 只验证重生成后的 TypeScript、Go 和 Wails v3 build，适合开发中快速确认。

## Socket bridge

Wails TypeScript 不暴露 raw WebSocket，而是统一使用 `ApiSocketBridge<ServerMessage, ClientMessage>`。

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

HTTP shared client 仍保留 `connect<Route>Raw()` 作为原生 WebSocket escape hatch。

## Harness 示例

`examples/wails-harness/v2` 与 `examples/wails-harness/v3` 是 repo-owned 最小可运行示例。它们手写 app shell，但直接消费共享树里的 Go bind wrappers 与 TypeScript API 产物。

`examples/wails-hello` 是独立 Wails v3 hello world 示例，包含自己的 Blueprint、生成快照和手写 app shell。它演示 `Go handler -> generated Wails binding -> generated TypeScript client -> GUI dialog` 的最小闭环。
