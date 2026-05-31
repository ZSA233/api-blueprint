# Rootless Blueprint 逻辑身份碰撞审查

- 状态：resolved
- 发现日期：2026-05-31
- 背景：实践中存在同一个应用协议被拆到多个顶层 URL namespace 的旧定义习惯，例如 `/account` 与 `/room` 属于同一 app。当前绕法是 `Blueprint(root="")` 后在 `group()` 中声明顶层路径。
- 风险分级：高
- 问题性质：协议契约与生成物可用性风险

## 存在性判断

问题真实存在。当前 `Blueprint(root="")` 首次创建共享 FastAPI app 时会用空字符串作为 title，触发 FastAPI 断言。显式传入 app 后，URL 拼接可生成 `/account/...`、`/room/...`，但 ContractGraph 与多端 writer 会把空 root 归一为 `root`，导致协议身份、服务 ID、生成目录和部分 binding 表存在碰撞或缺失风险。

## 复现场景

- `Blueprint(root="")` 且不传 `app`，如果它是第一个共享 app，构造阶段失败。
- `Blueprint(root="")` 与 `Blueprint(root="/root")` 共存时，route id 和生成目录都可能落到 `root.*`。
- `Blueprint(root="").group("/root")` 与 root group 可能形成相同 group slug，TypeScript/Go 等生成器可能覆盖或生成不可编译代码。
- Wails v3 binding manifest 会跳过空 root，前端运行时查不到绑定 key。
- `Blueprint(root="").group("/api")` 与 `Blueprint(root="/api")` 可能生成相同 HTTP method+URL。

## 影响范围

- Engine/FastAPI 默认 app 构造
- ContractGraph service/route identity
- Go / TypeScript / Python / Kotlin / Java / Flutter / Swift / gRPC / Wails 生成目录、包名、facade、连接事件和错误索引
- examples 快照与 conformance 覆盖

## 兼容性 / 修复风险

修复会新增 `Blueprint(name=...)` 作为逻辑身份。非空 `root` 默认继续使用现有 root slug，保持既有 `/api` 等 route id 与生成目录。裸 `root=""` 不再提供隐式 fallback；rootless blueprint 必须显式提供 `name`。旧 Swift 项目如需保留 `APIRoutes` / `APIRootClient` / `api` 入口形态，应迁移为 `Blueprint(name="api", root="")`。

显式拒绝重复 route id 和重复 HTTP method+URL 可能暴露既有隐藏冲突，属于有意的失败前移。

## 是否建议修复

建议修复。该问题影响协议契约稳定性、生成物可用性和多端一致性，且旧协议定义习惯需要正式支持路径。

## 后续处置建议

- 增加 `Blueprint(name=..., root=...)`，将 `root` 收敛为 URL prefix，将 `name` 作为协议与生成身份。
- ContractGraph 和 writer 统一使用逻辑 root slug。
- 在 ContractGraph 构建阶段拒绝重复 route id、重复 method+URL 和会造成生成身份碰撞的 root/group 组合。
- 修复 Wails v3 rootless binding manifest。
- 将 rootless 多 group 用法加入主 examples，并刷新多端快照。
- 补 engine、contract、codegen 与 examples 验证。

## 修复记录 / Resolution

- 修复日期：2026-05-31
- 修复摘要：
  - 新增 `Blueprint(name=..., root=...)` 逻辑身份，`root` 保持 URL prefix 语义；非空 root 默认逻辑名保持旧行为，裸 `root=""` fail fast 并要求显式 `name`。
  - 曾评估过裸 `root=""` 使用 `rootless` 作为兼容 fallback，但该方案会让旧 Swift 消费面从 `APIRoutes` / `APIRootClient` / `api` 漂移到 `RootlessRoutes` / `RootlessRootClient` / `rootless`；最终采用破坏性更新，由用户显式写 `Blueprint(name="api", root="")` 保留旧 Swift layout。
  - ContractGraph、route id、FastAPI operation id 与各端 writer 统一使用逻辑 root slug，并在生成前拒绝重复逻辑 root、重复 route id、重复 HTTP method+URL 和 root/group 生成面碰撞。
  - 修复 Wails v3 rootless binding manifest，保留 `/account/...`、`/room/...` 等 rootless URL path。
  - 新增 rootless 多 group 示例，刷新 Go、TypeScript、Python、Kotlin、Java、Flutter、Swift、gRPC、Wails 示例产物和文档说明。
- 验证命令：
  - `uv run pytest tests/engine tests/contract tests/codegen -q`
  - `uv run api-gen check -c examples/api-blueprint.toml`
  - `uv run python scripts/example_validation.py --mode refresh --scope blueprint`
  - `uv run python scripts/example_validation.py --mode check --scope blueprint`
  - `uv run python scripts/example_validation.py --mode check --scope grpc`
- 相关 commit/PR：N/A（本地工作区待提交）
