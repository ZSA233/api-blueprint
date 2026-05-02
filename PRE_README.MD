# API Blueprint README Fact Base

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

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/writer/`：Go / TypeScript / Kotlin / Wails 代码生成与 gRPC target/job 规划执行。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/`、`examples/typescript/`、`examples/kotlin/` 与 `examples/wails/`：Blueprint 生成产物快照。
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
- `examples/api-blueprint.toml` 是公开的共享示例配置，同时包含 Blueprint / Go / TypeScript / Kotlin / Wails / gRPC 示例段落；其中 `[[wails.targets]]` 指向 `examples/wails/*`，`[grpc]` 指向 `examples/grpc/*`。
- `scripts/example_validation.py` 是 examples 的官方验证入口，会同时验证 Blueprint / Wails / gRPC examples，执行“重生成 -> 快照比对 -> TypeScript 编译 -> Go 测试 -> Kotlin Gradle 编译 -> Python gRPC import smoke”闭环。
- Blueprint examples 的严格重生成依赖 `go-enum` 与 Gradle；gRPC examples 依赖 `protoc`、`protoc-gen-go`、`protoc-gen-go-grpc` 与 Python `grpcio-tools`。
- TypeScript 配置支持字面量 `base_url` 和原样表达式 `base_url_expr`；两者互斥，优先级为 `base_url_expr -> base_url -> upstream -> ""`。
- TypeScript 公开 WebSocket 客户端面已统一为 `ApiSocketBridge<ServerMessage, ClientMessage>`；HTTP 生成结果仍保留 `connect<Route>Raw()` 作为浏览器原生 `WebSocket` escape hatch，Wails 生成结果不暴露 raw `WebSocket`。
- Kotlin 配置支持 `[kotlin]`、`package`、`base_url`、`base_url_expr`、`include` 与 `exclude`；生成目标是 OkHttp + kotlinx.serialization Android 客户端，`base_url_expr` 与 `base_url` 互斥，接口裁剪由 include/exclude 明确控制。
- Wails 公开配置面使用 `[wails]` 与 `[[wails.targets]]`；每个 target 至少声明 `id`、`version = "v2" | "v3"`、`go_out_dir` 与 `typescript_out_dir`。
- `api-gen-wails` 公开 CLI 支持 `--list-targets`、`--target` 与 `--explain-target`。
- Wails Go 生成器保持业务 handler 名称与 `Method(ctx, req) (rsp, err)` 形态稳定，但生成的上下文已经切到 transport-neutral runtime，HTTP-only 行为通过专用 escape hatch 暴露。
- gRPC 公开配置面默认使用 `[grpc].source_root`、`[grpc].import_roots` 与 `[[grpc.targets]]`；`[[grpc.jobs]]` 仅保留为 legacy/raw mode。
- `[[grpc.targets]].id` 只负责选择 target；`source_root` 只负责 files 相对根和 `protoc` 工作根；`import_roots` 只负责 import 查找；`python_package_root` 只负责 Python 输出命名空间与生成代码 import 路径；`out_dir` 只负责最终生成目录。
- Go gRPC target 不再要求用户手填 `module` 或 `layout`；工具会从 `out_dir` 向上自动发现 `go.mod`、推导 module path，并校验选中的 proto `go_package` 与 `out_dir` 一致。
- Python gRPC target 默认仍按 source-relative 规则生成；设置 `python_package_root` 后，产物会稳定落在 `out_dir/<package_root>/...`，且生成代码内部 import 会统一走该包根。
- legacy/raw `[[grpc.jobs]]` 继续支持 `proto_root`、`include_paths`、`layout` 与 `module`，CLI 通过 `--job` / `--list-jobs` 调用。
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
6. Wails target 语义模型
7. gRPC 语义模型
8. Go target 与 module
9. Python source_root 与输出路径
10. 蓝图 DSL 示例
11. CLI 命令
12. 生成产物与仓库约束
13. 开发
14. 发布

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

- 项目是“Python DSL -> FastAPI/OpenAPI -> Go/TypeScript/Kotlin/Wails 代码生成器”加“已有 proto 树的 gRPC target 编译器”，并兼容 legacy/raw gRPC jobs。
- 当前公开 Go / TypeScript / Kotlin Android / Wails v2/v3 / gRPC；Java 仅为内部预留扩展位。
- Wails 公开配置使用 `[wails]` 与 `[[wails.targets]]`；target 必须显式声明 `id`、`version`、`go_out_dir` 与 `typescript_out_dir`。
- `api-gen-wails` 公开 CLI 支持 `--list-targets`、`--target` 与 `--explain-target`。
- Wails v3 在 README 中标记为 experimental，Wails v2 标记为 preview。
- TypeScript request/response client 公开方法签名在 HTTP 与 Wails 之间保持一致；WebSocket 公开面统一为 `ApiSocketBridge<ServerMessage, ClientMessage>`。
- HTTP TypeScript 生成结果保留 `connect<Route>Raw()` raw `WebSocket` escape hatch；Wails TypeScript 生成结果不暴露 raw `WebSocket`。
- Wails TypeScript 生成器直接面向公开运行时桥接 API：v3 使用 `window.wails.Call(...)` 与 events，v2 使用 `window.go...` 与 `window.runtime.EventsOn/EventsOff`，不依赖 Wails CLI 生成的 JS binding 目录作为输入。
- gRPC v1 不会从 Blueprint DSL 推导 proto；它只负责编排已有 `.proto` 目录树的编译。
- `api-gen-grpc` 可以只依赖 `[grpc]` 配置段，不要求 `[blueprint]`。
- TypeScript `base_url_expr` 会原样输出到生成代码；它与 `base_url` 互斥，且优先级高于 `base_url` 和 `upstream`。
- Kotlin `base_url_expr` 会原样输出到生成代码；它与 `base_url` 互斥，且优先级高于 `base_url` 和 `upstream`。Kotlin writer 第一版面向 JSON REST 客户端，暂不支持 WebSocket、form 与 binary route。
- Python gRPC target 依赖 `grpcio-tools`；Go gRPC target 依赖 `protoc`、`protoc-gen-go` 与 `protoc-gen-go-grpc`。
- README 主路径必须展示 `[grpc].source_root`、`[grpc].import_roots` 与 `[[grpc.targets]]`，而不是 `[[grpc.jobs]]`。
- `id` 只负责 target 选择；`source_root` 只负责 files 相对根与工作根；`import_roots` 只负责 import 查找；`out_dir` 只负责最终生成目录。
- Go gRPC target 会从 `out_dir` 向上自动发现 `go.mod`、推导 module path，并校验 proto `go_package` 与 `out_dir` 一致；公开配置不再要求 `module` 或 `layout`。
- Python gRPC target 默认仍按 source-relative 规则生成；设置 `python_package_root` 后，输出前缀改由包根决定。
- legacy/raw `[[grpc.jobs]]` 继续可用，并保留 `proto_root` / `include_paths` / `layout` / `module`。
- `api-gen-grpc` 公开 CLI 新增 `--list-targets`、`--target` 与 `--explain-target`；`--job` 与 `--list-jobs` 保留为 legacy/raw mode。
- `grpcio-tools` 保持为开发期依赖，不进入运行时安装依赖。
- `examples/blueprints/` 与 `examples/grpc/protos/` 是真源，`examples/golang/` / `examples/typescript/` / `examples/kotlin/` / `examples/wails/v3/` / `examples/wails/v2/` / `examples/grpc/go/` / `examples/grpc/python/` 是生成快照。
- `scripts/example_validation.py` 会在临时目录重生成 Blueprint / Wails / gRPC examples，并执行快照比对、`tsc --noEmit`、`go test ./...`、Kotlin Gradle `compileKotlin` 与 Python gRPC import smoke。
- `make example-validation` / `make example-refresh` / `make example-compile-check` 依赖 `tsc`、`go`、`go-enum`、Gradle（或 `API_BLUEPRINT_GRADLE_BIN`）、`protoc`、`protoc-gen-go`、`protoc-gen-go-grpc` 与 Python `grpc_tools`。
- snapshot drift 本身是“生成结果发生变化”的信号，不自动等于 bug；是否错误取决于这次变更是否预期。
- `make example-validation` 用于严格校验当前生成器与已提交 snapshots 完全一致。
- `make example-compile-check` 用于功能开发期，只检查重生成结果是否可编译。
- `make example-refresh` 用于接受预期变化并刷新已提交 snapshots；之后再用 `make example-validation` 确认仓库重新收敛。
- `make release-preflight` 必须包含严格的 `make example-validation`，因为进入发版前，预期变化应当已经被刷新并提交。
- 共享全局 app 是默认行为。
- GitHub-only 稳定安装入口是 `@stable`，不是固定 tag。
- stable 正式发布会经过 GitHub `production` environment 审批闸门。
- 发布流程和详细规范在 `docs/release-process.md`。
