# Go server route DTO enum 类型未收紧

## 状态

已解决。

## 发现日期

2026-06-21

## 背景

真实使用反馈显示：Go server target 已经为 DSL enum 生成 `_gen_enums` 包，也在 contract metadata 中标记字段为 enum，但 route request / response DTO 字段仍然使用 enum 的底层 scalar 类型。

当前生成形态类似：

```go
package enums

type ResOp int
type GiftStatus int
type GiftFormat int
```

但 route DTO 中仍是：

```go
type REQ_Op_JSON struct {
	Op     int `json:"op"`
	Status int `json:"status,omitempty"`
	Format int `json:"format,omitempty"`
}
```

更理想的 Go server 类型约束是：

```go
type REQ_Op_JSON struct {
	Op     enums.ResOp      `json:"op"`
	Status enums.GiftStatus `json:"status,omitempty"`
	Format enums.GiftFormat `json:"format,omitempty"`
}
```

这意味着 Go 编译器能够在业务 handler、测试 fixture 和 preserved scaffold 中看到真实 enum 类型，而不是裸 `int` / `string`。

## 风险分级

中高。当前 wire 协议不一定出错，但 Go server 侧类型约束没有完全生效，容易让业务代码继续写入任意 scalar 值。后续如果直接切换到 typed enum，又可能因为 go-enum 的 marshal 行为改变 JSON wire shape，因此需要谨慎设计。

## 问题性质

生成器类型一致性缺口。DSL、ContractGraph metadata 和 `_gen_enums` 生成已经识别 enum，但 Go server route DTO 类型没有使用生成的 enum type，导致“生成了 enum，但协议落点没有吃到 enum 约束”。

## 存在性判断

已确认。

当前 Go server 类型解析中，enum 字段会解析为 enum base type，即 `int` / `string` 等底层类型；生成示例中也可以看到 `_gen_enums` 已存在，但 route DTO 字段仍为 scalar。

这与 Go client / AppSocket 中“字段直接使用 typed enum”的形态不一致。

## 复现场景

DSL 中定义 enum 字段：

```python
class ResOp(enum.IntEnum):
    CREATE = 1
    UPDATE = 2

class ReqOp(Model):
    op = Enum[ResOp]()
```

Go server 生成 DTO 时，当前字段类型为：

```go
Op int `json:"op"`
```

业务代码可以写入：

```go
req.Body.Op = 999
```

编译仍然通过。期望是字段类型收紧为：

```go
Op enums.ResOp `json:"op"`
```

从而让业务代码显式使用 enum 常量或转换。

## 影响范围

- Go server route request / response DTO。
- JSON / XML / form / query / path binding 中包含 enum 字段的 route。
- array / map / nested model 中的 enum 字段，例如 `[]enums.GiftStatus`、`map[string]enums.GiftStatus`。
- preserved scaffold 和业务 handler 中已有裸 scalar 赋值的代码。
- Go example snapshot、conformance fixture 和编译 smoke。

## 序列化 / 反序列化判断

不能简单认为“Go named int/string 类型一定与底层类型序列化一致”。

如果 enum 类型只是普通 named scalar，例如：

```go
type Status int
```

那么 `encoding/json` 对数字 enum 通常会按数字处理。但当前 `_gen_enums` 使用 `go-enum --marshal`，生成的 enum type 会实现 `MarshalText` / `UnmarshalText`。在这种情况下，`encoding/json` 会把 int enum 编码为字符串文本，并且反序列化 JSON number 时可能失败。

验证示例：

```go
type StatusEnum int

func (x StatusEnum) MarshalText() ([]byte, error) { return []byte("PENDING"), nil }
func (x *StatusEnum) UnmarshalText(text []byte) error { *x = 1; return nil }

type T struct {
	Status StatusEnum `json:"status"`
}
```

`json.Marshal(T{Status: 1})` 会输出：

```json
{"status":"PENDING"}
```

而 `json.Unmarshal({"status":1})` 会报：

```text
cannot unmarshal number into Go struct field ... of type StatusEnum
```

因此，如果 route DTO 直接改成 `_gen_enums.StatusEnum`，numeric enum 的 wire shape 可能从 number 变成 string，或者导致旧服务端传入 number 时绑定失败。这是本问题最大的修复风险。

## 性能影响判断

如果最终方案能保持 enum 按底层 scalar wire 读写，性能影响预计很小：

- 字段类型从 `int` / `string` 变为 named scalar type，本身没有额外分配。
- 编译期类型约束不会进入请求处理热路径。
- array / map 中使用 named scalar type 也不会天然带来显著运行时成本。

需要重点评估的是自定义 marshal / unmarshal：

- 如果使用 `MarshalText` / `UnmarshalText` 的字符串名解析，可能引入 map lookup、字符串分配和错误路径成本。
- 如果 numeric enum 需要额外 `MarshalJSON` / `UnmarshalJSON` 保持数字 wire，则需要确认实现不引入明显热路径开销。
- query / form / path binding 若走字符串解析，也需要测试大批量请求下是否有可接受的开销。

整体看，性能不是主要阻碍；wire 兼容和绑定语义才是主要风险。

## 兼容性 / 修复风险

主要风险：

- Go server generated API 破坏性变化：业务代码中对 enum 字段的裸 `int` / `string` 赋值需要改为 enum 常量或显式 cast。
- numeric enum 的 JSON wire shape 可能被 `go-enum --marshal` 改成字符串，需要先设计保持原始 value wire 的策略。
- Gin / form / query / path binding 对 typed enum 的行为需要分别验证。
- optional / `omitempty` 语义必须保持：例如原来 `Status int` 的零值省略，改成 `enums.GiftStatus` 后不应改变。
- route package 对 `_gen_enums` 的 import 必须按需生成，避免无用 import 和 import cycle。
- array / map / nested enum 不能遗漏，否则会出现部分字段 typed、部分字段仍裸 scalar 的不一致。

## 是否建议修复

建议修复，但不建议直接把字段类型从 scalar 替换成 `_gen_enums.X` 后立即合入。

该优化属于协议生成质量的进化：它让 DSL enum、contract metadata、生成 enum 包和 Go server DTO 全部对齐，也能提升业务代码的编译期约束。但修复必须先解决 numeric enum 的 JSON wire 保持问题，否则可能把一个类型安全优化变成 wire breaking change。

## 后续处置建议

- 先设计 Go enum wire 策略：
  - string enum 继续按 string value 编解码。
  - int enum 应保持 JSON number / form number / path number wire，除非 DSL 明确声明需要 name string。
  - 如继续使用 `go-enum --marshal`，需要评估是否额外生成 `MarshalJSON` / `UnmarshalJSON` 覆盖 `MarshalText` 对 JSON 的影响。
- 更新 Go server type resolver，使 enum 字段、array item、map value 和 nested model 字段使用 `_gen_enums` typed enum。
- 增加 Go server codegen 测试：
  - request DTO 字段生成 `enums.ResOp`。
  - response DTO 字段生成 `enums.GiftStatus`。
  - `[]enums.X` / `map[string]enums.X` 正确生成并按需 import。
- 增加 JSON / query / form / path binding 测试，尤其覆盖 numeric enum 和 string enum。
- 更新 migration 文档，说明 Go server v3 后 enum DTO 字段从裸 scalar 收紧为 enum type，业务代码需要使用 enum 常量或显式 cast。
- 修复完成后移动本记录到 `docs/reviews/resolved/` 并追加验证命令与相关 commit。

## 修复记录 / Resolution

修复日期：2026-06-21

修复摘要：

- Go server type resolver 已将 DSL `Enum[...]` 字段解析为 `_gen_enums` typed enum，例如 `enums.ResOp`、`enums.GiftStatus`、`[]enums.X`、`map[string]enums.X`。
- Go server enum 生成移除了 `go-enum --marshal`，生成物不再包含 `MarshalText` / `UnmarshalText`，避免 numeric enum 被 `encoding/json` 编成 enum 名称字符串。
- DSL enum binding tag 补齐 `oneof=<values>`，JSON/query/form/path 等网络输入仍按 DSL enum value 校验。
- Go type 引用做了轻量收敛，新增 `GolangType.package_ref(...)`，替代 Go server 相关路径中的 `{provider_package$}` / `{binary_package$}` / `{protos_package$}` 手写占位字符串。
- Go server enum collector 不再复用按 `proto.name` 去重后的 route proto 列表；现在会扫描所有 route group 的 raw proto，避免多个包都有 `REQ_List_QUERY` 时，后出现的 route-local inline enum 被同名 proto 去重漏掉。
- 示例 preserved impl 已迁移为 enum 常量或显式 `string(...)` 转换，文档补充了 Go server DTO enum 收紧的迁移提示。
- 修复了 go.server 专项 example validation 的 preserved provider impl 准备逻辑，避免 targeted validation 误把用户保留文件再生成成默认 scaffold。

验证命令：

```bash
.venv/bin/python -m py_compile src/api_blueprint/writer/golang/common.py src/api_blueprint/writer/golang/protos.py src/api_blueprint/writer/golang/route_view.py src/api_blueprint/writer/golang/toolchain.py scripts/example_validation/workspace.py scripts/example_validation/constants.py
.venv/bin/python -m pytest tests/codegen/go/server/test_enum_types.py tests/codegen/go/server/test_http_adapter.py tests/codegen/go/server/test_path_params.py tests/codegen/go/server/test_binary_schema.py -q
.venv/bin/python -m pytest tests/codegen/go/server -q
.venv/bin/python -m pytest tests/codegen/wails -q
.venv/bin/python -m pytest tests/scripts/test_example_validation_structure.py -q
make example-refresh-go-server
make example-refresh-wails
make example-validation-go-server
make example-validation-wails
```

验证结果：

- Go server codegen 测试通过，覆盖 typed enum DTO、`oneof` binding tag、无 enum route 不导入 `_gen_enums`、numeric/string enum wire 行为，以及同名 `REQ_List_QUERY` 场景下 route-local inline enum 仍生成 `_gen_enums` type。
- Go server 和 Wails example validation 通过。Wails validation 仍输出环境级 npm/ld warning，但命令 exit code 为 0。

相关 commit / PR：

- 待提交。
