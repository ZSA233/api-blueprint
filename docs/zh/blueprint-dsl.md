# Blueprint DSL

Blueprint DSL 用 Python 描述 API 契约，包括路由分组、请求参数、请求体、响应模型、错误结构与 WebSocket 消息。

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

## WebSocket

```python
class ClientMessage(Model):
    message = String(description="client message")


class ServerMessage(Model):
    message = String(description="server message")


with bp.group("/demo") as views:
    views.WS("/ws").RECV(ClientMessage).SEND(ServerMessage)
```

TypeScript 生成结果会暴露 `ApiSocketBridge<ServerMessage, ClientMessage>`。Wails overlay 不暴露 raw WebSocket，HTTP shared client 仍保留 raw WebSocket escape hatch。

## 文档输出

`api-doc-server` 会加载 `[blueprint].entrypoints`，基于 Blueprint 构建 FastAPI/OpenAPI 文档。

```sh
api-doc-server -c api-blueprint.toml
```
