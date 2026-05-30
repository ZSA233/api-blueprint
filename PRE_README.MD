# API Blueprint README Fact Base

## 文档分层

`PRE_README.MD` 是 README 与用户文档收束的事实基线，不是直接面向用户的教程。它记录项目事实、文档边界和发版前文档检查项。

文档分层固定为：

- `README.md` / `README_EN.md`：首次用户入口页，只保留项目定位、安装、最小示例、目标概览和文档导航。
- `docs/zh/*` / `docs/en/*`：专题手册，承载 DSL、配置、生成器、二进制协议、Wails、gRPC、examples 验证、benchmark 等完整说明。
- `docs/release-process.md`：发布流程手册。
- `docs/plans/`：设计方案与实施记录，不作为 README 用户主路径。

README 只回答：

- 这个项目解决什么问题。
- 支持哪些生成目标。
- 如何安装。
- 如何用一个最小 Blueprint 与最小配置跑起来。
- 常用生成目标分别负责什么。
- 更详细的配置、生成器、Wails、gRPC、DSL、examples 验证、benchmark 与发布说明去哪里看。

README 不承载 changelog、设计记录、迁移说明、wire shape 细节、目录布局细节、generator ownership、provider pipeline、Wails socket bridge、gRPC target 推导、example drift 处理或单次需求的实现背景。

## README 推荐结构

1. 项目概述
2. 适合什么场景
3. 安装
4. 30 秒示例
5. 常用目标
6. 下一步文档索引
7. 开发和发布

README 必须保持简洁。新增公共能力时，README 最多增加入口级一句话或文档链接；详细事实必须先落到对应 `docs/` 专题页。

## 用户文档索引

README 应链接到以下用户文档：

- `docs/zh/getting-started.md` / `docs/en/getting-started.md`：完整快速开始。
- `docs/zh/configuration.md` / `docs/en/configuration.md`：配置文件字段说明。
- `docs/zh/blueprint-dsl.md` / `docs/en/blueprint-dsl.md`：Blueprint DSL、模型、请求、响应、错误和长连接写法。
- `docs/zh/binary-schema.md` / `docs/en/binary-schema.md`：Markdown Binary Schema、字段表、规则、生成输出与检查命令。
- `docs/zh/generators.md` / `docs/en/generators.md`：Go / TypeScript / Flutter / Swift / Kotlin / Java / Python 输出说明。
- `docs/zh/wails.md` / `docs/en/wails.md`：Wails target、overlay service、provider hook、transport bridge。
- `docs/zh/grpc.md` / `docs/en/grpc.md`：`grpc-proto`、`grpc-go`、`grpc-python` targets、proto/service 输出、工具链。
- `docs/zh/examples-validation.md` / `docs/en/examples-validation.md`：example refresh、validation 与 drift 语义。
- `docs/zh/benchmarks.md` / `docs/en/benchmarks.md`：可选 benchmark runner、binary codec benchmark、examples protocol benchmark 与趋势分析口径。
- `docs/release-process.md`：发布流程。

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 从 Blueprint 构建唯一协议真源 `ContractGraph`。
4. 通过 `api-gen check`、`api-gen inspect`、`api-gen manifest`、`api-gen diff` 和 `api-gen generate` 检查、查询、归档和生成代码。
5. 基于同一份 `ContractGraph` 输出 Go server/client、TypeScript client、Flutter client、Swift client、Kotlin client/server、Java client/server、Python client/server、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。
6. 在支持的 HTTP target 中统一表达 JSON、urlencoded、multipart、binary schema 请求体，以及 binary schema、buffered bytes、file、byte stream 等非 JSON 成功响应。

仓库事实：

- 包名：`api-blueprint`
- 对外 CLI：`api-doc-server`、`api-gen`；二者都支持 `--version` 查询当前包版本。
- GitHub-only 稳定安装入口：`git+https://github.com/zsa233/api-blueprint@stable`
- 版本真源：`release-version.toml`、`src/api_blueprint/_version.py`

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/contract/`：Blueprint -> ContractGraph 的协议 IR、manifest 与 diff。
- `src/api_blueprint/writer/`：Go / TypeScript / Flutter / Swift / Kotlin / Java / Python / Wails / gRPC proto 与 protoc-backed stub 代码生成。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/`、`examples/typescript/`、`examples/flutter/`、`examples/swift/`、`examples/kotlin/`、`examples/java/`、`examples/python/`、`examples/grpc/`、`examples/wails-*`：生成快照、preserved conformance harness、验证工程和示例 app shell。
- `scripts/example_conformance/`：examples 真实协议互通验证 CLI，按 Go / Java / Kotlin / Python server 与 Go / TypeScript / Kotlin / Flutter / Swift / Java / Python client 的能力交集执行真实互通矩阵。
- `scripts/example_benchmark/`：可选 benchmark CLI，复用 examples 与 conformance runner 评估 binary codec 和真实 server protocol 性能趋势，不作为默认 CI 阈值。
- `tests/`：单元测试、CLI 测试、codegen 测试、example 集成验证、打包与 release contract 测试。

## DSL 与契约事实

- Blueprint DSL 把 RPC、`STREAM`、`CHANNEL` 作为同一套 route contract 中的一等能力。
- `STREAM` 表示服务端持续推送，`CHANNEL` 表示双向消息通道；长连接语义通过 `OPEN`、`SERVER_MESSAGE`、`CLIENT_MESSAGE`、typed `CLOSE`、`ConnectionScope` 与 `ConnectionDelivery` 描述。
- 多消息类型必须通过单个判别联合消息契约声明，避免多个裸 event 名。
- 具名 variant 消息联合在 Go、TypeScript、Flutter、Swift、Python、Kotlin、Java 中生成构造、解码或分发关键帧 helper，并保持 `{ type, data }` wire shape；Swift 使用带 associated value 的 enum 和自定义 `Codable` codec 表达消息 union。Go server 额外为带具名 client message 的 `CHANNEL` 首次生成用户拥有的 `<leaf>_session.go` / `<leaf>_processor.go` / `<leaf>_error.go` scaffold，后续不覆盖；长连接 `Send`、`Close`、`Abort` 为 context-first API。详细使用方式放在 generators 专题文档，不写入 README 首页。
- HTTP RPC 请求体在 ContractGraph 中统一记录为 body kind：`none`、`json`、`urlencoded`、`multipart`、`binary_schema` 或 `raw_bytes`。DSL 推荐使用 `JSON(Model)` / `REQ_URLENCODED(Model)` / `REQ_MULTIPART(Model)` / `REQ_BINARY_SCHEMA(path)` 表达对应请求体；`.REQ_BINARY(path)` 保留为 binary schema 短别名，旧 `.REQ_FORM(Model)` 保留为 urlencoded 兼容入口，不再作为推荐写法。
- `FileField(content_types=..., max_size=..., description=..., omitempty=False)` 是 multipart 专用字段，只允许出现在 `REQ_MULTIPART` 绑定的 model 中。`FileField` 不允许进入 JSON、urlencoded、普通响应模型或长连接消息模型。
- 响应在 ContractGraph 中统一记录 response kind：`json`、`xml`、`text`、`binary_schema`、`bytes`、`file` 或 `byte_stream`。DSL 使用 `RSP_BINARY_SCHEMA(path)` / `RSP_BYTES(content_type=...)` / `RSP_FILE(content_type=..., default_filename=...)` / `RSP_BYTE_STREAM(content_type=...)` 表达非 JSON 成功响应；`.RSP_BINARY(path)` 是 binary schema 短别名。
- Binary schema、bytes、file、byte stream 成功响应不走 JSON response envelope；typed error 仍按既有 JSON 错误 envelope 返回，客户端继续通过 generated typed error helper 识别业务错误。
- `RSP_FILE(default_filename=...)` 记录默认下载名。Service 返回值中的 `filename` 或显式 `Content-Disposition` 会覆盖该默认值；客户端只解析实际响应头，不从 ContractGraph 默认值合成文件名。`filename=...` 保留为兼容 alias，如果与 `default_filename` 同时传入且不一致会报错。
- Markdown Binary Schema 是 HTTP 二进制请求体和 bounded 二进制成功响应的一等契约，route 使用 `.REQ_BINARY_SCHEMA(path)` 或 `.RSP_BINARY_SCHEMA(path)` 绑定 Markdown schema；在 body/response kind 中它归类为 `binary_schema`，不和 raw bytes/file/stream 概念混用。
- Binary schema metadata 可以写成裸 `key: value` 行，也可以包在 fenced code block 中改善 Markdown 渲染，两种写法解析等价。
- Binary schema 的 `content-encoding` 只约束 `.REQ_BINARY_SCHEMA(...)` 请求体。服务端按 route schema 白名单识别 HTTP `Content-Encoding`，内置 `identity` / `gzip`，`br` 等扩展编码需要宿主 runtime 注册 decoder；生成客户端默认不自动压缩请求体。
- 同一个 route group 内允许多个 binary schema；packet 入口名保持稳定，schema 内部生成符号按 packet name 作用域输出，归一化后重名的 packet name 在生成阶段报错。
- Binary schema parser / writer 诊断路径使用 schema 原始 packet、section、object 和 field 名，并在错误发生后按嵌套上下文包装路径，避免成功路径为了诊断信息提前拼接完整 path。
- Binary schema 生成的公开字段名遵循目标语言习惯：Go / Kotlin / Java / Flutter 使用导出或 camelCase 字段，TypeScript / Python 保持贴近 wire/JSON 的 snake_case 字段；诊断路径仍使用 schema 原始字段名。
- 稳定字段身份使用 `field(number, Field(...), optional=True)`，互斥选择使用 `choice="..."`，通用语义类型使用 `DateTime`、`JSONValue`、`AnyValue`。
- `operation_id` 是 RPC / `STREAM` / `CHANNEL` 的稳定 operation 命名能力；它改变 generated operation surface，不改变 route id、path 或 ContractGraph 连接语义。

## Contract 与 CLI 事实

- 公开 target kind：`contract`、`go-server`、`go-client`、`typescript-client`、`flutter-client`、`swift-client`、`kotlin-server`、`kotlin-client`、`java-server`、`java-client`、`python-server`、`python-client`、`http-transport`、`wails-transport`、`grpc-proto`、`grpc-go`、`grpc-python`。
- `api-gen check` 与 writer 共享 planner / capability metadata，生成前校验 target dependency、route kind、request kind、response kind 与 response envelope。multipart/raw media 与 binary schema response 支持 Go server/client、TypeScript client、Flutter client、Swift client、Kotlin client/server、Java client/server、Python server/client。Wails/gRPC 不投影 HTTP raw media route；遇到 HTTP multipart、Content-Disposition、HTTP status/header、MIME download 或 HTTP byte stream 语义时必须给出明确 unsupported contract 错误，并指向 Wails RPC descriptor/STREAM chunks 或 protobuf bytes/streaming chunks 等协议原生建模方式。
- `api-gen inspect routes/route/files/schema/binary-schema/errors` 是人类和 AI agent 查询 ContractGraph 的主入口；应优先按需查询，而不是先读生成物、完整 manifest 或 shards。
- 默认 contract target 生成轻量 `api-blueprint.index.json`；完整 JSON manifest、agent manifest、Markdown agent guide、contract shards 和 diff 通过显式命令或 formats/profile 生成。
- `manifest.version` 是 manifest schema 兼容版本；`manifest.generator.version` 来自包版本真源。

## Typed Error 与 Response Envelope 事实

- ContractGraph 从 `Blueprint(errors=...)` 和 route `.ERR(...)` 收集语言无关 typed errors。
- 全局 `errors` 保留完整定义表，`routes[].errors` 输出 route-oriented refs：`id/group/key/code/message/toast`。
- `id` 是公开协议错误身份，`code` 是业务码，可跨 group/route 复用；HTTP status 与业务 code 解耦。
- `ResponseEnvelope` 决定外部响应结构；默认 `CodeMessageDataEnvelope` 是 `{ code, message, data, error? }` 形态，`LegacyCodeMessageDataEnvelope` 保留严格 `{ code, message, data }` 形态，`OkDataErrorEnvelope` 显式选择 `{ ok, data/error }` 形态。
- 生成物公开错误 API 使用 `ApiError`、`ApiErrors`、`lookupApiError` / 语言惯用变体；Java 生成器拥有的错误类型按 ownership 规则使用 `GenApiError`、`GenApiErrors`、`GenApiErrorPayload` 等 `Gen*` 名称。catalog 字典不是用户主入口。
- 默认 Go / TypeScript / Flutter / Swift / Python / Kotlin / Java client transport 会按 envelope spec 自动还原 typed error，lookup 顺序为 `id`、`(route_id, code)`、global code fallback、unknown typed error；Java 返回 `GenApiError`。

## 生成器事实

- 生成物 ownership 必须在 docs 中按长期规则描述：生成器会覆盖的源码文件必须命名为 `gen_*` / `Gen*`，或位于 `_gen_*` 目录，并保留 `Code generated ... DO NOT EDIT` header；Swift `Package.swift` 这类由 target/module 列表决定的 manifest 可作为 generated manifest 管理。非 `gen_` / 非 `Gen` 的 facade、impl、service、client 扩展点只在缺失时创建，不能带 generated header。
- 生成器输出必须保持可读且低噪音：generated source 不应带尾随空白、EOF 空白行、连续 3 个以上空行，TypeScript route request block 不应因可选字段分支留下空洞。
- HTTP / Wails client 的普通 RPC route 必须暴露 per-call request options：调用方可以按单次请求传入 header 和 timeout；全局 default header / timeout 放在对应 HTTP transport config。Go timeout 继续使用 `context.Context`，并通过 variadic request option 补充 per-call header；gRPC timeout/header 使用各语言 gRPC 原生 deadline、metadata 和 call options，不由 `grpc-proto` 生成额外 client wrapper。
- 默认 client/server adapter 是协议落地和开发验证入口，不是完整生产运行时。生产项目应优先使用窄入口导入具体 route client、具体 HTTP/Wails factory、具体 server group router，并通过 preserved facade、custom transport、原生 HTTP/gRPC client、service implementation、middleware/plugin/filter 或 Wails app shell 承载鉴权、限流、cookie、TLS/proxy、重试、连接编排、权限和文件系统策略。`include` / `exclude` 是跨端稳定的生成期裁剪边界；不 import、不引用或只链接窄 product 属于各语言工具链优化，不作为结构体级 dead-strip 的统一协议承诺。
- HTTP server adapter 带安全默认上限并允许宿主放宽：Go `httptransport.ServerConfig` 默认 request body `16 MiB`、multipart memory `8 MiB`、single file `32 MiB`、decompressed binary `16 MiB`，WebSocket 默认同源校验并禁用 compression；Java Spring `GenSpringServerConfig` 默认 SSE timeout `30s`、WebSocket allowed origins 为空、inbound queue `256`、multipart single file `32 MiB`；Kotlin `ApiServerConfig` 默认 multipart file `32 MiB`、binary body `16 MiB`、WebSocket message `1 MiB`；Python `ApiServerConfig` 默认 body `16 MiB`、multipart file/part `32 MiB`、SSE queue `256`、WebSocket message `1 MiB`。
- Multipart file part runtime 优先支持 stream/file descriptor 路径，并保留 bytes helper 供小文件和测试使用。Java 使用 `GenApiFilePart` 的 `InputStream`/`Path`/bytes 形态，Kotlin 使用 `ApiFilePart.fromPath/fromBytes`，Flutter 使用 `ApiFilePart.fromStream/fromBytes`，Python multipart client 可传 bytes、path-like、file-like 或带 filename/content_type 的 tuple/dict；大文件场景不应依赖 `readAllBytes()` 便利方法。
- Java client route 会构造带嵌套 body/response spec 的 `GenApiRequest`；Python client route 会构造 `ApiRequest` dataclass。自定义 transport 应从 request object 读取 body kind、response kind、media type、binary decoder、envelope、headers 和 timeout，不应依赖持续膨胀的位置参数签名。
- Go server 的 HTTP-only route metadata 收束在 `RouteInfo.HTTP`；Java Spring、Kotlin Ktor 与 Python FastAPI server 在 generated HTTP adapter 内使用 route-local `HttpRouteInfo`。Binary `Content-Encoding` 白名单、manual/raw response 标记、response media type 与 file 默认下载名都应从 route metadata 读取，不作为散落 helper 参数继续传递。
- Go / Wails Go 生成物的 root/group 目录、Go import path 和 `package` 声明使用 Go-safe route package segment；URL、route path、selection/filter 语义不受影响。
- Go server 的 `out_dir` 是生成包根；route/provider/transport/error/binary runtime 按生成器布局输出，不隐式追加 `views`。Go HTTP server 支持 urlencoded、multipart、binary_schema 请求和 binary_schema/bytes/file/byte_stream 成功响应，raw 响应通过 generated provider/adapter contract 输出，不再依赖 `HTTP_RAW_RESPONSE()`。
- Go client 输出 runtime、routes、transports/http、根 facade；推荐从 `apiclient.NewHTTP(...)` 进入。Go HTTP client 支持 multipart file upload，`runtime.MultipartFile.Reader` 会以流式 multipart body 发送，binary_schema 成功响应返回 typed packet，bytes/file raw 响应返回 `RawResponse`，byte stream 以真流式 `StreamResponse` 返回并由调用方关闭。
- TypeScript client 输出 runtime、routes、transports，并通过 transport facade 注入 HTTP/Wails 能力。TypeScript HTTP client 支持 `ApiFilePart` multipart 输入、binary_schema 成功响应 typed packet 解码、`ApiRawResponse<T>` raw 响应，以及 `json/text/blob/arrayBuffer/stream` response type 分支。
- Flutter client 输出纯 Dart package：public entry `lib/<package>.dart` / `lib/<root>.dart` 和 `lib/src/<root>/<root>.dart` 是 preserved facade 且导出对应 `gen_*.dart`；实现位于 `lib/src/<root>/runtime`、`routes` 与 `transports/http`；`gen_*.dart` 由生成器覆盖，非 `gen_` facade、HTTP client facade 与 `api_json_codecs.dart` 作为 preserved scaffold 保留。默认 HTTP adapter 使用 `package:http`，支持 multipart、binary_schema 请求、binary_schema/bytes/file 成功响应，并把 byte_stream 作为 `ApiStreamResponse.body: Stream<List<int>>` 真流式返回；STREAM 使用 SSE，CHANNEL 使用 `web_socket_channel`，不生成 Flutter UI、状态管理、鉴权、重试、缓存或 session engine。
- Swift client 输出 Swift Package Manager SDK：`Package.swift` 是 generated manifest，会按当前 roots 重写 aggregate/runtime/root target 列表；package/root/route facade、types facade、`APICoding.swift` 与 `HTTPAPIClient.swift` 是 preserved 用户文件。Swift 的 `package` 是 SwiftPM package identity，`module` 是可选 Swift module stem（省略时默认等于 `package`）；生成布局使用一个 `<module>` aggregate module、一个 `<module>Runtime` 共享 runtime module，并为每个 blueprint root 生成独立 `<module><Root>Routes` module，避免 `/runtime` root 与 shared runtime 撞名。runtime 暴露 `APITransport`、`APIRequestOptions`、`APIRequest<Response>`、typed error lookup、raw response、stream/channel bridge、`APIFilePart`、`APIBinaryPayload`、`APIJSONValue`、`APICodingConfig`、`HTTPAPIConfig`、`APIBinaryReader`、`APIBinaryWriter` 和 URLSession HTTP transport；root routes module 只包含 root client、route client、route-local DTO 与 binary schema helper。DTO 使用 `public struct ...: Codable, Sendable`，wire 字段名通过 `CodingKeys` 保留，multi-variant STREAM/CHANNEL message 使用 associated-value enum 和自定义 codec；Markdown Binary Schema 生成 route-local 字段级 packet struct、value constants 和 encode/decode codec，并校验 const、range、sizeof、assert、reserved bytes/bits 等协议规则。默认 URLSession transport 覆盖 RPC、multipart/raw/binary response、SSE STREAM 和 WebSocket CHANNEL 协议桥接；URL 构造、header/multipart 校验和 payload limit 失败会抛出 `APITransportError`，byte stream 按 chunk 输出，SSE / WebSocket bridge 使用有限 buffer；连接重试、鉴权刷新、复杂 backpressure 和 session owner 仍由宿主应用实现。`HTTPAPIConfig` 可注入 base URL、headers、timeout、`URLSession`、JSON coding factory 和 body/stream/payload limit；默认 `runtime_profile = "modern"` 输出 `.iOS(.v15)` 并使用现代 `URLSession` async API；显式 `runtime_profile = "ios14-compat"` 输出 `.iOS(.v14)` 且只替换 HTTP transport 为 continuation/delegate 兼容实现，不改变 DTO、route、wire shape 或 typed error contract。Swift target 只生成协议 SDK，不生成 UI、鉴权、签名、401 处理、环境选择、缓存、重试、token storage、session owner 或 singleton app state；iOS 新架构应在 Core Networking 下包装或注入 generated `APITransport`，由应用自己的 `APIClient` 负责这些策略。
- Flutter 采用 Dart package 输出布局；Swift 采用 Swift Package Manager 输出布局；Kotlin / Java / Python 采用各自语言的 package-first 输出布局；这些 target 按 preview 口径描述，文档应要求使用方把生成结果纳入自身类型检查、lint、编译或 smoke。
- Kotlin client 使用 OkHttp + kotlinx.serialization，生成器拥有文件统一命名为 `Gen*.kt`，但 Kotlin public declaration 保持惯用名称；默认 HTTP adapter 覆盖 RPC query/json/urlencoded/multipart/binary_schema 请求、binary_schema/bytes/file 成功响应，并把 byte_stream 作为 closeable `ApiStreamResponse` / `InputStream` 真流式返回；Kotlin server 使用 Ktor + kotlinx.serialization，生成 service contract/stub、HTTP RPC adapter、raw streaming writer、SSE stream bridge、WebSocket channel bridge 和协议关键帧 helper。Kotlin server 不生成宿主 session engine、重试、鉴权、缓存或 room 管理。
- Java client 使用 Java 17 `HttpClient` + Jackson，Java server 使用 Spring MVC + Jackson；所有生成器覆盖的 runtime、route type、service stub 和 binary body public 类型都使用 `Gen*` 名称，例如 `GenApiTypes`、`GenDemoTypes`、`GenDemoServiceStub`；HTTP adapter 支持 query/json/urlencoded/multipart/binary_schema 请求、binary_schema/bytes/file 成功响应，并把 byte_stream 作为 `GenApiStreamResponse` / `InputStream` / `AutoCloseable` 真流式返回；binary schema 会生成 typed packet writer / parser，server controller 会把 `.REQ_BINARY_SCHEMA` body 解析为 typed packet 后交给 service；Spring server adapter 生成 `SseEmitter` stream bridge 与 WebSocket channel bridge，但不生成 Gradle/Maven 工程或 JPMS `module-info.java`。
- Python client 是 async-first，推荐从 `create_client(base_url)` 聚合 facade 进入；route DTO 使用递归强类型 `dataclass(kw_only=True)`、enum 和生成的 `from_mapping()` / `from_value()` / `to_mapping()` codec，通用 decode/encode helper 收束在 runtime `gen_codecs.py`，普通 route facade 使用 typed DTO 入参和 typed DTO/scalar/list/map 返回，raw mapping 逃生口保留在 transport 层。Python HTTP client 支持 multipart file upload，binary_schema 成功响应返回 typed packet，bytes/file raw 响应返回 `ApiRawResponse[bytes]`，byte stream 返回 async stream response context 并由调用方关闭。Python server 输出 typed service contract/stub 与 FastAPI HTTP adapter scaffold，包含 RPC/urlencoded/multipart/binary_schema、typed error、SSE 和 WebSocket 协议桥接；Python server multipart route 使用 FastAPI `UploadFile` / `Form` 组装 typed DTO，`.REQ_BINARY_SCHEMA` 请求由 adapter 解码 Content-Encoding 后解析成 typed packet，binary_schema 成功响应由 adapter 编码 typed packet，raw 响应使用 `Response`、`FileResponse` 或 `StreamingResponse`；坏 JSON 属于 transport input error 并返回 HTTP 400；运行 WebSocket server 需要安装 `websockets` 或等价 uvicorn WebSocket 后端。
- Wails target 保持 Go + TypeScript only；`frontend_mode = "external"` 只生成 API artifacts，外部 frontend 需要加载 Wails runtime。Wails 的同类能力通过普通 RPC 可序列化 payload、app-local file descriptor、STREAM/CHANNEL chunk 或 app-managed temp file/cache 建模，不模拟 HTTP response。
- gRPC proto 可由 `grpc-proto` target 从 ContractGraph 输出；`grpc-go` / `grpc-python` 可消费同配置内的 `grpc-proto`，也可直接编译手写 proto。gRPC 的同类能力通过 protobuf `bytes` 字段、typed packet payload 或 client/server streaming chunk message 建模，不继承 HTTP multipart、Content-Disposition、HTTP header/status 或 MIME download 语义。

## Examples 与验证事实

- `examples/blueprints/` 是 Blueprint 真源。
- 语言 examples、`examples/api-blueprint.index.json`、可选 full contract/agent/shards 快照与 `examples/grpc/{protos,go,python}/` 是生成快照；`examples/flutter/` 是纯 Dart package 快照，验证使用 `dart pub get`、`dart analyze` 和 `dart test`；`examples/swift/` 是 Swift Package Manager SDK 快照，验证使用文件/snippet 检查，并在 Swift toolchain 可用时运行 `swift build` 与 Swift conformance harness。
- examples DSL 覆盖 query/json/urlencoded/multipart、binary_schema、bytes/file/byte_stream raw response、request options header/timeout、media filename edge、raw media typed error、XML、static/no-envelope、header、scalar、enum、map、deprecated、typed error、命名冲突、多 blueprint root、stream、channel、SSE/WebSocket 等公开协议场景；暂不支持的端侧能力必须在 conformance manifest 中显式标注，不静默漏测。
- `scripts/example_validation.py` 负责 snapshot drift、refresh、compile/analyze/import smoke 和旧增强 suite；`python -m scripts.example_conformance` 负责真实互通验证，Makefile 通过 `make example-conformance-*` 暴露同一能力，并用 `EXAMPLE_CONFORMANCE_SERVERS`、`EXAMPLE_CONFORMANCE_CLIENTS`、`EXAMPLE_CONFORMANCE_SCENARIOS`、`EXAMPLE_CONFORMANCE_KEEP_WORKSPACE` 选择矩阵。默认服务端矩阵仍建议从 `go` 开始，完整矩阵可设置 `EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all`。
- conformance 当前服务端覆盖 Go HTTP、Java Spring、Kotlin Ktor 和 Python FastAPI；客户端覆盖 Go、TypeScript、Kotlin、Flutter、Swift、Java 和 Python。Swift harness 覆盖 HTTP RPC、urlencoded、multipart media、binary_schema、raw bytes/file/byte_stream、request options、typed error、命名冲突、多 root、SSE、WebSocket 和单模型 channel 场景。runner 按 server/client/scenario 的能力交集执行；Java/Python client 对暂不支持的 SSE/WebSocket 默认 transport 走显式 unsupported-contract，不能静默漏测。
- conformance 输出默认采用 stage summary：生成、snapshot、编译、server 启动输出一行状态，client 作为分组标题；每个 client 先输出 `client/setup` 表示正在冷启动或准备测试执行环境，再逐个执行 `client/scenario` 并在该项完成时立即输出结果。状态文本在 TTY 下自动着色，支持 `FORCE_COLOR=1` 与 `NO_COLOR=1`。被调用工具的详细 stdout/stderr 成功时隐藏，失败时回放到 stderr；client 场景失败时会额外回放当前 server log。
- conformance harness 位于各语言 preserved 文件中，例如 `examples/golang/conformance/`、`examples/typescript/conformance.ts`、`examples/kotlin/conformance/`、`examples/java/conformance/`、`examples/python/conformance/`、`examples/flutter/test/conformance_test.dart`、`examples/swift/Conformance/`，刷新生成物不得覆盖这些文件。
- `python -m scripts.example_benchmark` 提供可选 benchmark runner：`binary` 迁移旧 binary codec benchmark，`protocol` 复用 conformance workspace 和 server runner，对 Go / Java / Kotlin / Python server 的 `rpc-json`、`form`、`binary`、`typed-error` 做趋势压测，`sdk-smoke` 复用 conformance runner 验证 generated client SDK 的 request-options、binary-response、media 最小热路径。Makefile 暴露 `benchmark-list`、`benchmark-binary`、`example-benchmark-protocol` 与 `example-benchmark`；benchmark 只用于趋势与回归排查，不作为默认 CI 硬阈值。
- snapshot drift 表示生成结果变化，不自动等于 bug。
- `make example-golang-suite` 和 `make example-java-suite` 是手动增强验证，不进入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- generator-owned artifact 的长期逃生通道不再以旧 plan 作为用户入口；当前事实应维护在 `docs/zh|en/generators.md`、`configuration.md`、`wails.md` 与 `grpc.md` 中。用户应优先通过 preserved facade、custom transport、原生 client、codec registry、service implementation、middleware/plugin/filter、Wails app shell 或 gRPC native metadata/deadline/interceptor 绕过项目策略差异，不应编辑 `gen_*` / `Gen*` 文件。
- `main.py` 与 `debug.py` 是本地辅助脚本，不属于公共发布面。

## 文档维护规则

- 用户可见能力、CLI、配置、生成目录、安装方式或发布方式变化时，先更新本文件。
- 然后同步更新 `README.md` 与 `README_EN.md`，并保持二者标题层级、表格数量、代码块数量一致。
- 如果细节超过 README 的用户入口边界，优先新增或更新 `docs/zh/*` 与 `docs/en/*`。
- 用户文档应按长期概念组织，不按单次需求变更堆叠补丁式说明。
- 兼容、迁移、legacy 信息只放在明确的 `兼容性说明` / `Compatibility` / `Migration Notes` 段落中。
- 发布流程细节继续维护在 `docs/release-process.md`。

## 发布口径

- 默认发布路线是 direct stable；只有在用户明确要求时才走 RC。
- stable GitHub Release workflow 的正式发布 job 绑定 `production` environment，可配合 required reviewers 做人工审核。
- 发版前文档收束顺序固定为：
  - `PRE_README.MD`
  - `README.md`
  - `README_EN.md`
  - `docs/zh/*` / `docs/en/*`
- 发版前 editorial cleanup 固定检查：
  - README 是否仍像入门页，而不是专题手册。
  - docs 是否按主题结构承载细节，而不是散落单次变更说明。
  - 兼容/legacy 说明是否位于明确段落。
  - 中英文 README 与中英文 docs 对应专题是否保持结构和语义一致。
- 发布前检查主线命令：
  - `make`：输出 Makefile help，不执行安装或测试。
  - `make example-compile-check`
  - `make example-refresh`
  - `make example-validation`
  - `make example-conformance`
  - 可选手动增强：`make example-golang-suite`
  - 可选手动增强：`make example-java-suite`
  - `make release-version-show`
  - `make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-local RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]`
