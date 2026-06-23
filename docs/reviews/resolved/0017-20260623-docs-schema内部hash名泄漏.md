# Docs Schema 内部 hash 名泄漏

- 状态：已修复
- 发现日期：2026-06-23
- 修复日期：2026-06-23
- 风险分级：中
- 问题性质：文档可读性缺陷 / schema identity 边界泄漏 / 同名 schema 覆盖风险

## 背景

使用者反馈 `api-doc-server` 的 Swagger UI 中会展示类似 `RSP_Users_Envelope__cac74a1f2727`、`AdminMRecordUserInfo__15137d0db4ab` 的 schema 名。该 hash 是 Pydantic/OpenAPI 内部去重 identity，用于避免同名 DSL model 在 FastAPI OpenAPI 生成时冲突。

## 存在性判断

确认存在。复现中两个不同结构但同名的 route response item model 会导致：

- `/openapi.json` 的 `components.schemas` key 带 `__hash`。
- `$ref` 指向带 `__hash` 的 schema key。
- `Array[Model]` 字段 description 会包含 `[Model__hash]`。
- Protocol / AsyncAPI schema registry 之前用 clean title `setdefault`，存在同名不同结构 schema 被覆盖的风险。

## 影响范围

- OpenAPI / Swagger 展示可读性下降。
- 用户看到内部实现细节，误以为协议模型名包含 hash。
- 同名不同结构的连接协议 schema 在 protocol docs / AsyncAPI 中可能丢失。

## 修复记录 / Resolution

- 保留 Pydantic 内部 `Model__hash` identity，不改变冲突隔离机制。
- 在文档输出层统一生成 public schema name，并重写 `components.schemas` key、schema `title`、`$ref` 和包含内部名的 description。
- 同名不同结构 schema 使用稳定路径/方法/角色后缀，例如 `UserInfoApiAUsersGetResponse` / `UserInfoApiBUsersGetResponse`。
- `Array[Model]` / `Map[..., Model]` 字段 description 改用 DSL model display name，不再使用 Pydantic 内部 `__name__`。
- Protocol / AsyncAPI schema registry 改为按内部 schema key 保存，再统一 public remap，避免同名 schema 被 clean title 覆盖。

验证命令：

```bash
.venv/bin/python -m pytest tests/engine/test_schema.py tests/engine/test_docs_runtime.py -q
```

相关状态：本地修复，待提交。
