# Wails

`api-gen-wails` 生成 Wails API artifacts，不生成完整 Wails scaffold，也不调用 Wails CLI 生成 JS bindings。

Wails CLI 在本仓库中的角色是构建和打包 `examples/wails-harness/{v2,v3}` 这类手写 harness，而不是 `api-gen-wails` 的代码输入。

## Target 配置

```toml
[[transport.targets]]
id = "wails.v3"
kind = "wails"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

- `id`：供 `--target`、`--list-targets`、`--explain-target` 使用。
- `kind`：Wails target 固定为 `wails`。
- `version`：支持 `v3` 和 `v2`。
- `overlay_name`：默认 `wailsv3` / `wailsv2`，必须唯一。
- `frontend_mode`：默认 `external`；`none` 跳过 Wails TypeScript overlay。
- `include` / `exclude`：裁剪 Wails target overlay / facade。没有任何 selected route 的 root 不会生成 `transports/<overlay_name>`；共享 Go / TypeScript 主契约层仍完整生成。

## Go 输出布局

Wails Go overlay 生成在共享 `[golang]` 输出树的 transport target 目录中：

```text
views/
  routes/
    api/
      demo/
        gen_interface.go
        impl.go
  providers/
    gen_context.go
  transports/
    wailsv3/
      gen_runtime.go
      api/
        demo/
          gen_overlay.go
          gen_service.go
          impl_service.go
```

`views/routes/<root>/<group>` 是 transport-neutral core；`views/providers` 是共享 provider runtime；`views/transports/<overlay_name>` 是 Wails target。route 目录中的 `impl_service.go` 是用户拥有的 bootstrap 构造入口，重生成时保留。

## TypeScript 输出布局

Wails TypeScript overlay 生成在共享 `[typescript]` 输出树中：

```text
api/
  runtime/
    gen_client.ts
    gen_models.ts
  routes/
    api/
      demo/gen_client.ts
  transports/
    http/
      gen_transport.ts        # 仅当同时声明 HTTP target
      api/gen_factory.ts
    wailsv3/
      gen_transport.ts
      api/
        gen_factory.ts
        demo/gen_client.ts
```

`api/runtime` 是共享 transport-neutral runtime；`api/routes/<root>` 是 route core client；`api/transports/http/<root>` 与 `api/transports/<overlay_name>/<root>` 是场景 facade。Wails route overlay 暴露 `createClient(config)` 与窄类型 `type <Group>Client`，root overlay 暴露 `createClients(config)`。

## Provider 与 hook

Go HTTP 与 Wails 共用生成的 `RouteExecutor` provider pipeline。Wails service 默认会执行 `req/auth/handle/rsp` 与 WS preflight provider，不需要项目为每个 route 手写 adapter 来补 auth/provider。

长期 ownership 边界：

- `gen_*`：生成器拥有，重生成覆盖。
- `impl_auth.go`：用户拥有，保留 `AuthContext` 与 `BuildAuthContext(ctx, req)`。
- `impl_*` helper：用户拥有，但不应重新承载 provider 主流程。
- Wails runtime：generated-only，不提供 `impl_runtime.go`。

`RouteExecutor` 是 route-level 可复用执行计划，并会携带 `RouteInfo`。请求级状态必须放入 `Context` 或 metadata store，自定义 provider 应保持 stateless/reentrant。需要按 Wails / HTTP 或 root/route 选择不同 provider 实现时，使用 `views/providers.RegisterProviderFactory` 读取 `ProviderSpec.Route`，选择发生在 executor 创建期，不进入请求热路径。HTTP-only provider 应显式导入 `views/transports/http` 并通过类似 `httptransport.RequireGin(ctx)` 的 adapter helper 获取 Gin 上下文。

HTTP 行为测试建议放在外部测试包中，例如 `package demo_test`，再导入 `views/transports/http/<root>/<group>` adapter。业务 handler 单测可以继续放在 route 包内，直接构造 typed `ctx/req` 调用 handler。只有确实需要 Gin API 时才使用 `views/transports/http.RequireGin(ctx)`；这会让相关代码显式绑定 HTTP adapter。

## TypeScript transport

推荐 `frontend_mode = "external"`：已有 WebUI 继续持有共享 TypeScript API 真源，Wails target 只保留 app shell、构建配置和项目自有 transport shim。

external frontend 必须在应用挂载或创建 clients 前加载 Wails runtime。生成的 Wails transport 导出 `ensureWailsRuntime()`，可作为最小 bootstrap：

```ts
import { ensureWailsRuntime, WailsV3Transport } from "./api/transports/wailsv3/transport";
import { createClients } from "./api/transports/wailsv3/api";

await ensureWailsRuntime();

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

Wails v3 helper 会检测并按需加载 `/wails/runtime.js`；Wails v2 helper 会按需加载 `/wails/ipc.js` 与 `/wails/runtime.js`。transport 首次调用时也会懒检查 runtime，但推荐显式 bootstrap，以避免 UI 框架在 runtime 未就绪时挂载。

Wails facade 会复用共享 core client，并默认注入 Wails transport：

```ts
import { createClients } from "./api/transports/wailsv3/api";
import { WailsV3Transport } from "./api/transports/wailsv3/transport";

const clients = createClients({
    transport: new WailsV3Transport(),
});
```

Wails v3 transport 使用官方 runtime 的 `Call.ByName(...)` 并由生成器内置 binding manifest；业务项目不需要手写 Go service 包路径。Wails v2 transport 继续使用官方 `window.go.<package>.<service>.<method>` 运行时形态。

## Wails-only app

`api-blueprint` 可以用于不启动 HTTP 服务的 Wails app。`api-gen-wails` 仍会生成共享 Go / TypeScript 契约层；只声明 `kind = "wails"` target 时不会生成 Gin HTTP adapter。Wails app shell 只需要注册 generated services，不需要导入 HTTP adapter，也不需要启动 Gin/HTTP listener。

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[golang]
codegen_output = "golang"
module = "example.com/myapp/generated"

[typescript]
codegen_output = "typescript"

[[transport.targets]]
id = "desktop.v3"
kind = "wails"
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

只声明 Wails target 时，Wails app 只 import generated services，构建图不需要包含 Gin。若同一个项目需要 HTTP + Wails，再额外声明一个 `[[transport.targets]] kind = "http"`。完整最小示例见 `examples/wails-hello`。

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
