# Markdown Binary Schema

Markdown Binary Schema 用 `.md` 文件描述 HTTP 二进制请求体和 bounded 二进制成功响应。它的目标是让协议源文件既能被 Markdown 渲染成文档，也能被 `api-gen check` 校验，并生成 packet parser、writer、服务端响应 encoder 与客户端响应 decoder。

Schema 格式面向固定宽度二进制协议：显式字节序、显式长度字段、可验证的动态数组、结构体数组、保留字节和 bitflags。它不是通用 Markdown 文档解析器；参与 schema 的内容必须使用约定的 heading 和 table。

## 路由接入

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

`.REQ_BINARY_SCHEMA(path)` 可以和 `.ARGS(...)` query 参数共存，但不能和 JSON / form 请求体共存。`.RSP_BINARY_SCHEMA(path)` 是不套成功 envelope 的响应：generated server adapter 会把 service 返回的 typed packet 编码成 HTTP bytes，generated client 会把成功响应 bytes 解码回 typed packet。业务错误仍按 route 的 JSON typed-error envelope 返回。

## 文件结构

````md
# packet DemoPacket

```yaml
endian: little
content-type: application/octet-stream
content-encoding: identity,gzip
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

Schema 文件必须包含一个 `# packet Name`。`## header`、`## body` 等普通二级标题会按顺序组成 packet；`## struct Name` 定义可复用结构体；`## enum Name : u32` 和 `## bitflags Name : u32` 定义整数语义类型。

顶层 heading 后的 packet metadata 可以保持裸 `key: value` 行，也可以用 ```` ```yaml ```` 这类 fenced code block 包起来，改善 Markdown 渲染。两种写法解析结果相同；fenced block 内部仍然使用同一套 `key: value` 规则。

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

支持的规则：

| 规则 | 用途 |
|:---|:---|
| `const=...` | 字段必须等于固定值 |
| `min=...` / `max=...` | 整数字段或动态长度的范围约束 |
| `sizeof=field` | 该字段表示另一个数组或 bytes 字段的长度 |
| `assert=expr` | 该字段必须等于表达式结果 |
| `layout=...` | 文档化线性布局，用于展示 |
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

`bits=0` 表示第 0 位，`bits=2..3` 表示连续位段。`enum=DemoKind` 表示该位段按枚举值解释，Go 生成物会提供 `Mode()` / `WithMode(...)` 这类 helper。`const=0` 表示这些位是保留位，生成的 Go server parser 与 Go / TypeScript / Flutter / Kotlin / Python client writer 都会校验这些位必须为 0。

### 兼容性说明

较早的 `.REQ_BIN(Model)` 路由 API、`.REQ_BINARY(path)` 短别名、`.RSP_BINARY(path)` 短别名和 `name/value/comment` bitflags 表仍作为兼容路径保留。新 route schema 应使用 `.REQ_BINARY_SCHEMA(path)` / `.RSP_BINARY_SCHEMA(path)` 以及 `bits` / `rule` bitflags 表，因为它们更适合表达协议布局和保留位范围。

## 生成结果

生成器会按 route group 输出局部 binary helper，并复用共享 runtime。Go server 保留独立 `_gen_binary` parser package，因为它是服务端内部 request parser。Client SDK 的 binary packet 与 writer helper 从 route-local public types surface 暴露。例如：

```text
routes/api/binary/_gen_binary/gen_binary.go   # Go server
routes/api/binary/gen_binary.go               # Go client
routes/api/binary/BinaryTypes.java
routes/api/binary/BinaryTypes.kt
routes/api/binary/gen_binary.ts
lib/src/api/routes/api/binary/gen_binary.dart
lib/src/api/runtime/binary/gen_binary_runtime.dart
routes/api/binary/gen_binary.py
routes/api/binary/gen_types.py
runtime/binary/gen_runtime.go
```

当多个 `.REQ_BINARY_SCHEMA(...)` 或 `.RSP_BINARY_SCHEMA(...)` route 位于同一个 route group 时，packet 入口名仍保持基于 packet 的稳定命名，例如 `DemoPacket`、`DemoPacketWire`、`ParseDemoPacket`、`DemoPacketToBinaryBody`。Schema 内部生成符号会按 packet 作用域输出：`struct Item`、`enum Kind`、`bitflags Flags`、state holder、writer/parser helper 会生成类似 `DemoPacketItem`、`DemoPacketKind`、`DemoPacketFlags` 的名字。`DemoPacket` 与 `Demo_Packet` 这类归一化后生成名相同的 packet name 会在写文件前被明确拒绝。

二进制 parser / writer 的诊断路径使用 schema 原始 packet、section、object 和 field 名，而不是生成语言里的内部符号名。嵌套对象和数组元素会在错误发生后按上下文包装路径，例如 `DemoPacket.body.items[0].id`；成功写入路径不会为了诊断信息提前拼接完整字段路径。

Public packet 字段名遵循目标语言的 SDK 习惯，但诊断路径仍保持 schema 原始名字。Go / Kotlin / Java / Flutter 暴露 `ItemCount` 或 `itemCount` 这类语言风格字段；TypeScript / Python 保持 `item_count` 这类贴近 JSON / wire 命名的 snake_case 字段。

Go bitflags 仍生成整数别名，便于保持 wire 兼容和位运算性能；额外 helper 只提供更直观的访问方式：

```go
flags.HasPayload()
flags.WithHasPayload(true)
flags.Mode()
flags.WithMode(DemoKindMetric)
flags.HasReservedBits()
flags.Validate()
```

Go / TypeScript / Flutter / Kotlin / Python / Java client 会为同一 schema 生成：

- typed packet，适合小包或测试。
- streaming/raw binary body，适合大包热路径。
- writer helper 和 block helper，适合把已经缓存或预编码的字段片段直接接入。

对于 binary schema 响应，Go / Python / Kotlin / Java server adapter 会把 typed packet 返回值编码成 HTTP bytes，Go / TypeScript / Flutter / Kotlin / Java / Python client 会把成功响应 bytes 解码成 typed packet。Wails/gRPC 不继承 HTTP raw response 语义，相关 route 会在 `api-gen check` 阶段明确报 unsupported contract error，并提示使用 transport-native bytes / chunk 建模。

Java server controller 会把 `.REQ_BINARY_SCHEMA(...)` 请求字节解析成 generated typed packet 后再调用 generated service interface。这仍然是协议契约代码；HTTP content-encoding 编排仍属于 transport/runtime 层职责。

HTTP adapter 会使用 route binary schema 的 content type，缺省回退到 `application/octet-stream`；服务端 adapter 会按 schema 声明接受 `identity` 或 `gzip`。

## 检查与调试

```sh
api-gen check -c api-blueprint.toml
api-gen inspect binary-schema DemoPacket -c api-blueprint.toml
api-gen inspect routes -c api-blueprint.toml
```

完整示例见 `examples/blueprints/binary/demo_packet.md`。
