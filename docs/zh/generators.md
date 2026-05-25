# 生成器说明

本文概述非 Wails、非 gRPC 的主要生成器。Wails 见 [Wails 说明](wails.md)，gRPC 见 [gRPC 说明](grpc.md)。

## 共享规划与 capability

`api-gen check`、contract / agent artifact projection 和各语言 writer 使用同一份 planner / capability metadata。生成前会统一校验 target 依赖、route kind、request kind 与 response envelope，避免 check 通过但 writer 才发现不支持的情况。

生成器状态和路径约定属于共享规划的一部分。Go server 为可用目标；Go client、Flutter、Kotlin / Java / Python target 按 preview 口径使用。Go server / Go client / Wails Go 的 contract / agent artifact path 使用 Go-safe route package segment，例如 `/api-v1` -> `api_v1`、`/admin/v1` -> `admin_v1`。Flutter / Kotlin / Java / Python artifact path 使用各自语言的 route 输出布局，例如 `routes/api/demo`。

Markdown Binary Schema 的生成名在各 target 使用同一套碰撞策略：packet 入口名保持基于 packet 的稳定命名，schema 内部的 struct / enum / bitflags / state / helper 符号按 packet name 作用域输出。归一化后生成符号相同的 packet name 会在生成阶段被拒绝。Public binary packet 字段遵循目标语言习惯：Go / Kotlin / Java / Flutter 使用导出或 camelCase 字段名，TypeScript / Python 保持贴近 JSON / wire 名的 snake_case 字段。

HTTP body / response kind 也属于共享规划语义。请求体统一记录为 `none`、`json`、`urlencoded`、`multipart`、`binary_schema` 或 `raw_bytes`，响应统一记录为 `json`、`xml`、`text`、`binary_schema`、`bytes`、`file` 或 `byte_stream`。HTTP 生成器支持 Go server/client、TypeScript client、Flutter client、Kotlin client/server、Java client/server、Python server/client 的 multipart、raw media 响应和 binary schema 请求/响应。

### HTTP raw media 与非 HTTP transport

`multipart`、`Content-Disposition`、HTTP status/header、MIME download 和 HTTP byte stream 属于 HTTP transport 语义。Wails 和 gRPC 不会把这些 route 自动投影为伪 HTTP response；`api-gen check` 会对 HTTP raw media / binary schema body/response 给出明确 unsupported contract 错误，并在错误中指向协议原生建模方式。

gRPC 的等价能力应使用 protobuf 建模：小型 bytes 或 typed binary packet 放入 `bytes` 字段；需要保留 Markdown Binary Schema 精确 wire format 时，把 encoded packet 放入 `bytes payload`，不要自动展开成 proto fields；文件下载使用 server-streaming `FileChunk`，首包或 metadata 携带 `filename`、`content_type`、`size`、`sha256`，后续 chunk 携带 `bytes data`；文件上传使用 client-streaming `UploadChunk`；普通表单字段进入显式 request message；MJPEG 或 byte stream 使用 server-streaming chunk message，而不是 HTTP multipart boundary。

Wails 的等价能力应使用 IPC / app runtime 建模：小型 bytes 或 typed binary packet 返回 base64、number array 或项目封装的 `Uint8Array` adapter；文件下载返回 app-local file descriptor，例如 `path`、`filename`、`contentType`、`size`，由 app shell 负责 save/open dialog 和文件系统权限；byte stream 复用 `STREAM` / `CHANNEL` 分片传递 chunk 与 close payload；大文件优先走 app-managed temp file/cache。

### Client request options

生成的 client RPC 方法会按目标语言习惯暴露单次请求选项。TypeScript 与 Wails TypeScript 使用 `ApiRequestOptions` 对象，包含 `headers`、`timeoutMs` 和 HTTP 专用 `init`；Flutter / Kotlin 使用 `ApiRequestOptions(headers, timeout)`；Java 使用 `GenApiRequestOptions` overload；Python 使用 keyword-only `headers` 与 `timeout`；Go 使用 `context.Context` 表达 timeout/deadline，并通过 `runtime.WithHeader(...)` 等 variadic `runtime.RequestOption` 补充 header。

HTTP transport 会先合并 config default headers，再合并 per-call headers，最后在编码 JSON、form、multipart 或 binary body 时补充 `Content-Type` 等协议必要 header。per-call timeout 优先于 transport config timeout，再回落到 native client 默认值。`STREAM` / `CHANNEL` 的生命周期 timeout 不和普通 RPC 混用，仍由 context cancellation、close API、WebSocket/SSE runtime 或应用策略控制。

### 生产边界与窄入口

默认 HTTP/Wails adapter 是协议桥接和开发验证入口，不是完整生产运行时。它们会提供安全默认值、typed error、request options、raw response、SSE/WebSocket/Wails bridge 等协议关键帧，但鉴权、限流、cookie、TLS/proxy、重试、连接编排、文件权限、审计日志和复杂 backpressure 仍应由宿主应用通过 middleware/plugin/filter、原生 client、custom transport、service implementation 或 app shell 承载。

生产项目推荐优先导入窄入口：具体 route client、具体 HTTP/Wails factory、具体 server group router，而不是总 barrel 或 aggregate facade。聚合入口适合示例、发现能力和快速试用；窄入口更利于 tree-shaking、依赖审计和最小攻击面。

server adapter 默认启用有限资源上限，并允许宿主显式放宽：Go `httptransport.ServerConfig` 默认 request body `16 MiB`、multipart memory `8 MiB`、single file `32 MiB`、decompressed binary `16 MiB`，WebSocket 默认使用 origin 校验并禁用 compression；Java Spring `GenSpringServerConfig` 默认 SSE timeout `30s`、WebSocket allowed origins 为空、inbound queue `256`、multipart single file `32 MiB`、decompressed binary `16 MiB`；Kotlin `ApiServerConfig` 默认 multipart file `32 MiB`、binary body 与 decompressed binary body `16 MiB`、WebSocket message `1 MiB`；Python `ApiServerConfig` 默认 body 与 decompressed binary body `16 MiB`、multipart file/part `32 MiB`、SSE queue `256`、WebSocket message `1 MiB`。

multipart file part 的 runtime 表达优先支持 stream/file descriptor，bytes helper 仅适合小文件和测试。大文件路径应使用 Java `InputStream`/`Path`、Kotlin `fromPath`、Flutter `fromStream`、Python path-like/file-like 或宿主框架自己的 spool/temp file 策略，不应依赖 `readAllBytes()` 便利方法作为生产默认。

## Go

```sh
api-gen generate -c api-blueprint.toml --target go.server
```

Go 生成器输出：

- route interface 与默认 `impl.go`。
- 请求 / 响应 / 上下文结构。
- provider runtime 与 response envelope codec。
- transport-neutral Go core。
- 可选 HTTP/Gin adapter，包含 multipart bind、binary schema request 解码、binary schema response 编码与 raw bytes/file/stream response writer。

生成器会覆盖的文件必须命名为 `gen_*` / `Gen*`，或位于 `_gen_*` 目录，并保留 `Code generated ... DO NOT EDIT` header。`impl_*` 与非 `gen_` / 非 `Gen` 文件是用户拥有扩展点，只在缺失时创建，重生成时保留且不带 generated header。Flutter 使用 Dart 风格的 `gen_*.dart`；Kotlin 生成器拥有文件命名为 `Gen*.kt`，但 public declaration 名称保持 Kotlin 惯用形态；Java 生成器拥有文件与 public 类型都使用 `Gen*`。

`go-server` 只负责 Go 服务端 core。`out_dir` 就是生成包根；如果项目希望 import path 包含 `views`，应把 `views` 写进 `out_dir`。HTTP / Wails 输出由 `http-transport` / `wails-transport` target 通过 `server = "go.server"` 显式挂接。HTTP 入口生成在 `<out_dir>/transports/http/<go-root-segment>` 中，例如 `transports/http/api.NewBlueprint(engine)`。

Go route core 生成在 `<out_dir>/routes/<go-root-segment>/**`，provider runtime 生成在 `<out_dir>/providers`，transport adapter 生成在 `<out_dir>/transports/**`，typed error runtime 生成在 `<out_dir>/runtime/errors/**`。Go-safe segment 会把非 `[0-9A-Za-z_]` 转成 `_`、去首尾 `_`，数字开头补 `p_`，Go keyword 补 `_pkg`；URL、route path 和 selection/filter 语义不变，因此 Go 目录不保证逐级镜像 URL slash 层级。如果希望 import path 包含 `/views`，应显式设置 `out_dir = ".../views"`。

`providers` 是生成包根下的全局 transport-neutral runtime，不按 blueprint root 拆分。TypeScript 的 per-root `runtime` 主要服务模型和 client 命名隔离，和 Go provider hook 不是同一类职责。

需要按 root、route 或 transport 切换 provider 实现时，不要解析请求 path。生成器会在每个 route executor 构造期写入 `RouteInfo`，并把它挂到 `Context.Route` 与 `ProviderSpec.Route`。HTTP-only route 元数据收束在 `RouteInfo.HTTP` 下，例如 binary request `Content-Encoding` 白名单、`HTTP_RAW_RESPONSE()` 手写响应标记和 file response 默认下载名：

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

HTTP server adapter 生成 `transports/http/gen_config.go`，提供 `httptransport.DefaultServerConfig()`、`httptransport.SetServerConfig(config)` 与 `httptransport.ActiveServerConfig()`。默认请求体、multipart、解压后 binary 和 WebSocket origin/compression 策略按“生产安全默认”收紧；项目可以在启动期显式调用 `SetServerConfig` 放宽限制、设置 `WebSocketOriginPatterns`，或通过 `BinaryContentDecoders` 注册额外 binary request `Content-Encoding` decoder。

新 route 需要返回 bounded typed binary packet、bytes、file 或 byte stream 时，应优先使用 `RSP_BINARY_SCHEMA(...)`、`RSP_BYTES(...)`、`RSP_FILE(...)` 或 `RSP_BYTE_STREAM(...)`，让成功响应进入 ContractGraph 并被客户端生成器识别。`HTTP_RAW_RESPONSE()` 仍可作为旧项目的 HTTP adapter 逃生口，但它不是跨语言契约，不会生成 typed raw response client surface。

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

TypeScript、Flutter、Python、Kotlin、Java 使用各自语言习惯的轻量 helper，而不是照搬 Go visitor 形态。TypeScript 生成 `XxxMessageVariants.variant(data)`、`dispatchXxxMessage(message, handlers)` 与 unknown message typed dispatch error。Flutter 生成 Dart 3 `sealed class XxxMessage`、variant final class、`XxxMessageVariants.variant(data)` 与 `dispatchXxxMessage(...)`。Python client/server 的 route `gen_types.py` 生成 dataclass `XxxMessage`、`XxxMessageVariants`、`XxxMessageHandlers`、`dispatch_xxx_message(...)` 与 `XxxMessageDispatchError`。Kotlin 生成 `@Serializable data class XxxMessage(type, data)`、`object XxxMessageVariants`、`XxxMessageHandlers<R>`、`dispatchXxxMessage(...)` 与 `XxxMessageDispatchException`，runtime 暴露 `ApiJson` 供生成 helper 编解码。Java 在 route `Gen<Group>Types.java` 中生成 nested `record XxxMessage(String type, JsonNode data)`、variants、handlers、dispatch 与 dispatch exception，并通过 `GenApiJson.MAPPER` 共享 Jackson。它们适合构造 `CHANNEL` client message 和分发 server push，但仍不实现宿主应用的连接会话引擎。

Go server 还会为每个带具名 client message 的 `CHANNEL` 首次生成一组三个用户拥有的 scaffold 文件：`<leaf>_session.go`、`<leaf>_processor.go`、`<leaf>_error.go`。它们不带 `Code generated` 标记，后续生成时只在文件缺失时补齐，不覆盖用户修改。默认壳把 route handler、`Recv` loop、`VisitXxxMessage(...)`、`OnXxx` processor 和 message error policy 分到稳定落点，方便人和 AI agent 增量维护；但它仍只是可编辑起点，不是生成器拥有的 session engine，也不绑定具体 appkit、hub、middleware 或 close policy。

默认生成的非 scaffold 连接 handler 仍保持 `not implemented`，避免把示例业务逻辑写进所有用户项目。仓库示例在用户拥有的 `examples/golang/server/views/routes/api/demo/impl.go` 中展示 `STREAM` 的 `Open()`、message constructor、context-aware `Send(...)` 与 typed `Close(...)`；`CHANNEL` 示例落在 `assistant_session_session.go`、`assistant_session_processor.go` 和 `assistant_session_error.go`，processor 中的 `OnXxx` 方法通过 scaffold scope 使用 `Context`、route `CTX_*` 和 channel。

### Typed errors

ContractGraph 会把 `Blueprint(errors=...)` 和 route `.ERR(...)` 声明收集成语言无关 typed errors。Manifest `2.0` 保留全局 `errors` 完整定义表，并把 compact route-local refs（`id/group/key/code/message/toast`）写入 `routes[].errors`，因此生成客户端和 `api-gen inspect errors --route ...` 都能从该 route 看到可抛错误。`id` 是公开协议错误身份，`code` 只是业务码，可跨 group 或 route 复用。`ResponseEnvelope` 决定 wire shape：默认 `CodeMessageDataEnvelope` 使用 `{ code, message, data, error? }`，严格 `{ code, message, data }` 形态可选 `LegacyCodeMessageDataEnvelope`，显式选择 `OkDataErrorEnvelope` 才使用 `{ ok, data/error }`。

生成 runtime API 使用更贴近业务侧的 `ApiError`、`ApiErrors`、`ApiErrorsByID`、`lookupApiError`、`isApiError` 等语言惯用命名；Java 生成器拥有的错误类型按 ownership 规则使用 `GenApiError`、`GenApiErrors`、`GenApiErrorPayload` 等 `Gen*` 名称。catalog 字典只是内部索引，不是主要用户入口。默认 Go、TypeScript、Flutter、Python、Kotlin、Java client transport 会按 route 的 envelope spec 解包，按 `id`、`(route_id, code)`、global code fallback 的顺序还原 payload，并抛出或返回 typed error；Java 返回 `GenApiError`。Go server 在 `runtime/errors/common_err` 等分组包下生成 typed `ApiError` 值；`WithToast(...)` 返回不可变覆盖副本，适合按请求语言、租户或灰度返回动态 `toast.text`。业务 i18n 系统按 toast key 解析请求语言，客户端 helper 按 `toast.text`、外部 i18n、`toast.default`、`message` 的优先级得到展示文案。HTTP status 保持传输状态，不从业务错误码推导。

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

`gen_*.go` 文件由生成器拥有并覆盖；`client.go` façade 由用户拥有并保留。推荐入口是 `apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})`，然后调用 `api.Demo.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "token"}, runtime.WithHeader("X-Trace-Id", traceID))` 这类 route 方法。route/runtime client 只依赖 transport abstraction，`base_url` / `base_url_expr` 只写入 HTTP transport config。默认 HTTP adapter 实现 RPC 的 query/json/urlencoded/multipart/binary_schema 请求，multipart file 使用 `runtime.MultipartFile`；`Reader` 输入会以 streaming multipart body 发送，`Bytes` 适合小文件和测试。binary_schema 成功响应会解码成 typed packet，bytes/file raw 响应返回 `runtime.RawResponse`，byte stream 以真流式 `runtime.StreamResponse` 返回并由调用方关闭；请求 deadline 与 cancel 使用 `context.Context`，per-call request options 承载 header 和后续请求级开关；STREAM 和 CHANNEL 方法也会生成，默认 HTTP adapter 返回明确 unsupported error，项目可以替换自定义 transport。

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

HTTP transport 支持 JSON、urlencoded、multipart 和 binary_schema 请求。route RPC 方法把 `ApiRequestOptions` 作为第二个参数，用于按单次调用传入 headers、`timeoutMs` 和原生 `RequestInit`，不改变 route contract。multipart DTO 中的文件字段使用 `ApiFilePart = File | Blob | { blob: Blob; filename?: string; contentType?: string }`；binary_schema 成功响应会请求 HTTP bytes 并通过 route-local packet codec 解码。raw bytes/file 响应返回 `ApiRawResponse<Blob>` 或 `ApiRawResponse<ArrayBuffer>`，其中包含 `body`、`headers`、`status`、`contentType`、`contentDisposition`，`filename` 只从实际 `Content-Disposition` 响应头解析。client 不会根据 `RSP_FILE(default_filename=...)` contract 默认值合成文件名。byte stream route 使用 `responseType: "stream"`，具体可读流类型取决于运行环境的 Fetch API 能力。

`STREAM` / `CHANNEL` 会生成 `ApiStreamBridge<Recv, Close>` 与 `ApiChannelBridge<Recv, Send, Close>`。单消息方向直接使用模型类型；多消息方向生成判别联合类型，例如 `{ type: "progress"; data: TaskProgress }`。HTTP transport 的 stream bridge 使用 SSE，channel bridge 使用内部 envelope 的 WebSocket 来区分普通消息与 close lifecycle payload；Wails transport 使用 generated runtime events，但事件名不暴露给业务 client。

Markdown Binary Schema helper 是 route-local 的 `gen_binary.ts` 实现文件，并通过 `types.ts` re-export。route client 从 route types surface 使用 packet helper。

## Flutter Client

```sh
api-gen generate -c api-blueprint.toml --target flutter.client
```

Flutter client target 输出纯 Dart package，可被 Flutter Android/iOS app 直接依赖，但生成物本身不生成 Flutter UI、app lifecycle、状态管理、鉴权、重试、缓存或 session engine。

典型输出目录如下：

- `lib/<package>.dart`
- `lib/gen_<package>.dart`
- `lib/<root>.dart`
- `lib/gen_<root>.dart`
- `lib/src/<root>/<root>.dart`
- `lib/src/<root>/gen_<root>.dart`
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

`gen_*.dart` 文件由生成器覆盖；public entry、`api_client.dart`、`api_json_codecs.dart`、`http_api_client.dart`、route façade、types façade 和 `binary.dart` 只在缺失时创建，之后由用户维护且不带 generated header。`ApiJsonCodec<T>` 注册点保留在 `api_json_codecs.dart`，用于接入项目自己的 `build_runner` codec 或手写 codec；没有 override 时走生成器的 manual `fromJson` / `toJson`。

运行时入口包括 `ApiClient` 聚合 facade、route client（例如 `DemoApi`）、DTO `fromJson` / `toJson`、`ApiError`、`lookupApiError`、`ApiTransport`、`ApiRequestOptions`、`ApiStreamBridge`、`ApiChannelBridge` 和 binary `Uint8List` codec。默认 HTTP transport 使用 `package:http` 处理 RPC query/json/urlencoded/multipart/binary_schema 请求，应用 per-call `ApiRequestOptions.headers` 与 `ApiRequestOptions.timeout`，binary_schema 成功响应解码为 typed packet，bytes/file raw 响应返回 `ApiRawResponse<Uint8List>`，byte stream 以 `ApiStreamResponse.body: Stream<List<int>>` 真流式返回，STREAM bridge 使用 SSE，CHANNEL bridge 使用 `web_socket_channel`。raw response filename 只从实际 `Content-Disposition` header 解析。`base_url` / `base_url_expr` 写入 HTTP config，不进入 route/runtime client。

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

Kotlin 生成器拥有文件统一命名为 `Gen*.kt`，例如 `routes/api/demo/GenDemoApi.kt`、`routes/api/demo/GenDemoTypes.kt` 和 `runtime/GenApiClient.kt`，并带 generated header。非 `Gen*` façade 文件，例如 `DemoApi.kt`、`runtime/ApiClient.kt`、`transports/http/HttpApiClient.kt`，是保留的用户扩展点。

Route DTO 写入 `Gen<Group>Types.kt`，但其中 public DTO / helper declaration 名称保持不变。Markdown Binary Schema helper 是 `GenBinaryTypes.kt` 中的 route-local packet / wire helper 类型，与 route API 位于同一 package。

Kotlin 通过 transport abstraction 生成 `rpc`、`stream`、`channel` route surface，支持 query/json/urlencoded/multipart/binary_schema/open request kind，并支持 `none` / `code_message_data` / `ok_data_error` response envelope。RPC route 方法接收 `ApiRequestOptions(headers, timeout)` 做单次请求自定义。内置 OkHttp adapter 覆盖 RPC query/json/urlencoded/multipart/binary_schema 请求，应用 per-call headers 与 call timeout，binary_schema 成功响应解码为 typed packet，bytes/file raw 响应返回 `ApiRawResponse`，byte stream 以 closeable `ApiStreamResponse` / `InputStream` 真流式返回，并提供 `readChunk()` / `readAllBytes()` 便利方法；raw response filename 只从实际 `Content-Disposition` header 解析。`STREAM` bridge 使用 SSE，`CHANNEL` bridge 使用 OkHttp WebSocket；它只实现协议传输，不生成宿主应用的 session engine、重试、缓存或连接编排。

`base_url` / `base_url_expr` 会写入生成的 `transports/http/HttpApiConfig.kt` 默认值，不进入 transport-neutral runtime client。

### Kotlin Server

```sh
api-gen generate -c api-blueprint.toml --target kotlin.server
```

Kotlin server target 输出面向 Ktor 的 scaffold：

- `<package>/<root>/runtime/*`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Types.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>Service.kt`
- `<package>/<root>/routes/<root>/<group...>/Gen<Group>ServiceStub.kt`
- `<package>/<root>/routes/<root>/<group...>/<Group>Service.kt`
- `<package>/<root>/transports/ktor/<root>/<group...>/Gen<Group>KtorRoutes.kt`

`Gen<Group>Service.kt`、`Gen<Group>ServiceStub.kt`、`Gen<Group>Types.kt`、runtime `Gen*.kt` 文件与 `Gen<Group>KtorRoutes.kt` 由生成器拥有。`<Group>Service.kt` 是保留的用户文件，默认继承 generated stub。

RPC Ktor route 会 decode query/json/urlencoded/multipart/binary_schema 输入，调用 generated service interface，并按 route response envelope 包装 JSON 成功结果或 generated `ApiError`。每个 generated Ktor route 都带一个很小的 route-local HTTP metadata 值，binary `Content-Encoding` 白名单、raw response kind/media type 和 file 默认下载名由 helper 从这里读取，不再继续扩张 helper 参数列表。binary_schema 请求会校验 route schema 的 `Content-Encoding` 白名单，内置解码 `identity` / `gzip`，并可通过 `ApiServerConfig.binaryContentDecoders` 支持 `br` 等扩展编码。binary_schema、bytes、file、byte_stream 成功响应不套 JSON envelope，adapter 会输出 raw bytes、`Content-Type` 与文件下载 header；byte_stream 通过 Ktor streaming writer 分片写出。`STREAM` route 生成 SSE bridge，`CHANNEL` route 生成 Ktor WebSocket bridge；open payload 按 query 解析，message/close/client message 使用 generated serializer。`register*Routes` 接收 `ApiServerConfig`，默认限制 multipart file、binary body、decompressed binary body 和 WebSocket message 大小。它只提供协议桥接和关键帧，不生成宿主应用的 session engine、鉴权、重试、缓存、room 管理或连接编排。

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

Route DTO 输出为 `Gen<Group>Types.java`。Markdown Binary Schema typed packet 和 wire helper 也收束到 route types 容器中，例如 `GenBinaryTypes.DemoPacket` / `GenBinaryTypes.DemoPacketWire`。

Java client 生成 transport-neutral route surface、`GenApiTransport`、默认 JDK HTTP adapter 和 `GenApiClient`。用户保留文件包括 `runtime/ApiClient.java`、`routes/<root>/<group...>/<Group>Api.java`、`transports/http/HttpApiClient.java`；其他 `Gen*.java` 文件由生成器覆盖。推荐入口是 `HttpApiClient.create(baseUrl)`，public DTO 使用 `GenDemoTypes.ErrorDemoQuery` / `GenDemoTypes.ErrorDemoResponse` 这类命名。RPC route 方法提供 `GenApiRequestOptions` overload，用于 per-call headers 和 timeout。generated route client 会构造带嵌套 body/response spec 的 `GenApiRequest`，custom transport 从 request object 读取 request kind、response kind、media type、binary decoder 与 envelope 行为，不再依赖继续膨胀的 transport 方法签名。默认 HTTP adapter 实现 RPC query/json/urlencoded/multipart/binary_schema 请求，binary_schema 成功响应解码为 typed packet，bytes/file raw 响应返回 `GenApiRawResponse`，byte stream 以 `GenApiStreamResponse` / `InputStream` / `AutoCloseable` 真流式返回，并保留 `readAllBytes()` 便利方法；raw response filename 只从实际 `Content-Disposition` header 解析。STREAM 和 CHANNEL 默认抛明确 unsupported。

Java server 生成 route service interface、public stub、runtime、route types、`GenSpringServerConfig` 与 Spring controller。每个 generated controller 都带 route-local `HttpRouteInfo` metadata，用来记录 binary request encoding、raw/manual response 行为、response media type 和 file 默认下载名。对于 `.REQ_BINARY_SCHEMA(...)`，generated Spring controller 会校验 route schema 的 `Content-Encoding` 白名单，内置解码 `identity` / `gzip` 或使用注册的 `binaryContentDecoders`，再把请求字节解析成 generated typed packet 后调用 service；multipart route 会把 file part 解码为 `GenApiFilePart`；binary_schema、bytes、file、byte_stream 成功响应不套 JSON envelope，controller 会输出 raw bytes、`Content-Type` 与文件下载 header；byte_stream 通过 Spring streaming response 写出，不再强制缓冲为 byte array。`STREAM` route 使用 Spring `SseEmitter` bridge，`CHANNEL` route 生成 WebSocket handler/config，wire shape 兼容 `{type:"message",data}` / `{type:"close",data}`。`GenSpringServerConfig` 默认使用有界 WebSocket 入站队列、空 allowed origins、可替换 executor、multipart 文件上限、decompressed binary 上限和空 binary decoder registry；项目可提供自定义 bean/构造参数覆盖。用户保留文件是 `routes/<root>/<group...>/<Group>Service.java`；`Gen<Group>Types.java`、`Gen<Group>ServiceStub.java`、`Gen<Group>Service.java` 与 `transports/http/<root>/<group...>/Gen<Group>Controller.java` 由生成器覆盖。连接输出只提供协议桥接，不生成宿主 session engine、鉴权、重试、缓存或 room 管理。

DTO 使用 Java 17 `record`；字段带 Jackson `@JsonProperty`；enum 使用 `@JsonCreator` / `@JsonValue` 保留 wire value。`module` 只作为快捷表 alias normalize 到 `package`，不会生成 JPMS `module-info.java`。

## Python Client

```sh
api-gen generate -c api-blueprint.toml --target python.client
```

Python client 使用 `python_package_root` 作为包根，输出 async-first HTTP client：

- `<python_package_root>/<root>/runtime/*`
- `<python_package_root>/<root>/routes/<root>/<group...>/*`
- `<python_package_root>/<root>/transports/http/*`

根目录的 `gen_client.py` / `client.py` 提供聚合 facade，推荐入口是 `async with create_client(base_url) as api`。route 方法的 public facade 使用 typed dataclass DTO 和 keyword-only `headers` / `timeout` request options，不再把 `Mapping[str, Any]` 作为普通请求入口；需要原始 dict/body 逃生时应直接使用 transport。`routes/<root>/<group...>/gen_client.py` 是生成 route client，`routes/<root>/<group...>/gen_types.py` 是 route DTO 与 binary public export surface，`routes/<root>/<group...>/client.py` 是保留的 passthrough 入口，`runtime/gen_codecs.py` 收束共享 decode/encode helper，`transports/http/gen_client.py` 提供默认 httpx adapter。root-level route 直接生成在 `routes/<root>`。generated route client 会构造 `ApiRequest` dataclass，把 method/path、body variant、response metadata、headers 和 timeout 放在同一个请求对象中；custom transport 实现 `request(ApiRequest)`，不再依赖继续膨胀的位置参数签名。默认 httpx adapter 实现 RPC 的 JSON、urlencoded、multipart 和 binary_schema 请求；multipart 文件可传 bytes、path-like、file-like 或带 filename/content_type 的 tuple/dict，binary_schema 成功响应解码为 typed packet，bytes/file raw 响应返回 `ApiRawResponse[bytes]`，byte stream 响应返回 async context manager。raw response filename 只从实际 `Content-Disposition` header 解析。STREAM/CHANNEL bridge interface 会生成，但连接 transport 需要项目自定义或后续扩展。`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。

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

`routes/<root>/<group...>/gen_service.py` 是生成的 typed service contract，`routes/<root>/<group...>/service.py` 是用户可维护 stub 入口，`transports/http/gen_server.py` 与 `server.py` 提供 FastAPI HTTP adapter scaffold。root-level route 直接生成在 `routes/<root>`。FastAPI adapter 会把 query/json/urlencoded/multipart/open dict 递归 decode 成 route DTO 后再进入 service，multipart route 使用 `UploadFile = File(...)` 与普通字段 `Form(...)` 组装 DTO，并把 service 返回的 DTO/scalar/list/map 递归 encode 回 JSON；response envelope 与 typed error 包装仍由 adapter 处理。generated handler 引用 route-local `HttpRouteInfo`，让 binary request encoding、raw response kind/media/default filename 元数据和 route 绑定在一起，不再作为松散 helper 参数传递。binary_schema 请求会校验 route schema 的 `Content-Encoding` 白名单，内置解码 `identity` / `gzip` 或使用注册的 `binary_content_decoders`，再把解码后的 body 解析成 generated typed packet 后进入 service。binary_schema 成功响应会把 typed packet 返回值编码成 HTTP bytes。raw bytes/file/byte_stream 成功响应分别使用 `Response`、`FileResponse` 或 `StreamingResponse`，不会套 JSON envelope；typed error 仍按 JSON envelope 返回。`STREAM` 生成 `StreamingResponse` SSE bridge，`CHANNEL` 生成 WebSocket bridge，message payload 与 close payload 使用 generated DTO codec。`ApiServerConfig` 会限制 request body、decompressed binary body、multipart file/part、SSE queue 和 WebSocket message 大小；`create_<group>_router(..., config=...)` 是窄入口，`create_router(..., config=...)` 继续作为聚合入口。坏 JSON 或 binary 请求会作为 transport input error 返回 HTTP 400，不进入业务 envelope。Python server WebSocket 运行时需要 `websockets` 或等价 uvicorn WebSocket backend。作为 preview target，Python server 生成结果应纳入项目自己的类型检查、lint 和安装 smoke。

## examples 快照

`examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/flutter/`、`examples/kotlin/client`、`examples/kotlin/server`、`examples/java/client` / `examples/java/server` 与 `examples/python/` 是生成快照，不是业务真源；`examples/java/suite` 是手写运行时验证项目。`examples/golang/conformance/`、`examples/typescript/conformance.ts`、`examples/kotlin/conformance/`、`examples/java/conformance/`、`examples/python/conformance/` 与 `examples/flutter/test/conformance_test.dart` 是 preserved conformance 文件，职责是调用对应语言的生成物并连接真实 Go / Java / Kotlin / Python server，验证 RPC、urlencoded、multipart media、binary_schema、request options header/timeout、typed error、命名冲突、bytes/file/byte_stream raw response、media filename edge、raw media typed error、XML/static/header/scalar/enum/map/deprecated/audit-binary、单模型 channel 以及已支持的 SSE/WebSocket 互通；刷新生成物时不得覆盖这些文件。Go server / Go client / Wails Go contract / agent artifact 索引使用 Go-safe route package segment，Flutter / Kotlin / Java / Python artifact 索引继续使用各自的 route 输出路径。需要接受预期生成变化时，使用：

```sh
make example-refresh
```
