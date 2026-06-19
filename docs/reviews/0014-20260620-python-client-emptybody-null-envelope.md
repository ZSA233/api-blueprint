# python client EmptyBody envelope data:null 解码问题

## 状态

待修复，继续跟踪。

## 发现日期

2026-06-20

## 背景

真实 HTTP envelope 接口成功时没有业务 data，但服务端仍会返回 envelope，且 `data` 为 `null`：

```json
{
  "code": 200,
  "msg": "success",
  "data": null
}
```

DSL 侧用零字段响应模型表达“没有业务响应体”，例如：

```python
.POST("/system/agreement/update")
.REQ(...)
.RSP(EmptyBody)
```

预期：对 envelope route，`data: null` 和 `data: {}` 都应视为成功空响应；不应把 `null` 当成普通对象解码失败。

## 风险分级

高。请求已经成功、服务端响应也符合业务 envelope，但 generated Python client 会在本地解码阶段抛错，导致 safe-write / update / delete 等真实成功操作被误判为失败。

## 问题性质

Python client response decode 语义缺口。ContractGraph 能正确表达响应模型是空对象；问题发生在 envelope 解包后的 route response decoder。

## 存在性判断

已确认。

当前 Python client 的 HTTP transport 对 `code_message_data` 成功响应会返回 envelope 的 data 字段：

```python
if payload.get(code_field) == response_envelope.get("success_code", 0):
    return payload.get(data_field)
```

当服务端返回 `data: null` 时，route client 得到 `payload = None`。但 route client 对响应模型仍生成普通 object decoder：

```python
return UpdateResponse.from_value(payload, "update.response")
```

零字段 DTO 的 `from_value()` 仍要求输入是 `Mapping`：

```python
if not isinstance(value, Mapping):
    raise TypeError(f"{path}: expected object")
```

因此 envelope 已正确解包为 `None` 时，会抛：

```text
TypeError: update.response: expected object
```

## 复现场景

最小复现：

```python
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Model

class EmptyBody(Model):
    pass

bp = Blueprint(root="/api")

with bp.group("/system/agreement") as views:
    views.POST("/update").RSP(EmptyBody)
```

生成 Python client 后，若 transport 对该 route 返回 `None`（等价于 envelope 成功响应 `data: null` 已被解包），调用 route method 会抛：

```text
TypeError: update.response: expected object
```

`data: {}` 当前可成功解码为空 DTO。

## 影响范围

- 主要影响 Python client。
- 高风险接口包括 update / delete / write / action 等成功时无业务 data 的 envelope route。
- 只应影响响应模型为空对象的 envelope route；普通对象、数组、primitive response 不应放宽校验。
- native / no-envelope route 不应自动套用 `null` 兼容规则，否则会把本应严格校验的裸 `null` 响应误判为成功空对象。

## 关联发现

评估时还发现 `RouteContractIndex` 在构造 `RouteResponseContract.envelope` 时使用了：

```python
runtime.response_envelope or NoEnvelope
```

部分 envelope class 可能是 falsy，导致 writer 退回 `NoEnvelope`。这会让 generated Python client 不解包 envelope，甚至可能掩盖本问题。修复时应把这类判断改成显式 `is not None`，并补一条自定义 envelope 不回退为 `NoEnvelope` 的测试。

## 兼容性 / 修复风险

建议修在 Python client decode 生成层，而不是 HTTP transport 层按 route path 做特殊判断。

可行方向：

- 给 `PythonRoute` 增加“enveloped empty object response”判断：response envelope kind 不是 `none`，response schema 是 `type=object` 且 fields 为空。
- 对这类 route 生成 `UpdateResponse.from_value({} if payload is None else payload, "update.response")` 或等价 helper。
- 保持 `data: {}` 成功。
- 对非空 object、array、primitive 继续严格解码。
- 对 no-envelope route 继续让裸 `null` 走原来的 strict object decoder。
- 同时修复 `runtime.response_envelope or NoEnvelope` 的 falsy envelope 回退问题，避免 envelope route 在 Python writer 中被错误当成 no-envelope。

兼容性风险较低。唯一行为变化是 envelope + 空对象响应的 `data:null` 从抛错变为成功返回空 DTO；这符合 DSL “无业务 data”的语义。

## 是否建议修复

建议修复，并在 `v2.0.6` 发版前处理。真实 safe-write smoke 已需要临时 shim，说明该问题已经影响生成客户端可用性。

## 后续处置建议

- 增加 Python client codegen / runtime 测试：envelope route + `EmptyBody` + `data:null` 返回空 DTO，不抛 `expected object`。
- 增加 `data:{}` 兼容测试。
- 增加 no-envelope + `EmptyBody` + 裸 `null` 仍抛 `expected object` 的测试。
- 增加非空 response model + envelope `data:null` 仍抛错的测试。
- 增加自定义 envelope class 不被 `or NoEnvelope` 误判的测试。
