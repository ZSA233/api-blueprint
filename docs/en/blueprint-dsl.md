# Blueprint DSL

The Blueprint DSL describes API contracts in Python: route groups, request parameters, request bodies, response models, errors, and WebSocket messages.

## Basic Structure

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class DemoResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(DemoResponse)
```

`Blueprint(root="/api")` defines the route root. `group("/demo")` defines a group, producing `/api/demo/hello`.

## Model

```python
class Item(Model):
    id = Uint64(description="id")
    name = String(description="name")
    tags = Array[String](description="tags", omitempty=True)
```

Common types come from `api_blueprint.includes`, including `String`, `Bool`, `Int`, `Uint64`, `Float`, `Array`, and `Map`.

## Requests And Responses

```python
class CreateBody(Model):
    name = String(description="name")


class CreateResponse(Model):
    id = Uint64(description="id")


with bp.group("/items") as views:
    views.POST("/create").JSON(CreateBody).RSP(CreateResponse)
    views.GET("/detail").ARGS(id=Uint64(description="id")).RSP(CreateResponse)
```

- `ARGS(...)`: query parameters.
- `JSON(Model)`: JSON request body.
- `RSP(...)`: response model.

## WebSocket

```python
class ClientMessage(Model):
    message = String(description="client message")


class ServerMessage(Model):
    message = String(description="server message")


with bp.group("/demo") as views:
    views.WS("/ws").RECV(ClientMessage).SEND(ServerMessage)
```

TypeScript output exposes `ApiSocketBridge<ServerMessage, ClientMessage>`. Wails overlays do not expose raw WebSocket, while the HTTP shared client still keeps the raw WebSocket escape hatch.

## Documentation Output

`api-doc-server` loads `[blueprint].entrypoints` and builds FastAPI/OpenAPI documentation from Blueprint objects.

```sh
api-doc-server -c api-blueprint.toml
```
