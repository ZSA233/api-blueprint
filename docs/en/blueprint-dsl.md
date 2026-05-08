# Blueprint DSL

The Blueprint DSL describes API contracts in Python: route groups, request parameters, request bodies, response models, errors, and transport-neutral long-connection message flows.

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
    tags = Array[String](description="tags", optional=True)
```

Common types come from `api_blueprint.includes`, including `String`, `Bool`, `Int`, `Uint64`, `Float`, `Array`, and `Map`.
`optional=True` marks a field as optional. Legacy `omitempty=True` remains compatible, but new DSL should prefer `optional=True`.
Use `field(number, Type(...))` when a field needs stable identity, and `field(number, Type(...), choice="group")` to model mutually exclusive choices. These are generic contract semantics, not tied to a specific target.
Semantic value types include `DateTime`, `JSONValue`, and `AnyValue`; individual targets map them to their own time, JSON, or arbitrary payload representation.

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

## Errors And Toast

Error definitions use `Error(code, message)`. `message` is the protocol-level default description for logs, OpenAPI, and older-client fallback. Use `Toast(key, default, level)` for user-facing display metadata: the DSL writes only one default language, and generators emit only key/default/level instead of a built-in locale map.

```python
class CommonErr(Model):
    TOKEN_EXPIRE = Error(
        55555,
        "token login state expired",
        toast=Toast(
            key="auth.token_expire",
            default="Your session has expired. Please sign in again.",
            level="warning",
        ),
    )
```

When `toast` is omitted, the default is equivalent to `key="<Group>.<KEY>"`, `default=message`, and `level="error"`. Response wrappers carry an optional `toast` field; clients resolve display text through `toast.text`, business i18n, `toast.default`, then `message`. When the server must override display text by request language, tenant, or rollout, return an immutable override result instead of mutating generated global error values or catalog entries.

## Long-Connection Message Flows

`STREAM` and `CHANNEL` are the new long-connection DSL entrypoints. They sit alongside RPC semantically and do not expose the underlying WebSocket, SSE, or Wails event details directly.

- `STREAM`: server push, client subscribes only.
- `CHANNEL`: bidirectional client/server messaging.
- `OPEN(Model)`: connection-open parameters, mapped by HTTP to query/init parameters and by Wails to a session init envelope.
- `SERVER_MESSAGE(...)`: the logical message contract sent by the server.
- `CLIENT_MESSAGE(...)`: the logical message contract sent by the client, supported only by `CHANNEL`.
- `CLOSE(Model)`: the typed close lifecycle payload emitted by the server; a default close model is generated when it is omitted.

For one message type in a direction, pass the model directly:

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

For multiple message types in one direction, define one discriminated union message with a union name and keyword variants:

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

TypeScript output generates a stable discriminated union:

```ts
export type TaskStreamMessage =
    | { type: "state"; data: TaskState }
    | { type: "progress"; data: TaskProgress }
    | { type: "log"; data: TaskLog };
```

A bidirectional channel must declare both `CLIENT_MESSAGE` and `SERVER_MESSAGE`:

```python
class UserInput(Model):
    text = String(description="user input")


class AssistantDelta(Model):
    text = String(description="assistant delta")


with bp.group("/assistant") as views:
    views.CHANNEL("/session", scope=ConnectionScope.SESSION, operation_id="AssistantSession").OPEN(SweepOpen).CLIENT_MESSAGE(UserInput).SERVER_MESSAGE(AssistantDelta).CLOSE(StreamClose)
```

API rules:

- Multiple chained `.SERVER_MESSAGE()` / `.CLIENT_MESSAGE()` calls are not supported; repeated calls raise an error.
- `.SERVER_MESSAGE(TaskState, TaskLog)` is not supported because it has no stable discriminator value.
- `STREAM` does not allow `.CLIENT_MESSAGE(...)`.
- `CHANNEL` requires both `.CLIENT_MESSAGE(...)` and `.SERVER_MESSAGE(...)`.
- `operation_id` can be set on RPC / `STREAM` / `CHANNEL` when generated handler / client / transport names should use stable business semantics instead of default path-derived names. Explicit values are normalized into stable PascalCase identifiers without flattening token-internal casing, so `TaskEvents`, `taskEvents`, and `task_events` all stabilize to `TaskEvents`. It changes only the operation-derived surface, not the route id, path, or connection semantics.
- When `operation_id` is omitted and auto-generated names collide inside the same group for the same path, the generator disambiguates them by method or connection kind, for example `CurrentGet` / `CurrentPut` or `EventsStream` / `EventsChannel`.
- If multiple explicit `operation_id` values still collide after normalization, `api-gen check` / `api-gen generate` fail and require unique `operation_id` values for the conflicting routes.
- `scope` supports `ConnectionScope.SESSION`, `ConnectionScope.APP`, and `ConnectionScope.TOPIC`; each transport can map it according to its own capabilities. The default HTTP/Wails runtimes currently fully support only `SESSION`.
- HTTP `STREAM` maps to SSE, and HTTP `CHANNEL` maps to WebSocket.
- Wails `STREAM` / `CHANNEL` map to session-scoped runtime events; event names exist only inside the generated transport/runtime.
- `APP` / `TOPIC` message schemas are still generated by blueprint; fan-out policy such as broadcast targets, topic keys, replay, and authorization filtering belongs in a custom connection hub / manager.
- Client-side `close(code, reason)` is only a transport close request; model business cancellation as `CLIENT_MESSAGE(cancel=...)`.

For complete generated examples, see `/api/demo/sweep-events` and `/api/demo/assistant-session` in `examples/blueprints/api_demo.py`.

## Legacy WebSocket

```python
class ClientMessage(Model):
    message = String(description="client message")


class ServerMessage(Model):
    message = String(description="server message")


with bp.group("/demo") as views:
    views.WS("/ws").RECV(ClientMessage).SEND(ServerMessage)
```

`WS().RECV().SEND()` is a legacy form outside the 1.0 ContractGraph mainline. New blueprints should prefer `STREAM` / `CHANNEL` so multiple logical messages are not modeled as multiple raw events.

## Documentation Output

`api-doc-server` loads `[blueprint].entrypoints` and builds FastAPI/OpenAPI documentation from Blueprint objects.

```sh
api-doc-server -c api-blueprint.toml
```
