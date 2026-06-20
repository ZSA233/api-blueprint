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

## Root And Logical Name

`root` is only the URL prefix. `name` is the protocol and generation identity; ContractGraph route IDs, service IDs, language root packages/modules/directories, default gRPC proto paths, and the Wails binding manifest all derive from its stable slug.

When `name` is omitted, a non-empty `root` keeps the existing identity behavior:

```python
bp = Blueprint(root="/api")
```

The route IDs and generated root still use `api`, and URLs still start with `/api`.

When a legacy protocol splits one app across several top-level URL namespaces, prefer an explicit name:

```python
bp = Blueprint(name="legacy", root="")

with bp.group("/account") as account:
    account.GET("/profile").RSP(...)

with bp.group("/room") as room:
    room.GET("/list").RSP(...)
```

These routes have URLs `/account/profile` and `/room/list`, but they share the `legacy` logical identity; a typical route ID is `legacy.account.get.profile`. Bare `Blueprint(root="")` fails fast; rootless Blueprints must provide `name` explicitly to avoid generated identity collisions with other roots. Existing Swift projects that need to keep the `APIRoutes` / `APIRootClient` / `api` entry shape can migrate to `Blueprint(name="api", root="")`.

Before generation, api-blueprint rejects duplicate route IDs, duplicate HTTP method + URL pairs, duplicate Blueprint logical identities, and root-group versus `/root`-style group collisions that would produce the same service/module surface.

### Compatibility

`Blueprint(name=...)` is a breaking-version capability. With `root=""`, the generator no longer assigns an implicit `rootless` or other fallback identity; callers must provide an explicit `name`. If an existing project relied on the released Swift entry shape from an `/api` root, such as `APIRoutes`, `APIRootClient`, and the aggregate `api` property, but the real URLs are now supplied by top-level groups, use:

```python
bp = Blueprint(name="api", root="")
```

URLs still come from the group and leaf, for example `/account/profile` or `/api/sample-action`; ContractGraph route IDs and generated roots use `api`, so Swift keeps the `APIRoutes` / `APIRootClient` / `api` style layout. Do not correct identity drift with a Swift-specific layout switch; all targets should share the same Blueprint logical identity.

## Model

```python
class Item(Model):
    id = Uint64(description="id")
    name = String(description="name")
    tags = Array[String](description="tags", optional=True)
```

Common types come from `api_blueprint.includes`, including `String`, `Bool`, `Int`, `Uint64`, `Float`, `Array`, and `Map`.
`optional=True` marks a field as optional. Prefer it for new schemas; `omitempty=True` remains available for compatibility.
Use `field(number, Type(...))` when a field needs stable identity, and `field(number, Type(...), choice="group")` to model mutually exclusive choices. These are generic contract semantics, not tied to a specific target.
Semantic value types include `DateTime`, `JSONValue`, and `AnyValue`; individual targets map them to their own time, JSON, or arbitrary payload representation.

`FileField(content_types=..., max_size=..., description=..., omitempty=False)` describes a multipart upload field. It is not a normal JSON field and is valid only inside a model bound with `REQ_MULTIPART(Model)`; using it in JSON, urlencoded, response, or long-connection message models fails contract construction.

When a DTO does not appear directly on a route request/response or STREAM/CHANNEL message, but a project plugin still needs to read it from ContractGraph, export it explicitly:

```python
class PushPayload(Model):
    id = Int64(description="id")


bp.EXPORT_MODELS(PushPayload, domain="push")
```

`EXPORT_MODELS` only writes the schema into `schemas` and records metadata in manifest `exported_models`; it does not create a route, and official targets are not required to generate or consume that model.

### Legacy JSON Compatibility Types

Older services may already return multiple JSON shapes for the same field, such as string sometimes and array other times, or ID fields that drift between string and integer JSON numbers across Java / legacy implementations. Use the restricted compatibility types when those fields need to enter the contract:

```python
class LegacyRoom(Model):
    target = OneOf(String(), Array[String](), description="legacy target")
    ids = Array[OneOf(String(), Int())](description="legacy ids")
    normalized_ids = Array[LegacyStringID](description="ids normalized to string")
    room_id = LegacyStringID(alias="roomId", description="room id")
```

- `OneOf(...)` describes a non-discriminated JSON union. Variants are tried in declaration order with strict JSON-shape matching. It is for legacy compatibility, not a recommended shape for new APIs.
- `CoerceString(accepts=(String, Int))` and the shortcut `LegacyStringID` accept string or integer JSON numbers, but the business type remains string and encoding always writes string. Bool, object, array, and fractional numbers are rejected.
- `StringOrIntAsString` is a deprecated compatibility alias for `LegacyStringID`; new blueprints should use `LegacyStringID`.
- `OneOf` can be nested inside `Array[...]` / `Map[...]`, and `Array[...]` can also be a variant. Empty `OneOf()` declarations fail.
- `FileField` is not a JSON field and cannot be placed inside `OneOf`. If a legacy field cannot be narrowed to finite shapes, use `JSONValue` as the final fallback.

## Requests And Responses

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

- `ARGS(...)`: query parameters.
- `REQ_PATH(Model)`: path parameters; route paths use only OpenAPI-style `{name}` placeholders.
- `JSON(Model)`: JSON request body.
- `REQ_URLENCODED(Model)`: `application/x-www-form-urlencoded` request bodies; the older `REQ_FORM(Model)` remains as a compatibility alias.
- `REQ_MULTIPART(Model)`: `multipart/form-data` request bodies mixing ordinary fields and `FileField(...)`.
- `REQ_BINARY_SCHEMA(path)`: Markdown Binary Schema request bodies; `REQ_BINARY(path)` remains as a short alias.
- `RSP(...)`: response model.
- `RSP_EMPTY()`: JSON responses with no business data on success; this is not HTTP 204 / no body. With a JSON response envelope, both `data: null` and `data: {}` decode as an empty business response.

`REQ_PATH` placeholder names must exactly match path-model field wire names. Fields must be required scalar, enum, or string-coerce values; optional, array, map, object, file, binary, and oneof fields are rejected. Gin-style `:id` is not DSL syntax; write `{id}` instead. REQ_PATH is limited to HTTP RPC routes. ContractGraph, ir-plugin, and official HTTP targets emit or generate path parameters; Wails/gRPC fail fast to avoid unusable generated code.

A route can declare only one body kind. ContractGraph records path requests as `path_model` / `path_params`, records request bodies as `none`, `json`, `urlencoded`, `multipart`, `binary_schema`, or `raw_bytes`, and both generators and `api-gen check` use that unified semantics for capability checks.

Binary HTTP request or response bodies use `.REQ_BINARY_SCHEMA("./binary/packet.md")` or `.RSP_BINARY_SCHEMA("./binary/packet.md")` to reference Markdown Binary Schema. In ContractGraph this is `binary_schema` and is separate from raw bytes/file/stream media responses. See [Markdown Binary Schema](binary-schema.md) for table format, field types, rules, and generated output.

## Multipart And Non-JSON Responses

```python
class PreviewRequest(Model):
    image = FileField(content_types=["image/png", "image/jpeg"], description="source image")
    max_width = Uint64(description="max width", optional=True)


with bp.group("/media") as views:
    views.POST("/preview").REQ_MULTIPART(PreviewRequest).RSP_BYTES(content_type="image/jpeg")
    views.GET("/download").RSP_FILE(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", default_filename="report.xlsx")
    views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace; boundary=frame")
```

Non-JSON response DSL includes:

- `RSP_BINARY_SCHEMA(path, content_type=None)`: bounded typed binary packets encoded from a Markdown Binary Schema. `RSP_BINARY(path)` remains as a short alias.
- `RSP_BYTES(content_type="application/octet-stream")`: buffered bytes such as a JPEG or frame.
- `RSP_FILE(content_type=..., default_filename=None)`: file downloads; services may return a path or a generated file response.
- `RSP_BYTE_STREAM(content_type=...)`: continuous byte streams such as MJPEG or custom streaming payloads.

Binary schema and raw success responses are not wrapped in the JSON response envelope. HTTP `content-type`, `content-disposition`, headers, download, and streaming semantics are recorded in the ContractGraph manifest. Business errors still use the route's typed error / JSON envelope, so generated clients can keep recognizing `ApiError` consistently.

`RSP_FILE(default_filename=...)` is a default download name, not a forced filename. A service-returned raw response filename or explicit `Content-Disposition` header overrides it. Clients parse only the actual response header and do not synthesize a filename from the contract default. The older `filename=...` parameter remains as a compatibility alias; passing both names with different values fails contract construction.

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

When `toast` is omitted, the default is equivalent to `key="<Group>.<KEY>"`, `default=message`, and `level="error"`. Response envelopes can expose nested error identity and `toast` according to their `error_identity` policy; clients resolve display text through `toast.text`, business i18n, `toast.default`, then `message`. When the server must override display text by request language, tenant, or rollout, return an immutable override result instead of mutating generated global error values or lookup entries.

Routes can add local error groups. The manifest and client lookup merge global errors with `.ERR(...)` declarations for the current route error surface:

```python
class DemoErr(Model):
    RATE_LIMITED = Error(
        42901,
        "too many requests",
        toast=Toast(
            key="demo.rate_limited",
            default="Too many requests. Please try again later.",
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

See `examples/blueprints/errors.py` and `examples/blueprints/api_demo.py` for the full example. Generated clients prefer `error.id`, then `(route_id, code)` lookup for that route; undeclared error codes still produce a usable `ApiError`.

## Long-Connection Message Flows

`STREAM` and `CHANNEL` are the long-connection DSL entrypoints. They sit alongside RPC semantically and do not expose the underlying WebSocket, SSE, or Wails event details directly.

- `STREAM`: server push, client subscribes only.
- `CHANNEL`: bidirectional client/server messaging.
- `OPEN(Model)`: connection-open parameters, mapped by HTTP to query/init parameters and by Wails to a session init envelope.
- `SERVER_MESSAGE(...)`: the logical message contract sent by the server.
- `CLIENT_MESSAGE(...)`: the logical message contract sent by the client, supported only by `CHANNEL`.
- `CLOSE(Model)`: the typed close lifecycle payload emitted by the server; a default close model is generated when it is omitted.
- `delivery=ConnectionDelivery.ORDERED`: long-connection delivery policy; `ORDERED` is the default, and `UNORDERED` is for explicit high-frequency opt-out cases.

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
- `scope` supports `ConnectionScope.SESSION`, `ConnectionScope.APP`, and `ConnectionScope.TOPIC`; each transport can map it according to its own capabilities. The default HTTP/Wails runtimes fully support `SESSION`.
- `delivery` supports `ConnectionDelivery.ORDERED` and `ConnectionDelivery.UNORDERED`; `STREAM` / `CHANNEL` default to `ORDERED`. On HTTP, ordered delivery relies on native per-connection SSE / WebSocket ordering and does not add a generator-owned sequence overlay. The default Wails transport keeps ordered delivery asynchronous by adding transport-level sequence envelopes and a reorder buffer.
- HTTP `STREAM` maps to SSE, and HTTP `CHANNEL` maps to WebSocket.
- `delivery=ConnectionDelivery.UNORDERED` mainly affects Wails routes. HTTP transports still follow the native ordering behavior of SSE / WebSocket rather than intentionally switching to a separate unordered path.
- Wails `STREAM` / `CHANNEL` map to session-scoped runtime events; event names exist only inside the generated transport/runtime.
- `APP` / `TOPIC` message schemas are still generated by blueprint; fan-out policy such as broadcast targets, topic keys, replay, and authorization filtering belongs in a custom connection hub / manager.
- Client-side `close(code, reason)` is only a transport close request; model business cancellation as `CLIENT_MESSAGE(cancel=...)`.

For complete generated examples, see `/api/demo/sweep-events` and `/api/demo/assistant-session` in `examples/blueprints/api_demo.py`.

## Migration Note

`WS().RECV().SEND()` has been removed from the blueprint DSL. Use `CHANNEL` for bidirectional WebSocket-style contracts and `STREAM` for server-only event streams.

## Documentation Output

`api-doc-server` loads `[blueprint].entrypoints` and builds FastAPI/OpenAPI documentation from Blueprint objects. By default, `/` and `/docs` both serve the api-blueprint docs center: it loads a lightweight route index first, then opens sliced Swagger views by group, tag, kind, or route selection so large APIs do not render one full Swagger page at once.

```sh
api-doc-server -c api-blueprint.toml
```

The full `/openapi.json` remains available for external OpenAPI tools. `STREAM` routes appear in the route index and in HTTP docs as SSE routes; `CHANNEL` routes appear in protocol details in the route index but are not forced into standard OpenAPI.

When `[blueprint].docs_server` uses `host:0`, startup output prints the actual docs or hub URL with the bound port.
