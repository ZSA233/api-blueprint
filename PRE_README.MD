# API Blueprint README Fact Base

## README 定位

`README.md` 与 `README_EN.md` 是用户入口页，不是完整参考手册。

README 只回答：

- 这个项目解决什么问题。
- 支持哪些生成目标。
- 如何安装。
- 如何用最小 Blueprint 与最小配置跑起来。
- 常用 CLI 是什么。
- 生成文件哪些由生成器拥有、哪些由用户拥有。
- 更详细的配置、Wails、gRPC、DSL、examples 验证与发布说明去哪里看。

详细语义、目录布局、迁移规则、provider pipeline、Wails socket bridge、gRPC target 推导、example drift 处理等内容必须放到 `docs/` 下的专题文档中，再由 README 链接过去。

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 基于同一份蓝图输出 Go、TypeScript、Kotlin Android 与 Wails v2/v3 的代码快照。
4. 基于配置驱动的 gRPC target 编排编译已有 `.proto` 目录树，并兼容 legacy/raw job 模式输出 Go / Python gRPC 产物。

当前对外公开 Go、TypeScript、Kotlin Android、Wails 与 gRPC 生成器；`java` 只保留内部扩展位。

## 仓库事实

- 包名：`api-blueprint`
- 当前对外 CLI：
  - `api-doc-server`
  - `api-gen-golang`
  - `api-gen-grpc`
  - `api-gen-kotlin`
  - `api-gen-typescript`
  - `api-gen-wails`
- GitHub-only 稳定安装入口固定为：
  - `git+https://github.com/zsa233/api-blueprint@stable`
- 版本真源：
  - `release-version.toml`
  - `src/api_blueprint/_version.py`

## 用户文档结构

README 应链接到以下用户文档：

- `docs/zh/getting-started.md` / `docs/en/getting-started.md`：完整快速开始。
- `docs/zh/configuration.md` / `docs/en/configuration.md`：配置文件字段说明。
- `docs/zh/blueprint-dsl.md` / `docs/en/blueprint-dsl.md`：Blueprint DSL 与模型写法。
- `docs/zh/generators.md` / `docs/en/generators.md`：Go / TypeScript / Kotlin 输出说明。
- `docs/zh/wails.md` / `docs/en/wails.md`：Wails target、overlay、bindings、provider hook、socket bridge。
- `docs/zh/grpc.md` / `docs/en/grpc.md`：gRPC targets、工具链、legacy jobs。
- `docs/zh/examples-validation.md` / `docs/en/examples-validation.md`：example refresh、validation 与 drift 语义。
- `docs/release-process.md`：发布流程。

`.plans/` 是内部实施记录，不作为 README 用户主路径。

## README 推荐结构

1. 项目概述
2. 支持的输出
3. 安装
4. 快速开始
5. 最小配置
6. 常用命令
7. 生成产物与用户文件
8. 深入文档
9. 开发
10. 发布

README 必须保持简洁。Wails 的 RouteExecutor、provider pipeline、Go/TypeScript 内部保留目录、gRPC module 推导等细节不应直接堆在 README 中。

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/writer/`：Go / TypeScript / Kotlin / Wails 代码生成与 gRPC target/job 规划执行。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/`、`examples/typescript/` 与 `examples/kotlin/`：Blueprint 生成产物快照；Wails overlay 直接生成在共享 Go / TypeScript 树里的相邻保留子目录中。
- `examples/wails-harness/v2/` 与 `examples/wails-harness/v3/`：repo-owned 的最小 Wails harness 示例工程；app shell 手写维护，但直接消费共享树里生成的 bind wrappers 与 TypeScript API 产物。
- `examples/wails-hello/`：独立 Wails v3 hello world 示例；包含自己的 Blueprint、生成快照和手写 Wails app shell，用于演示不开 HTTP 服务的 Wails-only GUI 闭环。
- `examples/grpc/protos/`：gRPC 示例 proto 真源。
- `examples/grpc/go/` 与 `examples/grpc/python/`：gRPC 生成产物快照。
- `tests/`：单元测试、CLI 测试、codegen 测试、example 集成验证、打包与 release contract 测试。

## README 必须覆盖的事实

- 项目是“Python DSL -> FastAPI/OpenAPI -> Go/TypeScript/Kotlin/Wails 代码生成器”加“已有 proto 树的 gRPC target 编译器”。
- 当前公开 Go / TypeScript / Kotlin Android / Wails v2/v3 / gRPC；Java 仅为内部预留扩展位。
- Wails v3 标记为 experimental，Wails v2 标记为 preview。
- `api-gen-wails` 依赖共享 `[golang]` 与 `[typescript]` 配置，并生成共享树相邻 overlay；旧 `go_out_dir` / `typescript_out_dir` 已废弃。
- Wails `frontend_mode = "external"` 只生成 API artifacts；外部 frontend 需要在挂载应用前加载 Wails runtime，可使用生成的 `ensureWailsRuntime()` helper。
- Wails 可以运行在不启动 HTTP 服务的 app shell 中；当前生成的共享 Go 契约层仍包含 HTTP/Gin 注册代码和依赖，这不是完全无 HTTP 依赖的生成模式。
- Wails hello 示例有独立短命令：`make wails-hello-dev` 手动启动，`make wails-hello-check` 严格验证，`make wails-hello-compile-check` 快速编译验证。
- gRPC v1 不会从 Blueprint DSL 推导 proto；它只编排已有 `.proto` 目录树。
- TypeScript `base_url_expr` 与 Kotlin `base_url_expr` 会原样输出到生成代码，并与 `base_url` 互斥。
- `examples/blueprints/` 与 `examples/grpc/protos/` 是真源；各 language examples 是生成快照。
- snapshot drift 是“生成结果发生变化”的信号，不自动等于 bug。
- `gen_*` 文件由生成器拥有；`impl_*` 和非 `gen_*` passthrough 文件是用户扩展点并在重生成时保留。
- `main.py` 与 `debug.py` 仅作为本地辅助脚本保留，不属于公共发布面。

## 文档维护规则

- 用户可见能力、CLI、配置、生成目录、安装方式或发布方式变化时，先更新本文件。
- 然后同步更新 `README.md` 与 `README_EN.md`，并保持二者标题层级、表格数量、代码块数量一致。
- 如果细节超过 README 的用户入口边界，优先新增或更新 `docs/zh/*` 与 `docs/en/*`。
- 发布流程细节继续维护在 `docs/release-process.md`。

## 发布口径

- 默认发布路线是 direct stable。
- 只有在用户明确要求时才走 RC。
- stable GitHub Release workflow 的正式发布 job 绑定 `production` environment，可配合 required reviewers 做人工审核。
- 发版前文档收束顺序固定为：
  - `PRE_README.MD`
  - `README.md`
  - `README_EN.md`
- 发布前检查主线命令：
  - `make example-compile-check`
  - `make example-refresh`
  - `make example-validation`
  - `make release-version-show`
  - `make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-local RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]`
