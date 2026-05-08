# 生成器说明

本文概述非 Wails、非 gRPC 的主要生成器。Wails 见 [Wails 说明](wails.md)，gRPC 见 [gRPC 说明](grpc.md)。

## 共享规划与 capability

`api-gen check`、contract / agent artifact projection 和各语言 writer 使用同一份 planner / capability metadata。生成前会统一校验 target 依赖、route kind、request kind 与 response wrapper，避免 check 通过但 writer 才发现不支持的情况。

Kotlin / Python 是新实现的生成器表面，当前按 preview 口径使用。它们的 contract / agent artifact path 指向完整镜像 route path 的输出路径，例如 `routes/api/demo`；Python 不再使用 `routes/root` sentinel。

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

Go 生成器输出：

- route interface 与默认 `impl.go`。
- 请求 / 响应 / 上下文结构。
- provider runtime 与 wrapper。
- transport-neutral Go core。
- 可选 HTTP/Gin adapter。

`gen_*` 文件由生成器拥有，重生成会覆盖。`impl_*` 与非 `gen_*` 文件是用户拥有扩展点，重生成时保留。Kotlin 使用相同 ownership 模型，但生成器拥有文件命名为 `Gen*.kt`，非 `Gen*` façade / extension 文件由用户拥有。

`go-server` 只负责 Go 服务端 core。HTTP / Wails 输出由 `http-transport` / `wails-transport` target 通过 `server = "go.server"` 显式挂接。HTTP 入口生成在 `views/transports/http/<root>` 中，例如 `views/transports/http/api.NewBlueprint(engine)`。

Go route core 固定生成在 `views/routes/**`，provider runtime 固定生成在 `views/providers`。这两个目录名不再通过配置自定义，业务 root 可以安全使用 `/providers` 或 `/transports` 这类路径。

`views/providers` 是全局 transport-neutral runtime，不按 blueprint root 拆分。TypeScript 的 per-root `runtime` 主要服务模型和 client 命名隔离，和 Go provider hook 不是同一类职责。

需要按 root、route 或 transport 切换 provider 实现时，不要解析请求 path。生成器会在每个 route executor 构造期写入 `RouteInfo`，并把它挂到 `Context.Route` 与 `ProviderSpec.Route`：

```go
providers.RegisterProviderFactory(providers.PROV_RSP, func(spec providers.ProviderSpec) providers.Provider {
	if spec.Route.Root != "static" {
		return nil
	}
	// 可选：spec.Handler 是当前 route 的 typed handler，可在确实需要时做类型断言。
	return NewCachedRspProvider(spec.Data)
})
```

自定义 provider 可以在 DSL 中使用 `provider.Custom(name, data)` 加入 pipeline：

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

provider factory 应在应用启动或包 `init()` 阶段注册。provider sequence 只在 executor 创建期解析，factory 也只在创建期运行；高并发请求路径只执行已缓存 provider 实例。如果需要不用全局 registry 的项目内选择逻辑，直接在用户拥有的 `views/providers/impl_provider.go` 中实现 `SelectProvider(spec, handler)`；旧的 `Select(key, value, handler)` hook 已移除。

HTTP adapter 只在 blueprint root 存在直接 routes 时导入 root router。handler 如果已经通过 Gin 写出响应，adapter 不再追加自动响应；否则没有 `rsp` provider 的 route 仍保持旧行为，由 adapter 写出 handler 返回值。

需要由 handler 完全接管 HTTP 成功响应时，使用 `HTTP_RAW_RESPONSE()`。该语义只影响 HTTP adapter：成功时不自动写响应，错误时如果 Gin writer 尚未写出则返回 500；它不是 shared provider，也不会改变 Wails overlay。

### 长连接契约

Go core 将 `STREAM` / `CHANNEL` 生成为 transport-neutral handler interface。业务代码不直接感知 SSE、WebSocket 或 Wails event name：

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

HTTP transport 中，`STREAM` 生成 SSE adapter，`CHANNEL` 生成 WebSocket adapter。Wails transport 中，两者默认由 session-scoped runtime events 承载。多消息 variant 会生成一个带 `type` discriminator 的共享 union schema；不要把不同 variant 拆成多个 transport event。`.CLOSE(Model)` 会进入 Go handler 泛型与 TypeScript `onClose` 类型；服务端业务关闭使用 `Close(&CLOSE_...{...})`，异常或协议错误使用 `Abort(code, reason)`。

默认 HTTP/Wails runtime 只完整实现 `ConnectionScope.SESSION`。`APP` / `TOPIC` 会保留在 route contract 中，后续可通过自定义 connection hub / manager 实现广播或 topic 路由，不由生成器内置业务 fan-out 策略。

默认生成的连接 handler 仍保持 `not implemented`，避免把示例业务逻辑写进所有用户项目。仓库示例在用户拥有的 `examples/golang/views/routes/api/demo/impl.go` 中手写了最小用法：`STREAM` 展示 `Open()`、构造 server message、`Send()` 与 typed `Close()`；`CHANNEL` 额外展示 `Recv(ctx)` 接收客户端消息。

## TypeScript

```sh
api-gen generate -c api-blueprint.toml --target typescript.client
```

TypeScript client target 输出：

- `models.ts` / `gen_models.ts`。
- request client class。
- transport-neutral `ApiClientConfig`。
- 由 transport target 注入的 `createClients(config)` facade。
- user-owned passthrough 文件，例如 `client.ts`、`transport.ts`、`factory.ts`。

`base_url` / `base_url_expr` 由生成的 HTTP transport facade 拥有，不进入 route/runtime client。`base_url_expr` 会原样写入生成代码，适合 Vite、Next.js 等运行时配置；它与 `base_url` 互斥。

`STREAM` / `CHANNEL` 会生成 `ApiStreamBridge<Recv, Close>` 与 `ApiChannelBridge<Recv, Send, Close>`。单消息方向直接使用模型类型；多消息方向生成判别联合类型，例如 `{ type: "progress"; data: TaskProgress }`。HTTP transport 的 stream bridge 使用 SSE，channel bridge 使用内部 envelope 的 WebSocket 来区分普通消息与 close lifecycle payload；Wails transport 使用 generated runtime events，但事件名不暴露给业务 client。

## Kotlin Android

```sh
api-gen generate -c api-blueprint.toml --target kotlin.client
```

Kotlin target 输出 OkHttp + kotlinx.serialization Android 客户端。

Kotlin 输出为 package-first layout，route 目录完整镜像真实 route path：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

这是相对旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 的破坏性布局变更。重生成时旧布局会被清理，业务代码应改为导入 `<package>.<root>.runtime`、`<package>.<root>.routes...` 与 `<package>.<root>.transports.http` 下的类型。

Kotlin 生成器拥有文件统一命名为 `Gen*.kt`，例如 `routes/api/demo/GenDemoApi.kt` 和 `runtime/GenApiClient.kt`，并带 generated header。非 `Gen*` façade 文件，例如 `DemoApi.kt`、`runtime/ApiClient.kt`、`transports/http/HttpApiClient.kt`，是保留的用户扩展点。

Kotlin 通过 transport abstraction 生成 `rpc`、`legacy_ws`、`stream`、`channel` route surface，支持 query/json/form/binary/open request kind，并支持 none/general/custom response wrapper。内置 OkHttp adapter 以 RPC 为主；长连接 bridge 属于 preview/custom transport surface，建议先用 `api-gen check` 和目标平台 smoke 验证后再接入生产调用路径。

`base_url` / `base_url_expr` 会写入生成的 `transports/http/HttpApiConfig.kt` 默认值，不进入 transport-neutral runtime client。

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client 使用 `python_package_root` 作为包根，输出 async-first HTTP client：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_client.py` 是生成 route client，`routes/<root>/<group...>/client.py` 是保留的 passthrough 入口，`transports/http/gen_client.py` 提供默认 httpx adapter。root-level route 直接生成在 `routes/<root>`，不生成 `routes/root`。该 adapter 实现 RPC 请求；WS/STREAM/CHANNEL bridge interface 会生成，但连接 transport 需要项目自定义或后续扩展。`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。

## Python Server

```sh
api-gen generate -c api-blueprint.toml --target python.server
```

Python server 同样使用 `python_package_root` 作为包根，输出 route service contracts/stubs 与 FastAPI HTTP adapter scaffold：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_service.py` 是生成的 service contract，`routes/<root>/<group...>/service.py` 是用户可维护 stub 入口，`transports/http/gen_server.py` 与 `server.py` 提供 FastAPI HTTP adapter scaffold。root-level route 直接生成在 `routes/<root>`，不生成 `routes/root`。该目标是新实现 surface，建议把生成结果纳入项目自己的类型检查、lint 和安装 smoke。

## 预留 targets

Go client 目前只作为 target schema 预留，不生成业务代码。

## examples 快照

`examples/golang/`、`examples/typescript/` 与 `examples/kotlin/` 是生成快照，不是业务真源。Kotlin/Python contract / agent artifact 索引会使用新的 route 输出路径。需要接受预期生成变化时，使用：

```sh
make example-refresh
```
