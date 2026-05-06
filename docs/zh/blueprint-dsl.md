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
    tags = Array[String](description="tags", omitempty=True)
```

常用类型来自 `api_blueprint.includes`，包括 `String`、`Bool`、`Int`、`Uint64`、`Float`、`Array`、`Map` 等。

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

## 长连接消息流

`STREAM` 与 `CHANNEL` 是新的长连接 DSL 入口，语义上与 RPC 并列，而不是直接暴露底层 WebSocket、SSE 或 Wails event。

- `STREAM`：服务端持续推送，客户端只订阅。
- `CHANNEL`：客户端和服务端双向收发消息。
- `OPEN(Model)`：连接建立参数，HTTP 可作为 query/init 参数，Wails 可作为 session init envelope。
- `SERVER_MESSAGE(...)`：服务端推给客户端的逻辑消息契约。
- `CLIENT_MESSAGE(...)`：客户端发给服务端的逻辑消息契约，仅 `CHANNEL` 支持。
- `CLOSE(Model)`：服务端发出的 typed close lifecycle payload；未声明时生成默认关闭模型。

单消息方向直接传模型：

```python
class SweepOpen(Model):
    run_id = String(description="run id")


class TaskLog(Model):
    message = String(description="log message")


class StreamClose(Model):
    code = Int(description="logical close code")
    reason = String(description="close reason", omitempty=True)
    error = String(description="machine-readable error key", omitempty=True)


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
    views.STREAM("/events", scope=ConnectionScope.SESSION).OPEN(SweepOpen).SERVER_MESSAGE(
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
    views.CHANNEL("/session", scope=ConnectionScope.SESSION).OPEN(SweepOpen).CLIENT_MESSAGE(UserInput).SERVER_MESSAGE(AssistantDelta).CLOSE(StreamClose)
```

API 规则：

- 不支持多个 `.SERVER_MESSAGE()` / `.CLIENT_MESSAGE()` 链式叠加，重复调用会报错。
- 不支持 `.SERVER_MESSAGE(TaskState, TaskLog)`，因为缺少稳定 discriminator value。
- `STREAM` 不允许 `.CLIENT_MESSAGE(...)`。
- `CHANNEL` 必须同时有 `.CLIENT_MESSAGE(...)` 与 `.SERVER_MESSAGE(...)`。
- `scope` 支持 `ConnectionScope.SESSION`、`ConnectionScope.APP` 与 `ConnectionScope.TOPIC`，transport 可按自身能力映射；当前默认 HTTP/Wails runtime 只完整支持 `SESSION`。
- HTTP `STREAM` 映射为 SSE，HTTP `CHANNEL` 映射为 WebSocket。
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

`WS().RECV().SEND()` 是 legacy 写法，继续保留兼容。新蓝图优先使用 `STREAM` / `CHANNEL`，避免把多个逻辑消息误建模成多个裸 event。

## 文档输出

`api-doc-server` 会加载 `[blueprint].entrypoints`，基于 Blueprint 构建 FastAPI/OpenAPI 文档。

```sh
api-doc-server -c api-blueprint.toml
```
