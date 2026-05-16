# 生成器说明

本文概述非 Wails、非 gRPC 的主要生成器。Wails 见 [Wails 说明](wails.md)，gRPC 见 [gRPC 说明](grpc.md)。

## 共享规划与 capability

`api-gen check`、contract / agent artifact projection 和各语言 writer 使用同一份 planner / capability metadata。生成前会统一校验 target 依赖、route kind、request kind 与 response envelope，避免 check 通过但 writer 才发现不支持的情况。

生成器状态和路径约定属于共享规划的一部分。Go server 为可用目标；Go client、Kotlin / Java / Python target 按 preview 口径使用。Go server / Go client / Wails Go 的 contract / agent artifact path 使用 Go-safe route package segment，例如 `/api-v1` -> `api_v1`、`/admin/v1` -> `admin_v1`。Kotlin / Java / Python artifact path 使用各自语言的 route 输出布局，例如 `routes/api/demo`。

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

Go 生成器输出：

- route interface 与默认 `impl.go`。
- 请求 / 响应 / 上下文结构。
- provider runtime 与 response envelope codec。
- transport-neutral Go core。
- 可选 HTTP/Gin adapter。

`gen_*` 文件由生成器拥有，重生成会覆盖。`impl_*` 与非 `gen_*` 文件是用户拥有扩展点，重生成时保留。Kotlin / Java 使用相同 ownership 模型，Kotlin 生成器拥有文件命名为 `Gen*.kt`，Java 生成器拥有文件命名为 `Gen*.java` 以及 runtime generated 文件，非 `Gen*` façade / extension 文件由用户拥有。

`go-server` 只负责 Go 服务端 core。`out_dir` 就是生成包根；如果项目希望 import path 包含 `views`，应把 `views` 写进 `out_dir`。HTTP / Wails 输出由 `http-transport` / `wails-transport` target 通过 `server = "go.server"` 显式挂接。HTTP 入口生成在 `<out_dir>/transports/http/<go-root-segment>` 中，例如 `transports/http/api.NewBlueprint(engine)`。

Go route core 生成在 `<out_dir>/routes/<go-root-segment>/**`，provider runtime 生成在 `<out_dir>/providers`，transport adapter 生成在 `<out_dir>/transports/**`，typed error runtime 生成在 `<out_dir>/runtime/errors/**`。Go-safe segment 会把非 `[0-9A-Za-z_]` 转成 `_`、去首尾 `_`，数字开头补 `p_`，Go keyword 补 `_pkg`；URL、route path 和 selection/filter 语义不变，因此 Go 目录不保证逐级镜像 URL slash 层级。如果希望 import path 包含 `/views`，应显式设置 `out_dir = ".../views"`。

`providers` 是生成包根下的全局 transport-neutral runtime，不按 blueprint root 拆分。TypeScript 的 per-root `runtime` 主要服务模型和 client 命名隔离，和 Go provider hook 不是同一类职责。

需要按 root、route 或 transport 切换 provider 实现时，不要解析请求 path。生成器会在每个 route executor 构造期写入 `RouteInfo`，并把它挂到 `Context.Route` 与 `ProviderSpec.Route`：

```go
providers.RegisterProviderFactory(providers.PROV_RSP, func(spec providers.ProviderSpec) providers.Provider {
	if spec.Route.Root != "static" {
		return nil
	}
	// 可选：spec.Handler 是该 route 的 typed handler，可在确实需要时做类型断言。
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

provider factory 应在应用启动或包 `init()` 阶段注册。provider sequence 只在 executor 创建期解析，factory 也只在创建期运行；高并发请求路径只执行已缓存 provider 实例。如果需要不用全局 registry 的项目内选择逻辑，直接在用户拥有的 `providers/impl_provider.go` 中实现 `SelectProvider(spec, handler)`。

#### 兼容性说明

使用较早 `Select(key, value, handler)` provider hook 的项目，应把选择逻辑迁移到 `SelectProvider(spec, handler)`，让 route metadata 保持显式。

HTTP adapter 只在 blueprint root 存在直接 routes 时导入 root router。handler 如果已经通过 Gin 写出响应，adapter 不会追加自动响应；否则没有 `rsp` provider 的 route 由 adapter 写出 handler 返回值，作为兼容行为。

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

默认生成的连接 handler 仍保持 `not implemented`，避免把示例业务逻辑写进所有用户项目。仓库示例在用户拥有的 `examples/golang/server/views/routes/api/demo/impl.go` 中手写了最小用法：`STREAM` 展示 `Open()`、构造 server message、`Send()` 与 typed `Close()`；`CHANNEL` 额外展示 `Recv(ctx)` 接收客户端消息。

### Typed errors

ContractGraph 会把 `Blueprint(errors=...)` 和 route `.ERR(...)` 声明收集成语言无关 typed errors。Manifest `2.0` 保留全局 `errors` 完整定义表，并把 compact route-local refs（`id/group/key/code/message/toast`）写入 `routes[].errors`，因此生成客户端和 `api-gen inspect errors --route ...` 都能从该 route 看到可抛错误。`id` 是公开协议错误身份，`code` 只是业务码，可跨 group 或 route 复用。`ResponseEnvelope` 决定 wire shape：默认 `CodeMessageDataEnvelope` 使用 `{ code, message, data, error? }`，严格 `{ code, message, data }` 形态可选 `LegacyCodeMessageDataEnvelope`，显式选择 `OkDataErrorEnvelope` 才使用 `{ ok, data/error }`。

生成 runtime API 使用更贴近业务侧的 `ApiError`、`ApiErrors`、`ApiErrorsByID`、`lookupApiError`、`isApiError` 等命名；catalog 字典只是内部索引，不是主要用户入口。默认 Go、TypeScript、Python、Kotlin、Java client transport 会按 route 的 envelope spec 解包，按 `id`、`(route_id, code)`、global code fallback 的顺序还原 payload，并抛出或返回 typed `ApiError`。Go server 在 `runtime/errors/common_err` 等分组包下生成 typed `ApiError` 值；`WithToast(...)` 返回不可变覆盖副本，适合按请求语言、租户或灰度返回动态 `toast.text`。业务 i18n 系统按 toast key 解析请求语言，客户端 helper 按 `toast.text`、外部 i18n、`toast.default`、`message` 的优先级得到展示文案。HTTP status 保持传输状态，不从业务错误码推导。

Go server handler 可以直接返回 generated typed error，或者返回一个未声明业务错误码来触发客户端 unknown fallback：

```go
switch req.Q.Mode {
case "token":
    return nil, common_err.TOKEN_EXPIRE
case "rate_limit":
    return nil, demo_err.RATE_LIMITED.WithToast(apperrors.ToastPayload{
        Key: "demo.rate_limited", Level: "warning",
        Default: "请求过于频繁，请稍后再试", Text: "请等待 30 秒后重试",
    })
case "unknown":
    return nil, apperrors.New(70001, "example undefined business error")
}
```

TypeScript client 会从默认 HTTP transport 抛出 `ApiError`，业务代码通常只需要类型判断、按 `id/code` 分支，再用 toast helper 得到展示文案：

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

Kotlin 提供生成快照和编译验证；catch 形态与其他客户端一致：

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

仓库的 `/api/demo/error-demo` 示例和 Go / TypeScript / Python / Java suite 覆盖了 declared error、route-local error、动态 `toast.text` 和未声明错误码 fallback。

## Go Client

```sh
api-gen generate -c api-blueprint.toml --target go.client
```

Go client target 输出 preview HTTP client：

- `runtime/gen_*.go`
- `runtime/gen_types.go`
- `runtime/binary/gen_runtime.go`
- target 根目录的 `gen_client.go` / `client.go` 聚合 public facade
- `routes/<go-root-segment>/<go-group-segment>/gen_client.go`
- `routes/<go-root-segment>/<go-group-segment>/gen_types.go`
- `routes/<go-root-segment>/<go-group-segment>/gen_binary.go`，仅 binary schema route group 生成
- `routes/<go-root-segment>/<go-group-segment>/client.go`
- `transports/http/gen_config.go`
- `transports/http/gen_transport.go`
- `transports/http/client.go`

`gen_*.go` 文件由生成器拥有并覆盖；`client.go` façade 由用户拥有并保留。推荐入口是 `apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})`，然后调用 `api.Demo.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "token"})` 这类 route 方法。route/runtime client 只依赖 transport abstraction，`base_url` / `base_url_expr` 只写入 HTTP transport config。默认 HTTP adapter 实现 RPC 的 query/json/form/binary 请求；WS 兼容 surface、STREAM 和 CHANNEL 方法也会生成，默认 HTTP adapter 返回明确 unsupported error，项目可以替换自定义 transport。

## TypeScript

```sh
api-gen generate -c api-blueprint.toml --target typescript.client
```

TypeScript client target 输出：

- `types.ts` / `gen_types.ts`。
- request client class。
- transport-neutral `ApiClientConfig`。
- 由 transport target 注入的 `createClients(config)` facade。
- user-owned passthrough 文件，例如 `client.ts`、`transport.ts`、`factory.ts`。

`base_url` / `base_url_expr` 由生成的 HTTP transport facade 拥有，不进入 route/runtime client。`base_url_expr` 会原样写入生成代码，适合 Vite、Next.js 等运行时配置；它与 `base_url` 互斥。

`STREAM` / `CHANNEL` 会生成 `ApiStreamBridge<Recv, Close>` 与 `ApiChannelBridge<Recv, Send, Close>`。单消息方向直接使用模型类型；多消息方向生成判别联合类型，例如 `{ type: "progress"; data: TaskProgress }`。HTTP transport 的 stream bridge 使用 SSE，channel bridge 使用内部 envelope 的 WebSocket 来区分普通消息与 close lifecycle payload；Wails transport 使用 generated runtime events，但事件名不暴露给业务 client。

Markdown Binary Schema helper 是 route-local 的 `gen_binary.ts` 实现文件，并通过 `types.ts` re-export。route client 从 route types surface 使用 packet helper。

## Kotlin Android

```sh
api-gen generate -c api-blueprint.toml --target kotlin.client
```

Kotlin target 输出 OkHttp + kotlinx.serialization Android 客户端。

Kotlin 输出为 package-first layout，route 目录完整镜像真实 route path：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

Kotlin 生成器拥有文件统一命名为 `Gen*.kt`，例如 `routes/api/demo/GenDemoApi.kt` 和 `runtime/GenApiClient.kt`，并带 generated header。非 `Gen*` façade 文件，例如 `DemoApi.kt`、`runtime/ApiClient.kt`、`transports/http/HttpApiClient.kt`，是保留的用户扩展点。

Route DTO 输出为 `<Group>Types.kt`。Markdown Binary Schema helper 是 `BinaryTypes.kt` 中的 route-local packet / wire helper 类型，与 route API 位于同一 package。

Kotlin 通过 transport abstraction 生成 `rpc`、WS 兼容、`stream`、`channel` route surface，支持 query/json/form/binary/open request kind，并支持 `none` / `code_message_data` / `ok_data_error` response envelope。内置 OkHttp adapter 以 RPC 为主；长连接 bridge 属于 preview/custom transport surface，建议先用 `api-gen check` 和目标平台 smoke 验证后再接入生产调用路径。

`base_url` / `base_url_expr` 会写入生成的 `transports/http/HttpApiConfig.kt` 默认值，不进入 transport-neutral runtime client。

### Kotlin 兼容性说明

使用较早 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 布局的项目，重生成后应改为导入 `<package>.<root>.runtime`、`<package>.<root>.routes...` 与 `<package>.<root>.transports.http` 下的类型。

## Java Client / Server

```sh
api-gen generate -c api-blueprint.toml --target http.java
```

Java target 按 preview 口径使用。`java-client` 使用 Java 17 `java.net.http.HttpClient` + Jackson；`java-server` 使用 Spring MVC + Jackson。生成源码不包含 Gradle/Maven 工程结构，`out_dir` 是 package root，不会追加 `src/main/java`。仓库示例提供 `make example-java-suite`，可运行真实 Spring Boot server 与 generated Java client 的核心 round-trip。

Java client/server 都采用 package-first layout，route 目录完整镜像真实 route path：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

Route DTO 输出为 `<Group>Types.java`。Markdown Binary Schema bridge 也收束到 route types 容器中，例如 `BinaryTypes.DemoPacket` / `BinaryTypes.DemoPacketWire`。

Java client 生成 transport-neutral route surface、`ApiTransport`、默认 JDK HTTP adapter 和 `GenApiClient`。用户保留文件包括 `runtime/ApiClient.java`、`routes/<root>/<group...>/<Group>Api.java`、`transports/http/HttpApiClient.java`；其他 `Gen*.java` 与 runtime generated 文件由生成器覆盖。推荐入口是 `HttpApiClient.create(baseUrl)`，public DTO 使用 `DemoTypes.ErrorDemoQuery` / `DemoTypes.ErrorDemoResponse` 这类命名。默认 HTTP adapter 实现 RPC query/json/form/binary/binary-schema 请求，WS 兼容 surface、STREAM 和 CHANNEL 默认抛明确 unsupported。

Java server 生成 route service interface、public stub、runtime、route types 与 Spring controller。用户保留文件是 `routes/<root>/<group...>/<Group>Service.java`；`<Group>Types.java`、`<Group>ServiceStub.java`、`Gen<Group>Service.java` 与 `transports/http/<root>/<group...>/Gen<Group>Controller.java` 由生成器覆盖。RPC HTTP controller 可用，非 RPC connection route 先保留 service surface，HTTP adapter 返回明确 501。

DTO 使用 Java 17 `record`；字段带 Jackson `@JsonProperty`；enum 使用 `@JsonCreator` / `@JsonValue` 保留 wire value。`module` 只作为快捷表 alias normalize 到 `package`，不会生成 JPMS `module-info.java`。

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client 使用 `python_package_root` 作为包根，输出 async-first HTTP client：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

根目录的 `gen_client.py` / `client.py` 提供聚合 facade，推荐入口是 `async with create_client(base_url) as api`。route 方法接受 dataclass 或 mapping，默认返回 dataclass response。`routes/<root>/<group...>/gen_client.py` 是生成 route client，`routes/<root>/<group...>/gen_types.py` 是 route DTO 与 binary public export surface，`routes/<root>/<group...>/client.py` 是保留的 passthrough 入口，`transports/http/gen_client.py` 提供默认 httpx adapter。root-level route 直接生成在 `routes/<root>`。该 adapter 实现 RPC 请求；WS/STREAM/CHANNEL bridge interface 会生成，但连接 transport 需要项目自定义或后续扩展。`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。

Markdown Binary Schema codec 是 route-local 的 `gen_binary.py` 实现模块；public packet 与 writer helper 从 `gen_types.py` re-export。

## Python Server

```sh
api-gen generate -c api-blueprint.toml --target python.server
```

Python server 同样使用 `python_package_root` 作为包根，输出 route service contracts/stubs 与 FastAPI HTTP adapter scaffold：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_service.py` 是生成的 service contract，`routes/<root>/<group...>/service.py` 是用户可维护 stub 入口，`transports/http/gen_server.py` 与 `server.py` 提供 FastAPI HTTP adapter scaffold。root-level route 直接生成在 `routes/<root>`。作为 preview target，Python server 生成结果应纳入项目自己的类型检查、lint 和安装 smoke。

## examples 快照

`examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/kotlin/` 与 `examples/java/client` / `examples/java/server` 是生成快照，不是业务真源；`examples/java/suite` 是手写运行时验证项目。Go server / Go client / Wails Go contract / agent artifact 索引使用 Go-safe route package segment，Kotlin / Java / Python artifact 索引继续使用各自的 route 输出路径。需要接受预期生成变化时，使用：

```sh
make example-refresh
```
