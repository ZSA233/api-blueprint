# Blueprint DSL

Blueprint DSL 用 Python 描述 API 契约，包括路由分组、请求参数、请求体、响应模型、错误结构，以及与 transport 解耦的长连接消息流。

## 基本结构

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class DemoResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(DemoResponse)
```

`Blueprint(root="/api")` 定义路由根。`group("/demo")` 定义分组，最终路径为 `/api/demo/hello`。

## Root 与逻辑名称

`root` 只表示 URL 前缀。`name` 表示协议和生成身份，ContractGraph route id、service id、各语言 root package/module/directory、gRPC proto 默认路径和 Wails binding manifest 都使用它派生出的稳定 slug。

未传 `name` 时，非空 `root` 继续按原有规则作为逻辑身份来源：

```python
bp = Blueprint(root="/api")
```

上面的 route id 和生成 root 仍使用 `api`，URL 仍以 `/api` 开头。

当一个历史协议把同一个 app 的能力分散在多个顶级 URL namespace 中时，推荐显式写：

```python
bp = Blueprint(name="legacy", root="")

with bp.group("/account") as account:
    account.GET("/profile").RSP(...)

with bp.group("/room") as room:
    room.GET("/list").RSP(...)
```

这些 route 的 URL 是 `/account/profile` 和 `/room/list`，但逻辑身份同属 `legacy`，典型 route id 类似 `legacy.account.get.profile`。裸 `Blueprint(root="")` 会直接报错；rootless blueprint 必须显式提供 `name`，避免生成物身份和其他 root 发生碰撞。旧 Swift 项目如需保留 `APIRoutes` / `APIRootClient` / `api` 入口形态，可迁移为 `Blueprint(name="api", root="")`。

生成前会拒绝重复 route id、重复 HTTP method + URL、重复 Blueprint 逻辑身份，以及 root group 和 `/root` 风格 group 会落到同一 service/module surface 的碰撞。

### 兼容性说明

`Blueprint(name=...)` 是破坏性版本能力。使用 `root=""` 时，生成器不再隐式分配 `rootless` 或其他 fallback 身份；必须写出明确 `name`。如果旧项目原本依赖发布版中 `/api` root 对应的 Swift 入口，例如 `APIRoutes`、`APIRootClient` 和 aggregate `api` 属性，但实际 URL 已经改为由 group 提供顶级前缀，可以使用：

```python
bp = Blueprint(name="api", root="")
```

此时 URL 仍由 group 和 leaf 决定，例如 `/account/profile` 或 `/api/sample-action`；ContractGraph route id 和生成 root 使用 `api`，Swift 会继续生成 `APIRoutes` / `APIRootClient` / `api` 这一类布局。不要通过 Swift 专用 layout 开关修正身份漂移；各端应共享同一个 Blueprint 逻辑身份。

## Model

```python
class Item(Model):
    id = Uint64(description="id")
    name = String(description="name")
    tags = Array[String](description="tags", optional=True)
```

常用类型来自 `api_blueprint.includes`，包括 `String`、`Bool`、`Int`、`Uint64`、`Float`、`Array`、`Map` 等。
`optional=True` 表示字段可缺省；新 schema 推荐使用它，`omitempty=True` 作为兼容写法保留。
需要稳定字段身份时使用 `field(number, Type(...))`；需要表达互斥选择时使用 `field(number, Type(...), choice="group")`。这些都是通用契约语义，不绑定具体生成 target。
通用语义类型包括 `DateTime`、`JSONValue`、`AnyValue`，具体 target 可映射到自身的时间、JSON 或任意载荷表达。

`FileField(content_types=..., max_size=..., description=..., omitempty=False)` 用于 multipart 上传字段。它不是普通 JSON 字段，只能出现在 `REQ_MULTIPART(Model)` 绑定的请求 model 中；放入 JSON、urlencoded、响应模型或长连接消息模型都会在构建契约时失败。

如果某个 DTO 不直接出现在 route request/response 或 STREAM/CHANNEL message 上，但项目插件仍需要从 ContractGraph 读取它，可以显式导出：

```python
class PushPayload(Model):
    id = Int64(description="id")


bp.EXPORT_MODELS(PushPayload, domain="push")
```

`EXPORT_MODELS` 只会把 schema 写入 `schemas`，并在 manifest 的 `exported_models` 中记录 metadata；它不会创建 route，也不要求官方 target 必须生成或消费这个模型。

### legacy JSON 兼容类型

旧接口可能已经在线上返回多个 JSON shape，例如同一个字段有时是 string、有时是 array，或者 ID 字段在 Java / 旧服务实现中有时返回 string、有时返回整数。为了让这些字段进入契约，DSL 提供受限兼容类型：

```python
class LegacyRoom(Model):
    target = OneOf(String(), Array[String](), description="legacy target")
    ids = Array[OneOf(String(), Int())](description="legacy ids")
    normalized_ids = Array[LegacyStringID](description="ids normalized to string")
    room_id = LegacyStringID(alias="roomId", description="room id")
```

- `OneOf(...)` 表达非判别 JSON union，variant 按声明顺序用严格 JSON shape 匹配；它适合兼容旧字段，不推荐新接口把字段设计成多 shape。
- `CoerceString(accepts=(String, Int))` 与快捷 `LegacyStringID` 接受 string 或整数 JSON number，但业务类型仍是 string，编码时永远写 string；bool、object、array 和小数 number 会被拒绝。
- `StringOrIntAsString` 是 `LegacyStringID` 的废弃兼容 alias；新蓝图应使用 `LegacyStringID`。
- `OneOf` 可以嵌套在 `Array[...]` / `Map[...]` 中，也可以把 `Array[...]` 作为 variant。`OneOf()` 空 variant 会报错。
- `FileField` 不是 JSON 字段，不能放入 `OneOf`。如果无法把旧字段收窄到有限 shape，再退回 `JSONValue` 作为最后兜底。

## 请求与响应

```python
class CreateBody(Model):
    name = String(description="name")


class CreateResponse(Model):
    id = Uint64(description="id")


class DeleteUserMedalPath(Model):
    user = String(description="user id")
    medal = String(description="medal id")


with bp.group("/items") as views:
    views.POST("/create").JSON(CreateBody).RSP(CreateResponse)
    views.GET("/detail").ARGS(id=Uint64(description="id")).RSP(CreateResponse)
    views.DELETE("/user/{user}/{medal}").REQ_PATH(DeleteUserMedalPath).RSP_EMPTY()
```

- `ARGS(...)`：query 参数。
- `REQ_PATH(Model)`：path 参数，route path 只使用 OpenAPI 风格 `{name}` 占位符。
- `JSON(Model)`：JSON 请求体。
- `REQ_URLENCODED(Model)`：`application/x-www-form-urlencoded` 请求体；旧 `REQ_FORM(Model)` 作为兼容别名保留。
- `REQ_MULTIPART(Model)`：`multipart/form-data` 请求体，可混合普通字段和 `FileField(...)`。
- `REQ_BINARY_SCHEMA(path)`：Markdown Binary Schema 请求体；`REQ_BINARY(path)` 作为短别名保留。
- `RSP(...)`：响应模型。
- `RSP_EMPTY()`：成功时没有业务 data 的 JSON 响应；这不是 HTTP 204 / no body。使用 JSON response envelope 时，`data: null` 和 `data: {}` 都按空业务响应解码。

`REQ_PATH` 的占位符名称必须与 path model 字段 wire name 完全一致；字段只能是必填标量、enum 或 string-coerce 类型，不支持 optional、array、map、object、file、binary 或 oneof。Gin 风格 `:id` 不是 DSL 语法，请写成 `{id}`。REQ_PATH 仅支持 HTTP RPC route；ContractGraph、ir-plugin 和官方 HTTP target 会输出或生成 path 参数，Wails/gRPC 会 fail fast，避免生成不可用代码。

同一个 route 只能声明一种 body kind。ContractGraph 会把 path request 记录为 `path_model` / `path_params`，并把请求体记录为 `none`、`json`、`urlencoded`、`multipart`、`binary_schema` 或 `raw_bytes`，生成器和 `api-gen check` 都按这个统一语义判断 target 能力。

二进制 HTTP 请求体或响应体使用 `.REQ_BINARY_SCHEMA("./binary/packet.md")` 或 `.RSP_BINARY_SCHEMA("./binary/packet.md")` 引用 Markdown Binary Schema。它在 ContractGraph 中归类为 `binary_schema`，不和 raw bytes/file/stream media response 概念混用。Schema 表格格式、字段类型、规则和生成输出见 [Markdown Binary Schema](binary-schema.md)。

## Multipart 与非 JSON 响应

```python
class PreviewRequest(Model):
    image = FileField(content_types=["image/png", "image/jpeg"], description="source image")
    max_width = Uint64(description="max width", optional=True)


with bp.group("/media") as views:
    views.POST("/preview").REQ_MULTIPART(PreviewRequest).RSP_BYTES(content_type="image/jpeg")
    views.GET("/download").RSP_FILE(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", default_filename="report.xlsx")
    views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace; boundary=frame")
```

非 JSON 响应 DSL 包括：

- `RSP_BINARY_SCHEMA(path, content_type=None)`：由 Markdown Binary Schema 描述的 bounded typed binary packet；`RSP_BINARY(path)` 作为短别名保留。
- `RSP_BYTES(content_type="application/octet-stream")`：返回已缓冲的 bytes，例如 JPEG 或 frame。
- `RSP_FILE(content_type=..., default_filename=None)`：返回文件下载；service 可返回 path 或 generated file response。
- `RSP_BYTE_STREAM(content_type=...)`：返回持续字节流，例如 MJPEG 或自定义 streaming payload。

Binary schema 与 raw 成功响应不会被 JSON response envelope 包装；HTTP `content-type`、`content-disposition`、headers、download 和 streaming 语义会进入 ContractGraph manifest。业务错误仍按 route 的 typed error / JSON envelope 返回，生成客户端可以继续统一识别 `ApiError`。

`RSP_FILE(default_filename=...)` 是默认下载名，不是强制文件名。service 返回的 raw response filename 或显式 `Content-Disposition` header 会覆盖它。客户端只解析实际响应 header，不从 contract 默认值合成 filename。旧 `filename=...` 参数作为兼容 alias 保留；同时传入两个名字且值不一致会在构建契约时报错。

## Error 与 Toast

错误定义使用 `Error(code, message)`，其中 `message` 是协议级默认说明，适合日志、OpenAPI 和老客户端兜底。需要用户展示文案时使用 `Toast(key, default, level)`：DSL 只写一种默认语言，生成器只输出 key/default/level，不生成内置多语言 map。

```python
class CommonErr(Model):
    TOKEN_EXPIRE = Error(
        55555,
        "token登录态失效",
        toast=Toast(
            key="auth.token_expire",
            default="登录状态已失效，请重新登录",
            level="warning",
        ),
    )
```

不写 `toast` 时默认等价于 `key="<Group>.<KEY>"`、`default=message`、`level="error"`。响应 envelope 可按自身 `error_identity` 暴露 nested error identity 与 `toast`；客户端展示文案按 `toast.text`、业务 i18n、`toast.default`、`message` 兜底。服务端需要按请求语言、租户或灰度覆盖展示文案时，应返回不可变覆盖结果，不修改生成的全局错误值或 lookup entry。

route 可以继续追加局部错误组，生成 manifest 和 client lookup 时会把全局错误与 `.ERR(...)` 声明合并到该 route 的错误面：

```python
class DemoErr(Model):
    RATE_LIMITED = Error(
        42901,
        "请求过于频繁",
        toast=Toast(
            key="demo.rate_limited",
            default="请求过于频繁，请稍后再试",
            level="warning",
        ),
    )


with bp.group("/demo") as views:
    views.GET("/error-demo").ARGS(
        mode=String(description="ok/token/rate_limit/unknown", default="ok"),
    ).ERR(DemoErr).RSP(
        status=String(description="status"),
    )
```

完整示例见 `examples/blueprints/errors.py` 与 `examples/blueprints/api_demo.py`。生成后的客户端会在该 route 上优先按 `error.id` 匹配，再按 `(route_id, code)` 匹配；未声明错误码仍会得到可用的 `ApiError`。

## 长连接消息流

`STREAM` 与 `CHANNEL` 是长连接 DSL 入口，语义上与 RPC 并列，而不是直接暴露底层 WebSocket、SSE 或 Wails event。

- `STREAM`：服务端持续推送，客户端只订阅。
- `CHANNEL`：客户端和服务端双向收发消息。
- `OPEN(Model)`：连接建立参数，HTTP 可作为 query/init 参数，Wails 可作为 session init envelope。
- `SERVER_MESSAGE(...)`：服务端推给客户端的逻辑消息契约。
- `CLIENT_MESSAGE(...)`：客户端发给服务端的逻辑消息契约，仅 `CHANNEL` 支持。
- `CLOSE(Model)`：服务端发出的 typed close lifecycle payload；未声明时生成默认关闭模型。
- `delivery=ConnectionDelivery.ORDERED`：长连接消息交付策略；默认 `ORDERED`，只有显式高频场景才应切到 `UNORDERED`。

单消息方向直接传模型：

```python
class SweepOpen(Model):
    run_id = String(description="run id")


class TaskLog(Model):
    message = String(description="log message")


class StreamClose(Model):
    code = Int(description="logical close code")
    reason = String(description="close reason", optional=True)
    error = String(description="machine-readable error key", optional=True)


with bp.group("/runs") as views:
    views.STREAM("/logs", scope=ConnectionScope.SESSION).OPEN(SweepOpen).SERVER_MESSAGE(TaskLog).CLOSE(StreamClose)
```

多消息方向必须定义成单个判别联合消息，写法为一个 union 名称加 keyword variants：

```python
class TaskState(Model):
    status = String(description="current task state")


class TaskProgress(Model):
    current = Uint64(description="current step")
    total = Uint64(description="total steps")


with bp.group("/runs") as views:
    views.STREAM("/events", scope=ConnectionScope.SESSION, operation_id="TaskEvents").OPEN(SweepOpen).SERVER_MESSAGE(
        "TaskStreamMessage",
        state=TaskState,
        progress=TaskProgress,
        log=TaskLog,
    ).CLOSE(StreamClose)
```

TypeScript 会生成稳定的判别联合：

```ts
export type TaskStreamMessage =
    | { type: "state"; data: TaskState }
    | { type: "progress"; data: TaskProgress }
    | { type: "log"; data: TaskLog };
```

双向通道必须同时声明 `CLIENT_MESSAGE` 与 `SERVER_MESSAGE`：

```python
class UserInput(Model):
    text = String(description="user input")


class AssistantDelta(Model):
    text = String(description="assistant delta")


with bp.group("/assistant") as views:
    views.CHANNEL("/session", scope=ConnectionScope.SESSION, operation_id="AssistantSession").OPEN(SweepOpen).CLIENT_MESSAGE(UserInput).SERVER_MESSAGE(AssistantDelta).CLOSE(StreamClose)
```

API 规则：

- 不支持多个 `.SERVER_MESSAGE()` / `.CLIENT_MESSAGE()` 链式叠加，重复调用会报错。
- 不支持 `.SERVER_MESSAGE(TaskState, TaskLog)`，因为缺少稳定 discriminator value。
- `STREAM` 不允许 `.CLIENT_MESSAGE(...)`。
- `CHANNEL` 必须同时有 `.CLIENT_MESSAGE(...)` 与 `.SERVER_MESSAGE(...)`。
- `operation_id` 可用于 RPC / `STREAM` / `CHANNEL`，当生成的 handler / client / transport 名称需要稳定业务语义、而不是默认 path 推导名时应显式设置；显式值会规范化成稳定的 PascalCase 标识符，但不会压平 token 内部大小写，例如 `TaskEvents` / `taskEvents` / `task_events` 都会稳定为 `TaskEvents`。它只影响 operation-derived surface，不改变 route id、path 或连接语义。
- 如果未显式设置 `operation_id`，且同一个 group 下出现同 path 的自动命名冲突，生成器会按 method 或 connection kind 自动消歧，例如 `CurrentGet` / `CurrentPut`、`EventsStream` / `EventsChannel`。
- 如果多个 route 的显式 `operation_id` 规范化后仍然冲突，`api-gen check` / `api-gen generate` 会直接失败，并要求为冲突 route 提供唯一的 `operation_id`。
- `scope` 支持 `ConnectionScope.SESSION`、`ConnectionScope.APP` 与 `ConnectionScope.TOPIC`，transport 可按自身能力映射；默认 HTTP/Wails runtime 完整支持 `SESSION`。
- `delivery` 支持 `ConnectionDelivery.ORDERED` 与 `ConnectionDelivery.UNORDERED`；`STREAM` / `CHANNEL` 默认是 `ORDERED`。HTTP 下的 ordered 直接依赖 SSE / WebSocket 的单连接顺序，不额外叠加生成器自管的 sequence overlay；默认 Wails transport 会通过 transport-level sequence envelope 与 reorder buffer 保持“有序异步”。
- HTTP `STREAM` 映射为 SSE，HTTP `CHANNEL` 映射为 WebSocket。
- `delivery=ConnectionDelivery.UNORDERED` 主要影响 Wails route；HTTP transport 仍沿用 SSE / WebSocket 的原生顺序行为，不会主动切到另一条乱序交付路径。
- Wails `STREAM` / `CHANNEL` 映射为 session-scoped runtime events，event name 只存在于 generated transport/runtime 内部。
- `APP` / `TOPIC` 的消息 schema 仍由 blueprint 生成；广播对象、topic key、replay、权限过滤等 fan-out 策略应由自定义 connection hub / manager 实现。
- 客户端主动 `close(code, reason)` 只表达传输关闭请求；业务取消应建模为 `CLIENT_MESSAGE(cancel=...)`。

完整可生成示例见 `examples/blueprints/api_demo.py` 中的 `/api/demo/sweep-events` 与 `/api/demo/assistant-session`。

## 兼容性说明

`WS().RECV().SEND()` 已从 blueprint DSL 移除。双向 WebSocket 风格契约请使用 `CHANNEL`，服务端单向事件流请使用 `STREAM`。

## 文档输出

`api-doc-server` 会加载 `[blueprint].entrypoints`，基于 Blueprint 构建 FastAPI/OpenAPI 文档。默认 `/` 与 `/docs` 都是 api-blueprint 文档中心，会先加载轻量 route index，再按 group、tag、kind 或 route 选择打开 sliced Swagger，避免大接口集合一次性渲染完整 Swagger。

```sh
api-doc-server -c api-blueprint.toml
```

完整 `/openapi.json` 继续保留给外部 OpenAPI 工具。`STREAM` 会进入 route index，并在 HTTP 文档中按 SSE route 展示；`CHANNEL` 会进入 Protocol Catalog，但不会强行塞进标准 OpenAPI。

消息协议也有原生文档入口：

- `/docs/protocol` 是面向阅读的消息协议 UI，可按 route、group、tag、kind、direction、op、model 和字段搜索，查看 interaction、孤立 message 与 payload schema。默认 `CHANNEL` 只表达 client/server message 集合，不强行猜测请求/响应配对；如果 message metadata 中写入 `interaction` 与 `role`，内置 metadata interaction 插件会把它们组织成类似 Swagger operation 的请求/响应交互。
- `/docs/asyncapi` 是 AsyncAPI 可视化阅读页；`/docs/protocol.json` 与 `/asyncapi.json` 分别保留给机器消费和外部工具导出。
- docs center 会为 `STREAM` / `CHANNEL` 提供进入 Protocol UI / AsyncAPI UI 的入口，并保留禁用状态的 try-out 占位。真实 upstream 连接、token 处理和 frame codec 集成属于项目自有扩展，不进入默认 docs UI。

DSL `Enum[...]` 会进入 OpenAPI 标准 `enum` values，并额外输出 `x-enumNames` / `x-enum-varnames` 供 UI 或代码工具显示枚举名称；docs server 的本地 FastAPI route 会按 enum value 严格校验 query、path、form 和 body 输入。

如果 enum member 使用同一行注释，api-blueprint 会把它作为枚举值描述输出到 OpenAPI 的 `x-enumDescriptions` / `x-enum-descriptions`，并写入 contract manifest 的 `enum_values[].description`：

```python
class ActionKind(enum.IntEnum):
    CREATE = 1  # Create item
    UPDATE = 2  # Update item
```

该能力依赖源码可读性；动态创建的 enum 或只发布 `.pyc` 的环境会正常降级为仅输出名称和值。

当 `[blueprint].docs_server` 使用 `host:0` 时，启动输出会打印带真实绑定端口的 docs 或 hub URL。
