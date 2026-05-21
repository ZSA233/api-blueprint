# Binary Response And File Filename Semantics Review

## 状态

v1 已实现，其他端待扩展。

## 发现日期

2026-05-21

## 背景

`docs/reviews/0002-20260521-media-raw-transport-extension.md` 已把 raw media 请求/响应纳入 ContractGraph，但仍有两个协议语义需要在继续铺开其他语言端前收束：

- `REQ_BINARY` 已能让客户端编码、服务端解码 Markdown Binary Schema 请求体，但还缺少对称的结构化二进制响应契约。
- `RSP_FILE(filename=...)` 容易被理解为强制文件名；实际更合理的语义是默认下载名，可被 service 返回值覆盖。

## 风险分级

高。

这两个语义都影响 ContractGraph manifest、生成物 public API、客户端解码和服务端编码。如果在 Java/Kotlin/Flutter 等端继续扩展后再调整，迁移成本会显著增加。

## 问题性质

协议契约语义缺口与命名歧义。

## 存在性判断

存在。

当前 binary schema 主要覆盖请求方向；raw response 只能表达不透明 bytes/file/stream，不能生成 typed packet 的服务端编码和客户端解码。`RSP_FILE` 当前 manifest 字段名为 `filename`，缺少“默认值，可覆盖”的显式语义。

## 复现场景

- 服务端需要返回 `AuditPacket` 这类 Markdown Binary Schema packet，客户端希望直接拿到 typed packet，而不是手动处理 bytes。
- 文件下载 route 默认建议文件名为 `media-report.xlsx`，但业务需要按日期、租户或请求参数返回动态文件名。

## 影响范围

- Blueprint DSL 与 OpenAPI 输出。
- ContractGraph response manifest。
- Go/Python/TypeScript v1 client/server 生成器。
- examples binary/media 场景与 conformance。
- 其他尚未实现语言端的 capability check。

## 兼容性 / 修复风险

- 新增 canonical `REQ_BINARY_SCHEMA` / `RSP_BINARY_SCHEMA`，保留 `REQ_BINARY` / `RSP_BINARY` 作为短别名。
- `RSP_BINARY_SCHEMA` 成功响应不走 JSON envelope；typed error 继续走 JSON envelope。
- `RSP_FILE(default_filename=...)` 是 canonical 写法，`filename=...` 保留为兼容 alias；两者同时给出且不一致时报错。
- 客户端只解析实际 `Content-Disposition`，不从 ContractGraph 默认文件名合成下载名。

## 是否建议修复

建议修复。

本项是 media/raw transport redesign 继续扩展到其他语言端前的前置语义收束。

## 后续处置建议

- Python、Go、TypeScript 的 binary response 编解码闭环和 filename 边界测试已完成。
- 其他语言端继续对 `binary_schema` response 明确 unsupported，直到对应 writer/runtime 补齐。
- 本文保留在 `docs/reviews/` 顶层，作为 Java/Kotlin/Flutter/Wails/gRPC 后续扩展前的语义基线；全部目标补齐后再移动到 `docs/reviews/resolved/`。

## 实现记录 / Implementation

实现日期：2026-05-21。

本轮完成：

- 新增 canonical DSL：`REQ_BINARY_SCHEMA(...)`、`RSP_BINARY_SCHEMA(...)`；`REQ_BINARY(...)` 与 `RSP_BINARY(...)` 作为短别名保留。
- ContractGraph response 支持 `kind="binary_schema"`，记录 binary schema manifest、`content_type`、`success_enveloped=false`、`streaming=false`、`download=false`。
- OpenAPI 对 binary schema response 输出 binary schema extension 与对应 content type。
- Python server/client、Go server/client、TypeScript client 支持 binary schema 成功响应的服务端编码和客户端解码；typed error 继续走 JSON envelope。
- `RSP_FILE(default_filename=...)` 明确为默认下载名；`filename=...` 保留为兼容 alias，两者冲突时报错；service 返回 filename 或显式 `Content-Disposition` 覆盖默认值，客户端只解析实际响应头。
- 示例新增 binary response route 与 media dynamic filename route，并扩展 conformance 覆盖。

验证命令：

```sh
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
uv run pytest tests/engine/test_binary_schema.py tests/engine/test_media_contract.py tests/contract/test_graph.py tests/codegen/test_python_codegen.py tests/codegen/test_typescript_codegen.py tests/codegen/test_golang_codegen.py tests/codegen/test_golang_client_codegen.py tests/codegen/test_shared_planning.py -q
uv run python -m scripts.example_conformance.cli run --servers go,python --clients go,typescript,python --scenario binary-response,media,audit-binary
uv run python -m scripts.example_validation --mode refresh --scope blueprint
```

验证结果：

- `compileall` 通过。
- `api-gen check` 输出 `ok`。
- 相关单测 `135 passed`。
- Go/Python server × Go/TypeScript/Python client 的 binary-response、media、audit-binary 互通通过。
- blueprint example refresh 已通过，刷新后的生成快照已纳入本次变更。
