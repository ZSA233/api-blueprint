# Markdown Binary Schema

Markdown Binary Schema describes HTTP binary request bodies and bounded binary success responses with `.md` files. The same source can render as Markdown documentation, pass `api-gen check`, and generate packet parsers, writers, server response encoders, and client response decoders.

The schema format targets fixed-width binary protocols: explicit endian, explicit length fields, validated dynamic arrays, struct arrays, reserved bytes, and bitflags. It is not a general Markdown document parser; schema content must use the documented heading and table shapes.

## Route Usage

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class UploadResult(Model):
    ok = Bool(description="ok")


with bp.group("/binary") as views:
    views.POST("/packet").ARGS(
        trace=String(description="trace id", optional=True),
    ).REQ_BINARY_SCHEMA("./binary/demo_packet.md").RSP(UploadResult)

    views.GET("/latest-packet").RSP_BINARY_SCHEMA("./binary/demo_packet.md")
```

`.REQ_BINARY_SCHEMA(path)` can coexist with `.ARGS(...)` query parameters, but cannot coexist with JSON or form request bodies. `.RSP_BINARY_SCHEMA(path)` is a non-envelope success response: generated server adapters encode the returned typed packet, while generated clients decode successful HTTP bytes back into the packet type. Business errors still use the route's JSON typed-error envelope.

## File Shape

````md
# packet DemoPacket

```yaml
endian: little
content-type: application/octet-stream
content-encoding: identity,gzip,br
```

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="ABP1" | magic |
| version | u16 | 1 | const=1 | protocol version |
| flags | DemoFlags | 1 | min=0 | feature flags |
| item_count | u16 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | DemoItem | item_count | | items |

## struct DemoItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1,max=999 | item id |
| value | f64 | 1 | | value |

## bitflags DemoFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload exists |
| FastPath | 1 | | fast path marker |
| Mode | 2..3 | enum=DemoKind | packet mode |
| Reserved | 4..31 | const=0 | reserved bits must be zero |
````

A schema file must contain exactly one `# packet Name`. Normal second-level headings such as `## header` and `## body` become packet sections in order. `## struct Name` defines reusable structs. `## enum Name : u32` and `## bitflags Name : u32` define integer semantic types.

Packet metadata after the top heading can stay as plain `key: value` lines, or be wrapped in a fenced code block such as ```` ```yaml ```` for cleaner Markdown rendering. Both forms parse identically; the fenced block content still uses the same `key: value` rules.

## Field Tables

Field table columns are fixed:

| Column | Meaning |
|:---|:---|
| `field` | Field name |
| `type` | Field type: primitive, struct, enum, or bitflags |
| `count` | Element count; for `bytes`, count means byte length |
| `rule` | Validation and relation rules |
| `comment` | Documentation text |

Supported primitive types:

```text
u8/u16/u24/u32/u64
i8/i16/i24/i32/i64
f32/f64
bool
bytes/string
padding/reserved
```

`padding` and `reserved` do not become public typed packet fields. Generators write or validate the corresponding number of zero bytes.

## Rules

Supported rules:

| Rule | Purpose |
|:---|:---|
| `const=...` | Field must equal a fixed value |
| `min=...` / `max=...` | Range constraint for integers or dynamic lengths |
| `sizeof=field` | Current field stores the length of another array or bytes field |
| `assert=expr` | Current field must equal an expression result |
| `layout=...` | Documents display-oriented linearized layout |
| `encoding=utf-8` | Encoding hint for bytes/string fields |

Dynamic arrays or dynamic bytes must have a derivable upper bound. The common shape is `max=...` on the length field, or `max=...` on the array field itself. If no upper bound can be proven, `api-gen check` fails to avoid hostile packets causing large allocations.

## Enum And Bitflags

`enum` tables still use `name/value/comment`:

```md
## enum DemoKind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric packet |
| Debug | 2 | debug packet |
```

`bitflags` should prefer `bits` for bit indexes or ranges:

```md
## bitflags DemoFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload exists |
| HasScores | 1 | | scores exist |
| Mode | 2..3 | enum=DemoKind | packet mode |
| Reserved | 4..31 | const=0 | reserved bits must be zero |
```

`bits=0` means bit 0. `bits=2..3` means a continuous range. `enum=DemoKind` interprets the range as an enum value, and Go output generates helpers such as `Mode()` / `WithMode(...)`. `const=0` marks those bits as reserved; generated Go server parsers and Go / TypeScript / Flutter / Kotlin / Python client writers validate that they stay zero.

### Compatibility

The older `.REQ_BIN(Model)` route API, `.REQ_BINARY(path)` short alias, `.RSP_BINARY(path)` short alias, and `name/value/comment` bitflags tables remain compatibility paths. New route schemas should use `.REQ_BINARY_SCHEMA(path)` / `.RSP_BINARY_SCHEMA(path)` and `bits` / `rule` bitflags tables because they express protocol layout and reserved ranges more directly.

## Generated Output

Generators emit route-group-local binary helpers and reuse the shared runtime. Go server keeps a separate `_gen_binary` parser package because it is an internal request parser. Client SDKs expose binary packet and writer helpers from the route-local public types surface. For example:

```text
routes/api/binary/_gen_binary/gen_binary.go   # Go server
routes/api/binary/gen_binary.go               # Go client
routes/api/binary/GenBinaryTypes.java
routes/api/binary/GenBinaryTypes.kt
routes/api/binary/gen_binary.ts
lib/src/api/routes/api/binary/gen_binary.dart
lib/src/api/runtime/binary/gen_binary_runtime.dart
routes/api/binary/gen_binary.py
routes/api/binary/gen_types.py
runtime/binary/gen_runtime.go
```

When multiple `.REQ_BINARY_SCHEMA(...)` or `.RSP_BINARY_SCHEMA(...)` routes share the same route group, packet entry names stay packet-based (`DemoPacket`, `DemoPacketWire`, `ParseDemoPacket`, `DemoPacketToBinaryBody`). Schema-internal generated symbols are packet-scoped: a schema `struct Item`, `enum Kind`, `bitflags Flags`, state holder, or writer/parser helper is emitted as names such as `DemoPacketItem`, `DemoPacketKind`, and `DemoPacketFlags`. Packet names that normalize to the same generated symbol, such as `DemoPacket` and `Demo_Packet`, are rejected before files are written.

Binary parser / writer diagnostics use the schema's original packet, section, object, and field names rather than target-language internal generated symbols. Nested objects and array items wrap paths after an error occurs, for example `DemoPacket.body.items[0].id`; successful write paths do not eagerly concatenate full field paths just for diagnostics.

Public packet field names follow each target language's SDK conventions while diagnostics keep schema names. Go / Kotlin / Java / Flutter expose language-style fields such as `ItemCount` or `itemCount`; TypeScript and Python keep snake_case fields such as `item_count` to stay close to JSON / wire naming.

Go bitflags remain integer aliases to keep wire compatibility and bit-operation performance; helpers provide a clearer access surface:

```go
flags.HasPayload()
flags.WithHasPayload(true)
flags.Mode()
flags.WithMode(DemoKindMetric)
flags.HasReservedBits()
flags.Validate()
```

Go / TypeScript / Flutter / Kotlin / Python / Java clients generate, from the same schema:

- typed packets for small bodies or tests.
- streaming/raw binary bodies for large hot paths.
- writer helpers and block helpers for plugging in cached or pre-encoded field fragments.

For binary schema responses, Go / Python / Kotlin server adapters encode typed packet return values as HTTP bytes, and Go / TypeScript / Flutter / Kotlin / Java / Python clients decode successful HTTP bytes into typed packets. The Java server target emits Spring generated Controllers, delegate interfaces, typed packets, and helpers, but not a standalone HTTP adapter. Wails/gRPC do not inherit HTTP raw response semantics; those routes fail `api-gen check` with an explicit unsupported contract error that points to transport-native bytes / chunk modeling.

Go / Python / Kotlin server adapters parse `.REQ_BINARY_SCHEMA(...)` request bytes into the generated typed packet before calling the generated service interface. Java generated Controllers parse supported binary schema request bytes before calling the generated delegate.

HTTP adapters use the route binary schema content type, falling back to `application/octet-stream`. For request bodies, `content-encoding` is a route whitelist for `.REQ_BINARY_SCHEMA(...)`: an empty header is `identity`, `gzip` is decoded by built-in server helpers, and extensions such as `br` require an app-registered server decoder. Generated clients still send identity bodies unless caller code explicitly provides compressed bytes and the matching `Content-Encoding` header.

## Check And Inspect

```sh
api-gen check -c api-blueprint.toml
api-gen inspect binary-schema DemoPacket -c api-blueprint.toml
api-gen inspect routes -c api-blueprint.toml
```

See `examples/blueprints/binary/demo_packet.md` for a complete example.
