# API Blueprint README Fact Base

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 基于同一份蓝图输出 Go 与 TypeScript 的代码快照。
4. 基于配置驱动的 job 编排，编译已有 `.proto` 目录树并输出 Go / Python gRPC 产物。

当前对外公开 Go、TypeScript 与 gRPC 生成器；`kotlin`、`java` 只保留内部扩展位。

## 仓库事实

- 包名：`api-blueprint`
- 当前对外 CLI：
  - `api-doc-server`
  - `api-gen-golang`
  - `api-gen-grpc`
  - `api-gen-typescript`
- GitHub-only 稳定安装入口固定为：
  - `git+https://github.com/zsa233/api-blueprint@stable`
- 版本真源：
  - `release-version.toml`
  - `src/api_blueprint/_version.py`

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/writer/`：Go / TypeScript 代码生成与 gRPC job 编排执行。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/` 与 `examples/typescript/`：Blueprint 生成产物快照。
- `examples/grpc/protos/`：gRPC 示例 proto 真源。
- `examples/grpc/go/` 与 `examples/grpc/python/`：gRPC 生成产物快照。
- `tests/`：单元测试、CLI 测试、codegen 测试、example 集成验证、打包与 release contract 测试。

## 运行时事实

- `Blueprint(app=None)` 默认共享一个全局 `FastAPI` app。
- 如果多个 `Blueprint` 没有显式传入 `app`，它们会被注册到同一个文档应用里。
- `api-doc-server` 默认通过配置文件加载 entrypoints 并启动文档服务。

## 文档与生成约束

- `PRE_README.MD` 是 README 收束基线。
- `README.md` 与 `README_EN.md` 需要严格镜像。
- 只要用户可见能力、CLI、配置、生成结果目录、安装方式或发布方式发生变化，就必须先更新本文件。
- `main.py` 与 `debug.py` 属于本地辅助脚本，不是公共发布接口。
- `examples/api-blueprint.toml` 是公开的共享示例配置，同时包含 Blueprint / Go / TypeScript / gRPC 示例段落；其中 `[grpc]` 指向 `examples/grpc/*`。
- `scripts/example_validation.py` 是 examples 的官方验证入口，会同时验证 Blueprint examples 与 gRPC examples，执行“重生成 -> 快照比对 -> TypeScript 编译 -> Go 测试 -> Python gRPC import smoke”闭环。
- `Makefile` 暴露三类 example 目标：
  - `example-validation`：严格模式，检测 snapshot drift
  - `example-compile-check`：允许 drift，只验证重生成产物能编译
  - `example-refresh`：接受预期变化，直接刷新仓库中的 snapshots
- `release-preflight` 必须显式执行 `example-validation`，而不是宽松模式。

## 推荐 README 结构

1. 项目概述
2. 支持的输出
3. 安装
4. 核心工作流
5. 配置文件
6. 蓝图 DSL 示例
7. CLI 命令
8. 生成产物与仓库约束
9. 开发
10. 发布

## 推荐发布口径

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

## README 必须覆盖的事实

- 项目是“Python DSL -> FastAPI/OpenAPI -> Go/TypeScript 代码生成器”加“已有 proto 树的 gRPC job 编译器”。
- 当前公开 Go / TypeScript / gRPC；Kotlin / Java 仅为内部预留扩展位。
- gRPC v1 不会从 Blueprint DSL 推导 proto；它只负责编排已有 `.proto` 目录树的编译。
- `api-gen-grpc` 可以只依赖 `[grpc]` 配置段，不要求 `[blueprint]`。
- Python gRPC job 依赖 `grpcio-tools`；Go gRPC job 依赖 `protoc`、`protoc-gen-go` 与 `protoc-gen-go-grpc`。
- `grpcio-tools` 保持为开发期依赖，不进入运行时安装依赖。
- `examples/blueprints/` 与 `examples/grpc/protos/` 是真源，`examples/golang/` / `examples/typescript/` / `examples/grpc/go/` / `examples/grpc/python/` 是生成快照。
- `scripts/example_validation.py` 会在临时目录重生成 Blueprint 与 gRPC examples，并执行快照比对、`tsc --noEmit`、`go test ./...` 与 Python gRPC import smoke。
- snapshot drift 本身是“生成结果发生变化”的信号，不自动等于 bug；是否错误取决于这次变更是否预期。
- `make example-validation` 用于严格校验当前生成器与已提交 snapshots 完全一致。
- `make example-compile-check` 用于功能开发期，只检查重生成结果是否可编译。
- `make example-refresh` 用于接受预期变化并刷新已提交 snapshots；之后再用 `make example-validation` 确认仓库重新收敛。
- `make release-preflight` 必须包含严格的 `make example-validation`，因为进入发版前，预期变化应当已经被刷新并提交。
- 共享全局 app 是默认行为。
- GitHub-only 稳定安装入口是 `@stable`，不是固定 tag。
- stable 正式发布会经过 GitHub `production` environment 审批闸门。
- 发布流程和详细规范在 `docs/release-process.md`。
