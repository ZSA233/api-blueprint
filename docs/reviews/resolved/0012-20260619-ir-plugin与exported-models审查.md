# ir-plugin 与 exported models 审查

## 状态

已修复。

## 发现日期

2026-06-19

## 背景

`v2.0.5..HEAD` 新增了 `ir-plugin` target、`message_variant(..., metadata)` 和 `Blueprint.EXPORT_MODELS(...)`。这些能力把项目自定义生成物接入 ContractGraph，因此 manifest 的引用完整性、JSON 可序列化边界、CLI/文档可发现性会直接影响插件生成和发布质量。

## 风险分级

中。问题不影响普通 route 的主生成器路径，但会影响使用 standalone DTO、消息 metadata 或 IR plugin 的项目，可能导致 manifest 出现悬空 schema 引用、写 full contract 时才暴露序列化失败，或用户无法从配置文档完成接入。

## 问题性质

ContractGraph manifest 完整性缺口、扩展 metadata 校验缺口、用户可见配置文档缺口。

## 存在性判断

已确认。

- 当两个通过 `EXPORT_MODELS` 导出的模型同名但来自不同模块/作用域时，后出现的模型会触发 schema ref rewrite；现有 `_replace_schema_ref` 只更新 routes 和 schemas，不更新 `exported_models`，导致先导出的 `exported_models[].model` 指向已不存在的 schema key。
- `message_variant(..., metadata)` 直接把 `dict(metadata)` 写进 route manifest，未做 JSON-safe 校验。`Path` 等非 JSON 值可以进入 `to_manifest()`，到 `json.dumps()` 或插件 `write_json()` 时才失败。
- README 已声明 `IR plugin` target，但 `docs/zh/configuration.md` 和 `docs/en/configuration.md` 没有补 `ir-plugin` 配置示例、`plugin` / `options` 字段说明，也未说明没有快捷表时应使用 canonical `[[targets]]`。

## 复现场景

### exported_models 悬空引用

```python
from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Model
from api_blueprint.engine.model import String

PayloadA = type("Payload", (Model,), {"__module__": "pkg.a", "value": String(description="a")})
PayloadB = type("Payload", (Model,), {"__module__": "pkg.b", "value": String(description="b")})

bp = Blueprint(root="/api")
bp.EXPORT_MODELS(PayloadA, domain="a")
bp.EXPORT_MODELS(PayloadB, domain="b")
bp.GET("/ping").RSP(message=String(description="ok"))

manifest = build_contract_graph([bp]).to_manifest()
missing = [item["model"] for item in manifest["exported_models"] if item["model"] not in manifest["schemas"]]
assert missing == ["Payload"]
```

### message variant metadata 非 JSON-safe

```python
import json
from pathlib import Path

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Model, message_variant
from api_blueprint.engine.model import String

class ServerMessage(Model):
    value = String(description="value")

class ClientMessage(Model):
    value = String(description="value")

bp = Blueprint(root="/api")
bp.CHANNEL("/chat").SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(
    "ClientUnion",
    input=message_variant(ClientMessage, path=Path("x")),
)

manifest = build_contract_graph([bp]).to_manifest()
json.dumps(manifest)  # TypeError: Object of type PosixPath is not JSON serializable
```

## 影响范围

- `api-gen manifest --profile full`、contract target `formats = ["json"]`、contract shards 或插件 `context.write_json(...)` 可能在较晚阶段失败。
- IR plugin 读取 `contract_graph.to_manifest()["exported_models"]` 时可能拿到无法在 `schemas` 中解析的模型名。
- 使用同名 DTO 的多模块项目、插件专属 DTO、push payload 或缓存快照场景更容易触发。
- 新用户从 README 跳到配置说明时看不到完整 IR plugin 配置方法。

## 兼容性 / 修复风险

修复应是向后兼容的：

- `_replace_schema_ref` 追加更新 `self.exported_models` 中的 `"model"` 字段即可闭合引用，不改变普通 schema collision 策略。
- message variant metadata 可复用 exported model/provider 的 JSON-safe 转换逻辑；非 JSON-safe 值应在 ContractGraph 构建或 manifest 生成时给出明确错误。
- 文档补齐不影响运行时行为。

主要风险是错误信息和校验时机可能变化；如果已有插件依赖非 JSON metadata 对象，应明确把 metadata 定位为 manifest 字段，只接受 JSON-safe 值。

## 是否建议修复

建议修复。`exported_models` 是新增公开 manifest 字段，悬空引用会破坏插件读取契约；metadata 如果允许非 JSON 值，会违背 ContractGraph manifest 可序列化的基本假设。

## 后续处置建议

- 给 `ContractGraphBuilder` 增加 exported model schema rewrite 覆盖，并补同名 standalone model 测试。
- 给 `message_variant` metadata 增加 JSON-safe 校验或在 `_message_manifest` 使用统一转换 helper，并补非 JSON metadata 失败测试。
- 补齐 `docs/zh/configuration.md` / `docs/en/configuration.md` 的 `ir-plugin` canonical 配置示例和字段说明；如保留 `api-gen explain-target`，建议显示 `options`。
- 修复完成后移动到 `docs/reviews/resolved/`，追加 Resolution、验证命令以及相关 commit/PR。

## 修复记录 / Resolution

修复日期：2026-06-19

修复摘要：

- `ContractGraphBuilder._replace_schema_ref` 会同步更新 `exported_models`，避免同名 standalone model schema identity rewrite 后产生悬空引用。
- `message_variant(..., **metadata)` 复用 JSON-safe 校验，非 JSON 可序列化 metadata 会在 ContractGraph 构建时抛出明确 `ValueError`。
- `TargetConfig.options` 在配置加载阶段校验 JSON 可序列化；`api-gen explain-target` 会展示 `ir-plugin` 的 `options`，空配置显示 `{}`。
- 中英文 configuration 文档补齐 `ir-plugin` canonical target 示例、字段说明与 metadata/options JSON-safe 约束；README / README_EN / PRE_README 同步入口说明和事实基线。

验证命令：

```sh
.venv/bin/python -m pytest tests/application/test_ir_plugin.py tests/engine/test_connection_dsl.py tests/cli/config/test_targets.py tests/cli/apigen/test_inspect.py -q
.venv/bin/python -m pytest -q
```

验证结果：targeted regression 50 passed；full suite 493 passed.

相关 commit/PR：当前工作区未提交。
