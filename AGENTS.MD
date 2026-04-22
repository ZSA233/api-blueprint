# api-blueprint AI Agent Guide

## 目的

本文件约束 AI agent 在 `api-blueprint/` 仓库中的开发、调试、测试与发布准备方式。

目标不是只把功能改出来，而是让改动同时具备以下特征：

- 可验证
- 可回退
- 低耦合
- 方便后续 AI 和人类继续维护

若某个场景未被单独覆盖，默认遵循：

- 优先最小必要改动
- 优先保留证据而不是堆补丁
- 优先清晰结构而不是隐式约定

## 基本原则

- 修复问题时，先区分“猜测性修复”和“已确认修复”。
- 任何影响公共行为的改动，都要同时补测试或补可验证的检查路径。
- 不要为了可能的未来需求引入长期复杂度。
- 临时排查代码在问题定位后必须明确保留还是删除。
- 代码组织既要服务人类维护，也要服务大模型上下文理解。

## 仓库职责边界

- `src/api_blueprint/engine/` 是蓝图 DSL、FastAPI/OpenAPI 语义和运行时组装层。
- `src/api_blueprint/writer/` 是代码生成层，负责 Go / TypeScript 输出，不负责 DSL 语义定义。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/` 是文档服务展示资源。
- `examples/blueprints/` 是示例蓝图真源。
- `examples/golang/` 与 `examples/typescript/` 是根据示例蓝图生成出的快照产物，不是手写业务源。

修改时必须遵守：

- 不要把 DSL 语义判断塞进 `writer/` 模板绕过 `engine/`。
- 不要手改 `examples/golang/` 或 `examples/typescript/` 的业务逻辑；如果模板、DSL 或示例配置变化导致产物变化，应重新生成并校验。
- 如果只想修复生成产物，先确认真实问题是在模板、writer 还是示例蓝图，而不是直接编辑快照。

## Blueprint 运行时规则

- `Blueprint(app=None)` 默认复用全局 `FastAPI` app；这属于项目既有行为。
- 如果需要拆分多个文档服务或多应用场景，必须显式传入 `app`，不要假设每个 `Blueprint` 默认独立。
- 涉及多蓝图测试时，应显式验证是否共享同一个 app，避免重复注册路由或误判行为。

## 文档维护规则

- `PRE_README.MD` 是 README 收束的事实基线。
- 只要改动影响用户可见能力、CLI、配置、生成目录、文档服务或发布方式，就必须先更新 `PRE_README.MD`。
- 然后再同步收束到：
  - `README.md`
  - `README_EN.md`
- `README.md` 与 `README_EN.md` 必须严格镜像：
  - 标题层级一致
  - 表格数量和顺序一致
  - 代码块数量和顺序一致
  - 提示项和限制说明一致
- `main.py` 与 `debug.py` 是本地辅助脚本，不属于对外公共文档主线，不应在 README 中当作正式接口推广。

## 发布规则

- 用户如果只说“发版”，AI agent 不应自行猜目标版本号；必须等用户明确给出版本号。
- 发布工作默认在冻结分支 `release/vX.Y.Z` 上完成，而不是直接在日常开发分支上打 tag。
- 进入正式发版准备前，必须先完成文档收束：
  - `PRE_README.MD`
  - `README.md`
  - `README_EN.md`
- 版本真源只允许通过：
  - `release-version.toml`
  - `src/api_blueprint/_version.py`
- 不要手改版本号散落文件。
- `make release-version-rc` / `make release-version-stable` 只负责切换版本真源与同步检查，不会自动创建 git commit 或 tag。
- release commit、git tag、push tag 必须按顺序显式执行，不要并行，不要把 tag 打到前一个提交上。
- 正式发布前必须先通过：
  - `make release-preflight RELEASE_TAG=...`
  - `make release-local RELEASE_TAG=...`
  - `make release-install-check RELEASE_TAG=...`
- push tag 前必须确认当前 release ref 的 GitHub Actions `CI` 已经全绿。
- stable `Release` workflow 的正式发布 job 必须绑定 GitHub `production` environment。
- 如果仓库启用了 `production` environment 的 required reviewers，AI agent 必须等待人工审核通过后，才允许 workflow 继续执行正式发布。
- 如果 stable 发布在进入审核前就被 GitHub 拒绝，并提示 tag 不允许部署到 `production`，优先检查 environment 的 branch/tag policy，不要先改 workflow。
- stable 发布完成后，远端 `stable` 分支必须同步到对应 stable tag 的提交。
- stable 发布完成后，`release/vX.Y.Z` 必须合并回 `main`，否则本次发布不算真正收束完成。

## 测试与验证规则

- 新增或修改公共行为时，至少补一类验证：
  - 单元测试
  - 打包/安装 smoke
  - release contract 校验
- 变更打包配置时，必须验证 wheel/sdist 是否包含：
  - `writer/templates/**/*`
  - `hub/templates/**/*`
  - `static/**/*`
- 变更 CLI 或配置行为时，至少跑一轮 `api-doc-server --help`、`api-gen-golang --help`、`api-gen-typescript --help` smoke。
- 变更 release 逻辑时，必须覆盖：
  - `release-version.toml` 解析
  - `_version.py` 同步
  - README / release 文档契约

## 结构优化规则

- 文件过大或职责混杂时，优先按逻辑边界拆分，而不是继续往同一文件堆逻辑。
- 入口文件应尽量薄，主要负责装配与对外暴露接口。
- 新增 Python 逻辑时，优先补足类型注解，减少后续 agent 推断成本。
- 不要为了内部兼容长期保留魔法中转层；公共接口需要兼容，内部实现不默认兼容。

## AI Agent 提交前自查

- 这次改动属于猜测性修复还是已确认修复？
- 改动是否足够小、足够局部、足够容易回退？
- 是否保留了可验证证据，而不是只留下结论？
- 如果触达用户可见行为，`PRE_README.MD` 和 README 是否已同步？
- 如果触达版本或发布流程，release contract 和测试是否已同步？
