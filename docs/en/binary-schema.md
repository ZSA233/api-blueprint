# Markdown Binary Schema

Markdown Binary Schema describes HTTP binary request bodies with `.md` files. The same source can render as Markdown documentation, pass `api-gen check`, and generate server parsers plus client writers.

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
    ).REQ_BINARY("./binary/demo_packet.md").RSP(UploadResult)
```

`.REQ_BINARY(path)` can coexist with `.ARGS(...)` query parameters, but cannot coexist with JSON or form request bodies.

## File Shape

```md
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip

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
```

A schema file must contain exactly one `# packet Name`. Normal second-level headings such as `## header` and `## body` become packet sections in order. `## struct Name` defines reusable structs. `## enum Name : u32` and `## bitflags Name : u32` define integer semantic types.

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

`bits=0` means bit 0. `bits=2..3` means a continuous range. `enum=DemoKind` interprets the range as an enum value, and Go output generates helpers such as `Mode()` / `WithMode(...)`. `const=0` marks those bits as reserved; generated Go server parsers and Go / TypeScript / Kotlin / Python client writers validate that they stay zero.

### Compatibility

The older `.REQ_BIN(Model)` route API and `name/value/comment` bitflags tables remain compatibility paths. New schemas should use `.REQ_BINARY(path)` and `bits` / `rule` bitflags tables because they express protocol layout and reserved ranges more directly.

## Generated Output

Generators emit route-group-local binary helpers and reuse the shared runtime. Go server keeps a separate `_gen_binary` parser package because it is an internal request parser. Client SDKs expose binary packet and writer helpers from the route-local public types surface. For example:

```text
routes/api/binary/_gen_binary/gen_binary.go   # Go server
routes/api/binary/gen_binary.go               # Go client
routes/api/binary/BinaryTypes.java
routes/api/binary/BinaryTypes.kt
routes/api/binary/gen_binary.ts
routes/api/binary/gen_binary.py
routes/api/binary/gen_types.py
runtime/binary/gen_runtime.go
```

Go bitflags remain integer aliases to keep wire compatibility and bit-operation performance; helpers provide a clearer access surface:

```go
flags.HasPayload()
flags.WithHasPayload(true)
flags.Mode()
flags.WithMode(DemoKindMetric)
flags.HasReservedBits()
flags.Validate()
```

Go / TypeScript / Kotlin / Python clients generate, from the same schema:

- typed packets for small bodies or tests.
- streaming/raw binary bodies for large hot paths.
- writer helpers and block helpers for plugging in cached or pre-encoded field fragments.

HTTP adapters send binary bodies as `application/octet-stream`; server adapters accept `identity` or `gzip` according to the schema.

## Check And Inspect

```sh
api-gen check -c api-blueprint.toml
api-gen inspect binary-schema DemoPacket -c api-blueprint.toml
api-gen inspect routes -c api-blueprint.toml
```

See `examples/blueprints/binary/demo_packet.md` for a complete example.
