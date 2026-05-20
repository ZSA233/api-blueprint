# 生成器说明

本文概述非 Wails、非 gRPC 的主要生成器。Wails 见 [Wails 说明](wails.md)，gRPC 见 [gRPC 说明](grpc.md)。

## 共享规划与 capability

`api-gen check`、contract / agent artifact projection 和各语言 writer 使用同一份 planner / capability metadata。生成前会统一校验 target 依赖、route kind、request kind 与 response envelope，避免 check 通过但 writer 才发现不支持的情况。

生成器状态和路径约定属于共享规划的一部分。Go server 为可用目标；Go client、Flutter、Kotlin / Java / Python target 按 preview 口径使用。Go server / Go client / Wails Go 的 contract / agent artifact path 使用 Go-safe route package segment，例如 `/api-v1` -> `api_v1`、`/admin/v1` -> `admin_v1`。Flutter / Kotlin / Java / Python artifact path 使用各自语言的 route 输出布局，例如 `routes/api/demo`。

Markdown Binary Schema 的生成名在各 target 使用同一套碰撞策略：packet 入口名保持基于 packet 的稳定命名，schema 内部的 struct / enum / bitflags / state / helper 符号按 packet name 作用域输出。归一化后生成符号相同的 packet name 会在生成阶段被拒绝。Public binary packet 字段遵循目标语言习惯：Go / Kotlin / Java / Flutter 使用导出或 camelCase 字段名，TypeScript / Python 保持贴近 JSON / wire 名的 snake_case 字段。

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

`gen_*` 文件由生成器拥有，重生成会覆盖。`impl_*` 与非 `gen_*` 文件是用户拥有扩展点，重生成时保留。Flutter 使用 Dart 风格的 `gen_*.dart` 作为 generator-owned 文件，非 `gen_` façade / extension 文件由用户拥有；Kotlin / Java 使用相同 ownership 模型，Kotlin 生成器拥有文件命名为 `Gen*.kt`，Java 生成器拥有文件命名为 `Gen*.java` 以及 runtime generated 文件，非 `Gen*` façade / extension 文件由用户拥有。

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
	stream STREAM_Events,
) error
Chat(
	ctx *CTX_Chat,
	channel CHANNEL_Chat,
) error
```

HTTP transport 中，`STREAM` 生成 SSE adapter，`CHANNEL` 生成 WebSocket adapter。Wails transport 中，两者默认由 session-scoped runtime events 承载。多消息 variant 会生成一个带 `type` discriminator 的共享 union schema；不要把不同 variant 拆成多个 transport event。`.CLOSE(Model)` 会进入 Go handler 泛型与 TypeScript `onClose` 类型；服务端业务写出和关闭统一显式传入 context：`Send(ctx, msg)`、`Close(ctx, close)`、`Abort(ctx, code, reason)`。

默认 HTTP/Wails runtime 只完整实现 `ConnectionScope.SESSION`。`APP` / `TOPIC` 会保留在 route contract 中，后续可通过自定义 connection hub / manager 实现广播或 topic 路由，不由生成器内置业务 fan-out 策略。

具名 variant union message 会生成稳定 helper，继续使用同一个 `{ type, data }` wire shape。Go server 与 Go client 会把 message union、`NewXxxMessageVariant(...)` 与 `DecodeVariant()` 放入 `gen_messages.go`；消息关键帧放在 `gen_message_cases.go`：`XxxMessageProcessor[C]`、`VisitXxxMessage(ctx, message, processor)`、`XxxMessageVariantCase.Decode()` 以及 `AsXxxMessageError(...)` / `IsXxxMessageErrorKind(...)` 等 typed error helper。visitor 只处理单条消息，不接管 `Recv` loop、middleware、close/abort、写出通道或错误策略；这些运行时决策由用户在自己的 route/app 层实现。

TypeScript、Flutter、Python、Kotlin、Java 使用各自语言习惯的轻量 helper，而不是照搬 Go visitor 形态。TypeScript 生成 `XxxMessageVariants.variant(data)`、`dispatchXxxMessage(message, handlers)` 与 unknown message typed dispatch error。Flutter 生成 Dart 3 `sealed class XxxMessage`、variant final class、`XxxMessageVariants.variant(data)` 与 `dispatchXxxMessage(...)`。Python client/server 的 route `gen_types.py` 生成 dataclass `XxxMessage`、`XxxMessageVariants`、`XxxMessageHandlers`、`dispatch_xxx_message(...)` 与 `XxxMessageDispatchError`。Kotlin 生成 `@Serializable data class XxxMessage(type, data)`、`object XxxMessageVariants`、`XxxMessageHandlers<R>`、`dispatchXxxMessage(...)` 与 `XxxMessageDispatchException`，runtime 暴露 `ApiJson` 供生成 helper 编解码。Java 在 route `<Group>Types.java` 中生成 nested `record XxxMessage(String type, JsonNode data)`、variants、handlers、dispatch 与 dispatch exception，并通过 `ApiJson.MAPPER` 共享 Jackson。它们适合构造 `CHANNEL` client message 和分发 server push，但仍不实现宿主应用的连接会话引擎。

Go server 还会为每个带具名 client message 的 `CHANNEL` 首次生成一组三个用户拥有的 scaffold 文件：`<leaf>_session.go`、`<leaf>_processor.go`、`<leaf>_error.go`。它们不带 `Code generated` 标记，后续生成时只在文件缺失时补齐，不覆盖用户修改。默认壳把 route handler、`Recv` loop、`VisitXxxMessage(...)`、`OnXxx` processor 和 message error policy 分到稳定落点，方便人和 AI agent 增量维护；但它仍只是可编辑起点，不是生成器拥有的 session engine，也不绑定具体 appkit、hub、middleware 或 close policy。

默认生成的非 scaffold 连接 handler 仍保持 `not implemented`，避免把示例业务逻辑写进所有用户项目。仓库示例在用户拥有的 `examples/golang/server/views/routes/api/demo/impl.go` 中展示 `STREAM` 的 `Open()`、message constructor、context-aware `Send(...)` 与 typed `Close(...)`；`CHANNEL` 示例落在 `assistant_session_session.go`、`assistant_session_processor.go` 和 `assistant_session_error.go`，processor 中的 `OnXxx` 方法通过 scaffold scope 使用 `Context`、route `CTX_*` 和 channel。

### Typed errors

ContractGraph 会把 `Blueprint(errors=...)` 和 route `.ERR(...)` 声明收集成语言无关 typed errors。Manifest `2.0` 保留全局 `errors` 完整定义表，并把 compact route-local refs（`id/group/key/code/message/toast`）写入 `routes[].errors`，因此生成客户端和 `api-gen inspect errors --route ...` 都能从该 route 看到可抛错误。`id` 是公开协议错误身份，`code` 只是业务码，可跨 group 或 route 复用。`ResponseEnvelope` 决定 wire shape：默认 `CodeMessageDataEnvelope` 使用 `{ code, message, data, error? }`，严格 `{ code, message, data }` 形态可选 `LegacyCodeMessageDataEnvelope`，显式选择 `OkDataErrorEnvelope` 才使用 `{ ok, data/error }`。

生成 runtime API 使用更贴近业务侧的 `ApiError`、`ApiErrors`、`ApiErrorsByID`、`lookupApiError`、`isApiError` 等命名；catalog 字典只是内部索引，不是主要用户入口。默认 Go、TypeScript、Flutter、Python、Kotlin、Java client transport 会按 route 的 envelope spec 解包，按 `id`、`(route_id, code)`、global code fallback 的顺序还原 payload，并抛出或返回 typed `ApiError`。Go server 在 `runtime/errors/common_err` 等分组包下生成 typed `ApiError` 值；`WithToast(...)` 返回不可变覆盖副本，适合按请求语言、租户或灰度返回动态 `toast.text`。业务 i18n 系统按 toast key 解析请求语言，客户端 helper 按 `toast.text`、外部 i18n、`toast.default`、`message` 的优先级得到展示文案。HTTP status 保持传输状态，不从业务错误码推导。

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

仓库的 `/api/demo/error-demo` 示例和 Go / TypeScript / Kotlin / Flutter / Python / Java 验证覆盖了 declared error、route-local error、动态 `toast.text` 和未声明错误码 fallback。

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

`gen_*.go` 文件由生成器拥有并覆盖；`client.go` façade 由用户拥有并保留。推荐入口是 `apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})`，然后调用 `api.Demo.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "token"})` 这类 route 方法。route/runtime client 只依赖 transport abstraction，`base_url` / `base_url_expr` 只写入 HTTP transport config。默认 HTTP adapter 实现 RPC 的 query/json/form/binary 请求；STREAM 和 CHANNEL 方法也会生成，默认 HTTP adapter 返回明确 unsupported error，项目可以替换自定义 transport。

## TypeScript

```sh
api-gen generate -c api-blueprint.toml --target typescript.client
```

TypeScript client target 输出：

- `types.ts` / `gen_types.ts`。
- request client class。
- transport-neutral `ApiClientConfig`。
- 由 transport target 注入的 `createClients(config)` facade。
- `api/transports/clients` 聚合入口；同时生成多个 transport 时会导出共同 client 子集 `CommonGeneratedClients` 与 `createClientsForTransport({ transport })`。
- user-owned passthrough 文件，例如 `client.ts`、`transport.ts`、`factory.ts`。

`base_url` / `base_url_expr` 由生成的 HTTP transport facade 拥有，不进入 route/runtime client。`base_url_expr` 会原样写入生成代码，适合 Vite、Next.js 等运行时配置；它与 `base_url` 互斥。

`STREAM` / `CHANNEL` 会生成 `ApiStreamBridge<Recv, Close>` 与 `ApiChannelBridge<Recv, Send, Close>`。单消息方向直接使用模型类型；多消息方向生成判别联合类型，例如 `{ type: "progress"; data: TaskProgress }`。HTTP transport 的 stream bridge 使用 SSE，channel bridge 使用内部 envelope 的 WebSocket 来区分普通消息与 close lifecycle payload；Wails transport 使用 generated runtime events，但事件名不暴露给业务 client。

Markdown Binary Schema helper 是 route-local 的 `gen_binary.ts` 实现文件，并通过 `types.ts` re-export。route client 从 route types surface 使用 packet helper。

## Flutter Client

```sh
api-gen generate -c api-blueprint.toml --target flutter.client
```

Flutter client target 输出纯 Dart package，可被 Flutter Android/iOS app 直接依赖，但生成物本身不生成 Flutter UI、app lifecycle、状态管理、鉴权、重试、缓存或 session engine。

典型输出目录如下：

- `lib/<package>.dart`
- `lib/src/<root>/<root>.dart`
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

`gen_*.dart` 文件由生成器覆盖；`api_client.dart`、`api_json_codecs.dart`、`http_api_client.dart`、route façade、types façade 和 `binary.dart` 只在缺失时创建，之后由用户维护。`ApiJsonCodec<T>` 注册点保留在 `api_json_codecs.dart`，用于接入项目自己的 `build_runner` codec 或手写 codec；没有 override 时走生成器的 manual `fromJson` / `toJson`。

运行时入口包括 `ApiClient` 聚合 facade、route client（例如 `DemoApi`）、DTO `fromJson` / `toJson`、`ApiError`、`lookupApiError`、`ApiTransport`、`ApiStreamBridge`、`ApiChannelBridge` 和 binary `Uint8List` codec。默认 HTTP transport 使用 `package:http` 处理 RPC query/json/form/binary 请求，STREAM bridge 使用 SSE，CHANNEL bridge 使用 `web_socket_channel`。`base_url` / `base_url_expr` 写入 HTTP config，不进入 route/runtime client。

Markdown Binary Schema helper 是 route-local 的 `gen_binary.dart`，共享二进制 reader/writer runtime 位于 `runtime/binary/gen_binary_runtime.dart`。Dart 公开字段使用 lowerCamelCase，诊断路径仍保留 schema 原始字段名。

## Kotlin Client / Server

Kotlin target 仍按 preview 口径使用，并用 kotlinx.serialization 承载 DTO、typed error 和消息关键帧 helper。`kotlin-client` 侧重 OkHttp client；`kotlin-server` 侧重 Ktor HTTP RPC adapter 与 service scaffold。

### Kotlin Client

```sh
api-gen generate -c api-blueprint.toml --target kotlin.client
```

Kotlin client target 输出 OkHttp + kotlinx.serialization 客户端。

Kotlin 输出为 package-first layout，route 目录完整镜像真实 route path：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/*`
- `<package>/<root>/transports/http/*`

Kotlin 生成器拥有文件统一命名为 `Gen*.kt`，例如 `routes/api/demo/GenDemoApi.kt` 和 `runtime/GenApiClient.kt`，并带 generated header。非 `Gen*` façade 文件，例如 `DemoApi.kt`、`runtime/ApiClient.kt`、`transports/http/HttpApiClient.kt`，是保留的用户扩展点。

Route DTO 输出为 `<Group>Types.kt`。Markdown Binary Schema helper 是 `BinaryTypes.kt` 中的 route-local packet / wire helper 类型，与 route API 位于同一 package。

Kotlin 通过 transport abstraction 生成 `rpc`、`stream`、`channel` route surface，支持 query/json/form/binary/open request kind，并支持 `none` / `code_message_data` / `ok_data_error` response envelope。内置 OkHttp adapter 覆盖 RPC query/json/form/binary 请求，`STREAM` bridge 使用 SSE，`CHANNEL` bridge 使用 OkHttp WebSocket；它只实现协议传输，不生成宿主应用的 session engine、重试、缓存或连接编排。

`base_url` / `base_url_expr` 会写入生成的 `transports/http/HttpApiConfig.kt` 默认值，不进入 transport-neutral runtime client。

### Kotlin Server

```sh
api-gen generate -c api-blueprint.toml --target kotlin.server
```

Kotlin server target 输出面向 Ktor 的 scaffold：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/<Group>Types.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Service.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>ServiceStub.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>Service.kt`
- `<package>/<root>/transports/ktor/<root>/<group...>/Gen<Group>KtorRoutes.kt`

`Gen<Group>Service.kt`、`<Group>ServiceStub.kt`、`<Group>Types.kt`、runtime `Gen*.kt` 文件与 `Gen<Group>KtorRoutes.kt` 由生成器拥有。`<Group>Service.kt` 是保留的用户文件，默认继承 generated stub。

RPC Ktor route 会 decode query/json/form/binary 输入，调用 generated service interface，并按 route response envelope 包装成功结果或 generated `ApiError`。`STREAM` route 生成 SSE bridge，`CHANNEL` route 生成 Ktor WebSocket bridge；open payload 按 query 解析，message/close/client message 使用 generated serializer。它只提供协议桥接和关键帧，不生成宿主应用的 session engine、鉴权、重试、缓存、room 管理或连接编排。

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

Route DTO 输出为 `<Group>Types.java`。Markdown Binary Schema typed packet 和 wire helper 也收束到 route types 容器中，例如 `BinaryTypes.DemoPacket` / `BinaryTypes.DemoPacketWire`。

Java client 生成 transport-neutral route surface、`ApiTransport`、默认 JDK HTTP adapter 和 `GenApiClient`。用户保留文件包括 `runtime/ApiClient.java`、`routes/<root>/<group...>/<Group>Api.java`、`transports/http/HttpApiClient.java`；其他 `Gen*.java` 与 runtime generated 文件由生成器覆盖。推荐入口是 `HttpApiClient.create(baseUrl)`，public DTO 使用 `DemoTypes.ErrorDemoQuery` / `DemoTypes.ErrorDemoResponse` 这类命名。默认 HTTP adapter 实现 RPC query/json/form/binary/binary-schema 请求，STREAM 和 CHANNEL 默认抛明确 unsupported。

Java server 生成 route service interface、public stub、runtime、route types 与 Spring controller。对于 `.REQ_BINARY(...)`，generated Spring controller 会先把请求字节解析成 generated typed packet，再调用 service。`STREAM` route 使用 Spring `SseEmitter` bridge，`CHANNEL` route 生成 WebSocket handler/config，wire shape 兼容 `{type:"message",data}` / `{type:"close",data}`。用户保留文件是 `routes/<root>/<group...>/<Group>Service.java`；`<Group>Types.java`、`<Group>ServiceStub.java`、`Gen<Group>Service.java` 与 `transports/http/<root>/<group...>/Gen<Group>Controller.java` 由生成器覆盖。连接输出只提供协议桥接，不生成宿主 session engine、鉴权、重试、缓存或 room 管理。

DTO 使用 Java 17 `record`；字段带 Jackson `@JsonProperty`；enum 使用 `@JsonCreator` / `@JsonValue` 保留 wire value。`module` 只作为快捷表 alias normalize 到 `package`，不会生成 JPMS `module-info.java`。

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client 使用 `python_package_root` 作为包根，输出 async-first HTTP client：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

根目录的 `gen_client.py` / `client.py` 提供聚合 facade，推荐入口是 `async with create_client(base_url) as api`。route 方法的 public facade 使用 typed dataclass DTO，不再把 `Mapping[str, Any]` 作为普通请求入口；需要原始 dict/body 逃生时应直接使用 transport。`routes/<root>/<group...>/gen_client.py` 是生成 route client，`routes/<root>/<group...>/gen_types.py` 是 route DTO 与 binary public export surface，`routes/<root>/<group...>/client.py` 是保留的 passthrough 入口，`runtime/gen_codecs.py` 收束共享 decode/encode helper，`transports/http/gen_client.py` 提供默认 httpx adapter。root-level route 直接生成在 `routes/<root>`。该 adapter 实现 RPC 请求；STREAM/CHANNEL bridge interface 会生成，但连接 transport 需要项目自定义或后续扩展。`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。

Python DTO 使用 `@dataclass(kw_only=True)`、Python `Enum` / `StrEnum` / `IntEnum` 和生成 codec。显式嵌套 model、数组、map、enum key/value 都会递归生成和解码，例如 response 中的 `dict[str, NestedItem]` 会还原为 `NestedItem` 实例而不是裸 dict。每个 DTO 输出 `from_mapping()`、`from_value()` 和 `to_mapping()`；缺少 required 字段、字段类型错误或 enum 值非法会抛出带字段路径的 `ValueError` / `TypeError`。字段名使用 Python-safe 属性名，JSON/query/form wire name 由 codec 保留。

Markdown Binary Schema codec 是 route-local 的 `gen_binary.py` 实现模块；public packet 与 writer helper 从 `gen_types.py` re-export。

## Python Server

```sh
api-gen generate -c api-blueprint.toml --target python.server
```

Python server 同样使用 `python_package_root` 作为包根，输出 route service contracts/stubs 与 FastAPI HTTP adapter scaffold：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

`routes/<root>/<group...>/gen_service.py` 是生成的 typed service contract，`routes/<root>/<group...>/service.py` 是用户可维护 stub 入口，`transports/http/gen_server.py` 与 `server.py` 提供 FastAPI HTTP adapter scaffold。root-level route 直接生成在 `routes/<root>`。FastAPI adapter 会把 query/json/form/open dict 递归 decode 成 route DTO 后再进入 service，并把 service 返回的 DTO/scalar/list/map 递归 encode 回 JSON；response envelope 与 typed error 包装仍由 adapter 处理。`STREAM` 生成 `StreamingResponse` SSE bridge，`CHANNEL` 生成 WebSocket bridge，message payload 与 close payload 使用 generated DTO codec；`.REQ_BINARY` 的 Python server service 边界接收原始 `bytes`，不会在 server scaffold 中生成 binary schema parser，业务实现可按项目需要解析。坏 JSON 请求会作为 transport input error 返回 HTTP 400，不进入业务 envelope。Python server WebSocket 运行时需要 `websockets` 或等价 uvicorn WebSocket backend。作为 preview target，Python server 生成结果应纳入项目自己的类型检查、lint 和安装 smoke。

## examples 快照

`examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/flutter/`、`examples/kotlin/client`、`examples/kotlin/server`、`examples/java/client` / `examples/java/server` 与 `examples/python/` 是生成快照，不是业务真源；`examples/java/suite` 是手写运行时验证项目。`examples/golang/conformance/`、`examples/typescript/conformance.ts`、`examples/kotlin/conformance/`、`examples/java/conformance/`、`examples/python/conformance/` 与 `examples/flutter/test/conformance_test.dart` 是 preserved conformance 文件，职责是调用对应语言的生成物并连接真实 Go / Java / Kotlin / Python server，验证 RPC、form、binary、typed error、命名冲突以及已支持的 SSE/WebSocket 互通；刷新生成物时不得覆盖这些文件。Go server / Go client / Wails Go contract / agent artifact 索引使用 Go-safe route package segment，Flutter / Kotlin / Java / Python artifact 索引继续使用各自的 route 输出路径。需要接受预期生成变化时，使用：

```sh
make example-refresh
```
