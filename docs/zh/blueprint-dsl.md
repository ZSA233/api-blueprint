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

## Model

```python
class Item(Model):
    id = Uint64(description="id")
    name = String(description="name")
    tags = Array[String](description="tags", optional=True)
```

常用类型来自 `api_blueprint.includes`，包括 `String`、`Bool`、`Int`、`Uint64`、`Float`、`Array`、`Map` 等。
`optional=True` 表示字段可缺省；旧的 `omitempty=True` 仍兼容，但新 DSL 推荐使用 `optional=True`。
需要稳定字段身份时使用 `field(number, Type(...))`；需要表达互斥选择时使用 `field(number, Type(...), choice="group")`。这些都是通用契约语义，不绑定具体生成 target。
通用语义类型包括 `DateTime`、`JSONValue`、`AnyValue`，具体 target 可映射到自身的时间、JSON 或任意载荷表达。

## 请求与响应

```python
class CreateBody(Model):
    name = String(description="name")


class CreateResponse(Model):
    id = Uint64(description="id")


with bp.group("/items") as views:
    views.POST("/create").JSON(CreateBody).RSP(CreateResponse)
    views.GET("/detail").ARGS(id=Uint64(description="id")).RSP(CreateResponse)
```

- `ARGS(...)`：query 参数。
- `JSON(Model)`：JSON 请求体。
- `RSP(...)`：响应模型。

二进制 HTTP 请求体使用 `.REQ_BINARY("./binary/packet.md")` 引用 Markdown Binary Schema。Schema 表格格式、字段类型、规则和生成输出见 [Markdown Binary Schema](binary-schema.md)。

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

route 可以继续追加局部错误组，生成 manifest 和 client lookup 时会把全局错误与 `.ERR(...)` 声明合并到当前 route 的错误面：

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

`STREAM` 与 `CHANNEL` 是新的长连接 DSL 入口，语义上与 RPC 并列，而不是直接暴露底层 WebSocket、SSE 或 Wails event。

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
- `scope` 支持 `ConnectionScope.SESSION`、`ConnectionScope.APP` 与 `ConnectionScope.TOPIC`，transport 可按自身能力映射；当前默认 HTTP/Wails runtime 只完整支持 `SESSION`。
- `delivery` 支持 `ConnectionDelivery.ORDERED` 与 `ConnectionDelivery.UNORDERED`；`STREAM` / `CHANNEL` 默认是 `ORDERED`。HTTP 下的 ordered 直接依赖 SSE / WebSocket 的单连接顺序，不额外叠加生成器自管的 sequence overlay；默认 Wails transport 会通过 transport-level sequence envelope 与 reorder buffer 保持“有序异步”；legacy `WS` 不进入这条 surface。
- HTTP `STREAM` 映射为 SSE，HTTP `CHANNEL` 映射为 WebSocket。
- `delivery=ConnectionDelivery.UNORDERED` 当前主要影响 Wails route；HTTP transport 仍沿用 SSE / WebSocket 的原生顺序行为，不会主动切到另一条乱序交付路径。
- Wails `STREAM` / `CHANNEL` 映射为 session-scoped runtime events，event name 只存在于 generated transport/runtime 内部。
- `APP` / `TOPIC` 的消息 schema 仍由 blueprint 生成；广播对象、topic key、replay、权限过滤等 fan-out 策略应由自定义 connection hub / manager 实现。
- 客户端主动 `close(code, reason)` 只表达传输关闭请求；业务取消应建模为 `CLIENT_MESSAGE(cancel=...)`。

完整可生成示例见 `examples/blueprints/api_demo.py` 中的 `/api/demo/sweep-events` 与 `/api/demo/assistant-session`。

## Legacy WebSocket

```python
class ClientMessage(Model):
    message = String(description="client message")


class ServerMessage(Model):
    message = String(description="server message")


with bp.group("/demo") as views:
    views.WS("/ws").RECV(ClientMessage).SEND(ServerMessage)
```

`WS().RECV().SEND()` 是 legacy 写法，不进入 1.0 ContractGraph 主线。新蓝图优先使用 `STREAM` / `CHANNEL`，避免把多个逻辑消息误建模成多个裸 event。

## 文档输出

`api-doc-server` 会加载 `[blueprint].entrypoints`，基于 Blueprint 构建 FastAPI/OpenAPI 文档。

```sh
api-doc-server -c api-blueprint.toml
```

当 `[blueprint].docs_server` 使用 `host:0` 时，启动输出会打印带真实绑定端口的 docs 或 hub URL。
