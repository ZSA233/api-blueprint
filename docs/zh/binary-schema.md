# Markdown Binary Schema

Markdown Binary Schema 用 `.md` 文件描述 HTTP 二进制请求体。它的目标是让协议源文件既能被 Markdown 渲染成文档，也能被 `api-gen check` 校验并生成服务端 parser 与客户端 writer。

第一版定位是固定宽度二进制协议：显式字节序、显式长度字段、可验证的动态数组、结构体数组、保留字节和 bitflags。它不是通用 Markdown 文档解析器；参与 schema 的内容必须使用约定的 heading 和 table。

## 路由接入

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

`.REQ_BINARY(path)` 可以和 `.ARGS(...)` query 参数共存，但不能和 JSON / form 请求体共存。旧 `.REQ_BIN(Model)` 不再作为正式能力使用。

## 文件结构

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

Schema 文件必须包含一个 `# packet Name`。`## header`、`## body` 等普通二级标题会按顺序组成 packet；`## struct Name` 定义可复用结构体；`## enum Name : u32` 和 `## bitflags Name : u32` 定义整数语义类型。

## 字段表

字段表列固定为：

| 列 | 含义 |
|:---|:---|
| `field` | 字段名 |
| `type` | 字段类型，可以是基础类型、结构体、enum 或 bitflags |
| `count` | 元素数量；`bytes` 的 count 表示字节数 |
| `rule` | 校验和关联规则 |
| `comment` | 文档说明 |

支持的基础类型：

```text
u8/u16/u24/u32/u64
i8/i16/i24/i32/i64
f32/f64
bool
bytes/string
padding/reserved
```

`padding` 和 `reserved` 不进入 public typed packet 字段；生成器会写入或校验对应数量的 0 字节。

## 规则

第一版支持的规则：

| 规则 | 用途 |
|:---|:---|
| `const=...` | 字段必须等于固定值 |
| `min=...` / `max=...` | 整数字段或动态长度的范围约束 |
| `sizeof=field` | 当前字段表示另一个数组或 bytes 字段的长度 |
| `assert=expr` | 当前字段必须等于表达式结果 |
| `layout=...` | 文档化线性布局，当前主要用于展示 |
| `encoding=utf-8` | bytes/string 的文本编码说明 |

动态数组或动态 bytes 必须能推导最大上限。常见写法是在长度字段上写 `max=...`，或在数组字段本身写 `max=...`。如果无法证明上限，`api-gen check` 会失败，避免坏包触发大内存分配。

## Enum 与 Bitflags

`enum` 表继续使用 `name/value/comment`：

```md
## enum DemoKind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric packet |
| Debug | 2 | debug packet |
```

`bitflags` 推荐使用 `bits` 表达位号或位段：

```md
## bitflags DemoFlags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload exists |
| HasScores | 1 | | scores exist |
| Mode | 2..3 | enum=DemoKind | packet mode |
| Reserved | 4..31 | const=0 | reserved bits must be zero |
```

`bits=0` 表示第 0 位，`bits=2..3` 表示连续位段。`enum=DemoKind` 表示该位段按枚举值解释，Go 生成物会提供 `Mode()` / `WithMode(...)` 这类 helper。`const=0` 表示这些位是保留位，生成的 Go server parser 与 Go / TypeScript / Kotlin / Python client writer 都会校验这些位必须为 0。

旧的 `name/value/comment` bitflags 表仍兼容，但新 schema 优先使用 `bits`，因为它更接近协议蓝图，也更容易表达保留位范围。

## 生成结果

生成器会按 route group 输出局部 binary helper，并复用共享 runtime。Go server / Go client 使用独立 `_gen_binary` package；Java/Kotlin 输出同 route package 下的 `GenBinary`；TypeScript/Python 输出同 route 目录下的 `gen_binary` module。例如：

```text
routes/api/binary/_gen_binary/gen_binary.go
routes/api/binary/GenBinary.java
routes/api/binary/GenBinary.kt
routes/api/binary/gen_binary.ts
routes/api/binary/gen_binary.py
runtime/binary/gen_runtime.go
```

Go bitflags 仍生成整数别名，便于保持 wire 兼容和位运算性能；额外 helper 只提供更直观的访问方式：

```go
flags.HasPayload()
flags.WithHasPayload(true)
flags.Mode()
flags.WithMode(DemoKindMetric)
flags.HasReservedBits()
flags.Validate()
```

Go / TypeScript / Kotlin / Python client 会为同一 schema 生成：

- typed packet，适合小包或测试。
- streaming/raw binary body，适合大包热路径。
- writer helper 和 block helper，适合把已经缓存或预编码的字段片段直接接入。

HTTP adapter 会把 binary body 作为 `application/octet-stream` 发送；服务端 adapter 会按 schema 声明接受 `identity` 或 `gzip`。

## 检查与调试

```sh
api-gen check -c api-blueprint.toml
api-gen inspect binary-schema DemoPacket -c api-blueprint.toml
api-gen inspect routes -c api-blueprint.toml
```

完整示例见 `examples/blueprints/binary/demo_packet.md`。
