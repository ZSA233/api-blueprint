# 生产逃生通道与窄入口实施计划

## 状态

已实施并归档。

## 背景

`docs/reviews/resolved/0005-20260521-client-server生成物逃生通道与可用性审查.md` 已确认各端不存在因为 `Gen*` / `gen_*` 不可修改而导致的致命能力缺口，但仍有几类需要下落到长期文档和生成入口的优化：

- 默认 adapter 是协议落地样例，不是完整生产运行时。
- 生产项目应优先使用窄入口导入具体 route、transport、router，而不是总 barrel / aggregate facade。
- gRPC / Wails 的 deadline、metadata、IPC、权限和取消语义应继续走协议原生路径。

## 目标

- 在用户文档中明确 client/server 生成物的逃生通道：custom transport、原生 client 注入、service implementation、middleware/plugin/filter、preserved facade。
- 为 TypeScript HTTP/Wails transport 和 Python server 补更清晰的窄入口路径或测试证明。
- 保留现有 aggregate entrypoint，避免破坏已有 import。
- 将 0005 的后续修复记录追加到已归档 review。

## 实施内容

### 文档

- 先更新 `PRE_README.MD`。
- 同步 `README.md` / `README_EN.md` 的入口级说明。
- 更新 `docs/zh/generators.md` 与 `docs/en/generators.md`：
  - 推荐生产使用具体 route client、HTTP factory、server group router。
  - 标注 aggregate client/router/barrel 是发现能力和示例友好的入口，不是最窄依赖面。
- 更新 `docs/zh/configuration.md` 与 `docs/en/configuration.md`：
  - 说明 timeout、headers、原生 client、middleware、proxy、TLS、cookie、retry 等应通过 request options 或宿主 client 实现。
- 更新 `docs/zh/wails.md` / `docs/en/wails.md`：
  - 标注 Wails `timeoutMs` 只是前端等待超时，不取消 native invoke。
  - Wails v3 继续标记 experimental。
- 更新 `docs/zh/grpc.md` / `docs/en/grpc.md`：
  - gRPC 使用 native metadata、deadline、interceptor、stream backpressure。

### 窄入口

- TypeScript 保留 `transports/gen_clients.ts` 总入口。
- 强化 per-transport HTTP factory 文档和测试，证明 HTTP-only narrow import 不引用 Wails factory。
- Python server 新增 per-group router factory，允许只 include 实际部署 group；aggregate `create_router()` 继续兼容。

## 兼容性

- 不移除现有 aggregate client/server/barrel。
- 新增窄入口不改变 DSL、wire contract 或 route 方法签名。
- 文档会明确：如果项目需要完整生产策略，应该包一层或替换默认 adapter，而不是编辑生成文件。

## 验证

```bash
uv run pytest tests/codegen/typescript tests/codegen/python -q
uv run python -m compileall src/api_blueprint -q
git diff --check
```

完整实施计划会与资源守卫计划一起执行：

```bash
uv run pytest tests/codegen/shared tests/codegen/go tests/codegen/java tests/codegen/kotlin tests/codegen/python tests/codegen/flutter tests/codegen/typescript tests/codegen/wails -q
uv run api-gen check -c examples/api-blueprint.toml
```

## 归档标准

- 文档已说明生产逃生通道和窄入口推荐。
- TypeScript / Python 窄入口有 codegen 测试。
- `0005` 追加后续 Resolution。
- 本计划移动到 `docs/plans/resolved/`。

## 实施记录

实施日期：2026-05-22

已完成：

- `PRE_README.MD`、`README.md`、`README_EN.md` 已补充生产逃生通道与窄入口说明。
- `docs/zh|en/generators.md`、`configuration.md`、`wails.md`、`grpc.md` 已补充默认 adapter 边界、协议原生逃生通道和窄入口建议。
- Python HTTP server 已生成 per-group router factory，aggregate `create_router()` 保持兼容。
- TypeScript 已补充回归测试，验证 HTTP per-transport 窄入口不导入 Wails factory。

验证：

```bash
uv run pytest tests/codegen/typescript -q
```
