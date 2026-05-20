# API Blueprint README Fact Base

## 文档分层

`PRE_README.MD` 是 README 与用户文档收束的事实基线，不是直接面向用户的教程。它记录项目事实、文档边界和发版前文档检查项。

文档分层固定为：

- `README.md` / `README_EN.md`：首次用户入口页，只保留项目定位、安装、最小示例、目标概览和文档导航。
- `docs/zh/*` / `docs/en/*`：专题手册，承载 DSL、配置、生成器、二进制协议、Wails、gRPC、examples 验证等完整说明。
- `docs/release-process.md`：发布流程手册。
- `docs/plans/`：设计方案与实施记录，不作为 README 用户主路径。

README 只回答：

- 这个项目解决什么问题。
- 支持哪些生成目标。
- 如何安装。
- 如何用一个最小 Blueprint 与最小配置跑起来。
- 常用生成目标分别负责什么。
- 更详细的配置、生成器、Wails、gRPC、DSL、examples 验证与发布说明去哪里看。

README 不承载 changelog、设计记录、迁移说明、wire shape 细节、目录布局细节、generator ownership、provider pipeline、Wails socket bridge、gRPC target 推导、example drift 处理或单次需求的实现背景。

## README 推荐结构

1. 项目概述
2. 适合什么场景
3. 安装
4. 30 秒示例
5. 常用目标
6. 下一步文档索引
7. 开发和发布

README 必须保持简洁。新增公共能力时，README 最多增加入口级一句话或文档链接；详细事实必须先落到对应 `docs/` 专题页。

## 用户文档索引

README 应链接到以下用户文档：

- `docs/zh/getting-started.md` / `docs/en/getting-started.md`：完整快速开始。
- `docs/zh/configuration.md` / `docs/en/configuration.md`：配置文件字段说明。
- `docs/zh/blueprint-dsl.md` / `docs/en/blueprint-dsl.md`：Blueprint DSL、模型、请求、响应、错误和长连接写法。
- `docs/zh/binary-schema.md` / `docs/en/binary-schema.md`：Markdown Binary Schema、字段表、规则、生成输出与检查命令。
- `docs/zh/generators.md` / `docs/en/generators.md`：Go / TypeScript / Flutter / Kotlin / Java / Python 输出说明。
- `docs/zh/wails.md` / `docs/en/wails.md`：Wails target、overlay service、provider hook、transport bridge。
- `docs/zh/grpc.md` / `docs/en/grpc.md`：`grpc-proto`、`grpc-go`、`grpc-python` targets、proto/service 输出、工具链。
- `docs/zh/examples-validation.md` / `docs/en/examples-validation.md`：example refresh、validation 与 drift 语义。
- `docs/release-process.md`：发布流程。

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 从 Blueprint 构建唯一协议真源 `ContractGraph`。
4. 通过 `api-gen check`、`api-gen inspect`、`api-gen manifest`、`api-gen diff` 和 `api-gen generate` 检查、查询、归档和生成代码。
5. 基于同一份 `ContractGraph` 输出 Go server/client、TypeScript client、Flutter client、Kotlin client/server、Java client/server、Python client/server、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。

仓库事实：

- 包名：`api-blueprint`
- 对外 CLI：`api-doc-server`、`api-gen`；二者都支持 `--version` 查询当前包版本。
- GitHub-only 稳定安装入口：`git+https://github.com/zsa233/api-blueprint@stable`
- 版本真源：`release-version.toml`、`src/api_blueprint/_version.py`

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/contract/`：Blueprint -> ContractGraph 的协议 IR、manifest 与 diff。
- `src/api_blueprint/writer/`：Go / TypeScript / Flutter / Kotlin / Java / Python / Wails / gRPC proto 与 protoc-backed stub 代码生成。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/golang/`、`examples/typescript/`、`examples/flutter/`、`examples/kotlin/`、`examples/java/`、`examples/python/`、`examples/grpc/`、`examples/wails-*`：生成快照、preserved conformance harness、验证工程和示例 app shell。
- `scripts/example_conformance/`：examples 真实协议互通验证 CLI，第一阶段以 Go HTTP server 为服务端真源，驱动 Go / TypeScript / Kotlin / Flutter client。
- `tests/`：单元测试、CLI 测试、codegen 测试、example 集成验证、打包与 release contract 测试。

## DSL 与契约事实

- Blueprint DSL 把 RPC、`STREAM`、`CHANNEL` 作为同一套 route contract 中的一等能力。
- `STREAM` 表示服务端持续推送，`CHANNEL` 表示双向消息通道；长连接语义通过 `OPEN`、`SERVER_MESSAGE`、`CLIENT_MESSAGE`、typed `CLOSE`、`ConnectionScope` 与 `ConnectionDelivery` 描述。
- 多消息类型必须通过单个判别联合消息契约声明，避免多个裸 event 名。
- 具名 variant 消息联合在 Go、TypeScript、Flutter、Python、Kotlin、Java 中生成构造、解码或分发关键帧 helper，并保持 `{ type, data }` wire shape；Go server 额外为带具名 client message 的 `CHANNEL` 首次生成用户拥有的 `<leaf>_session.go` / `<leaf>_processor.go` / `<leaf>_error.go` scaffold，后续不覆盖；长连接 `Send`、`Close`、`Abort` 为 context-first API。详细使用方式放在 generators 专题文档，不写入 README 首页。
- Markdown Binary Schema 是 HTTP 二进制请求体的一等契约，route 使用 `.REQ_BINARY(path)` 绑定 Markdown schema。
- Binary schema metadata 可以写成裸 `key: value` 行，也可以包在 fenced code block 中改善 Markdown 渲染，两种写法解析等价。
- 同一个 route group 内允许多个 binary schema；packet 入口名保持稳定，schema 内部生成符号按 packet name 作用域输出，归一化后重名的 packet name 在生成阶段报错。
- Binary schema parser / writer 诊断路径使用 schema 原始 packet、section、object 和 field 名，并在错误发生后按嵌套上下文包装路径，避免成功路径为了诊断信息提前拼接完整 path。
- Binary schema 生成的公开字段名遵循目标语言习惯：Go / Kotlin / Java / Flutter 使用导出或 camelCase 字段，TypeScript / Python 保持贴近 wire/JSON 的 snake_case 字段；诊断路径仍使用 schema 原始字段名。
- 稳定字段身份使用 `field(number, Field(...), optional=True)`，互斥选择使用 `choice="..."`，通用语义类型使用 `DateTime`、`JSONValue`、`AnyValue`。
- `operation_id` 是 RPC / `STREAM` / `CHANNEL` 的稳定 operation 命名能力；它改变 generated operation surface，不改变 route id、path 或 ContractGraph 连接语义。

## Contract 与 CLI 事实

- 公开 target kind：`contract`、`go-server`、`go-client`、`typescript-client`、`flutter-client`、`kotlin-server`、`kotlin-client`、`java-server`、`java-client`、`python-server`、`python-client`、`http-transport`、`wails-transport`、`grpc-proto`、`grpc-go`、`grpc-python`。
- `api-gen check` 与 writer 共享 planner / capability metadata，生成前校验 target dependency、route kind、request kind 与 response envelope。
- `api-gen inspect routes/route/files/schema/binary-schema/errors` 是人类和 AI agent 查询 ContractGraph 的主入口；应优先按需查询，而不是先读生成物、完整 manifest 或 shards。
- 默认 contract target 生成轻量 `api-blueprint.index.json`；完整 JSON manifest、agent manifest、Markdown agent guide、contract shards 和 diff 通过显式命令或 formats/profile 生成。
- `manifest.version` 是 manifest schema 兼容版本；`manifest.generator.version` 来自包版本真源。

## Typed Error 与 Response Envelope 事实

- ContractGraph 从 `Blueprint(errors=...)` 和 route `.ERR(...)` 收集语言无关 typed errors。
- 全局 `errors` 保留完整定义表，`routes[].errors` 输出 route-oriented refs：`id/group/key/code/message/toast`。
- `id` 是公开协议错误身份，`code` 是业务码，可跨 group/route 复用；HTTP status 与业务 code 解耦。
- `ResponseEnvelope` 决定外部响应结构；默认 `CodeMessageDataEnvelope` 是 `{ code, message, data, error? }` 形态，`LegacyCodeMessageDataEnvelope` 保留严格 `{ code, message, data }` 形态，`OkDataErrorEnvelope` 显式选择 `{ ok, data/error }` 形态。
- 生成物公开错误 API 使用 `ApiError`、`ApiErrors`、`lookupApiError` / 语言惯用变体；catalog 字典不是用户主入口。
- 默认 Go / TypeScript / Flutter / Python / Kotlin / Java client transport 会按 envelope spec 自动还原 typed error，lookup 顺序为 `id`、`(route_id, code)`、global code fallback、unknown `ApiError`。

## 生成器事实

- 生成物 ownership 必须在 docs 中按长期规则描述：生成器拥有 `gen_*` / `Gen*` 文件，用户拥有保留的 facade、impl、service、client 扩展点。
- Go / Wails Go 生成物的 root/group 目录、Go import path 和 `package` 声明使用 Go-safe route package segment；URL、route path、selection/filter 语义不受影响。
- Go server 的 `out_dir` 是生成包根；route/provider/transport/error/binary runtime 按生成器布局输出，不隐式追加 `views`。
- Go client 输出 runtime、routes、transports/http、根 facade；推荐从 `apiclient.NewHTTP(...)` 进入。
- TypeScript client 输出 runtime、routes、transports，并通过 transport facade 注入 HTTP/Wails 能力。
- Flutter client 输出纯 Dart package：public entry 位于 `lib/<package>.dart`，实现位于 `lib/src/<root>/runtime`、`routes` 与 `transports/http`；`gen_*.dart` 由生成器覆盖，非 `gen_` facade、HTTP client facade 与 `api_json_codecs.dart` 作为 preserved scaffold 保留。默认 HTTP adapter 使用 `package:http`，STREAM 使用 SSE，CHANNEL 使用 `web_socket_channel`，不生成 Flutter UI、状态管理、鉴权、重试、缓存或 session engine。
- Flutter 采用 Dart package 输出布局；Kotlin / Java / Python 采用各自语言的 package-first 输出布局；这些 target 按 preview 口径描述，文档应要求使用方把生成结果纳入自身类型检查、lint、编译或 smoke。
- Kotlin client 使用 OkHttp + kotlinx.serialization；Kotlin server 使用 Ktor + kotlinx.serialization，生成 service contract/stub、HTTP RPC adapter 和协议关键帧 helper。Kotlin server 不生成 WebSocket/SSE/session engine；非 RPC 连接 route 的 Ktor adapter 返回明确 501。
- Java client 使用 Java 17 `HttpClient` + Jackson，Java server 使用 Spring MVC + Jackson；binary schema 会生成 typed packet writer / parser，server controller 会把 `.REQ_BINARY` body 解析为 typed packet 后交给 service；不生成 Gradle/Maven 工程，也不生成 JPMS `module-info.java`。
- Python client 是 async-first，推荐从 `create_client(base_url)` 聚合 facade 进入；Python server 输出 service contract/stub 与 FastAPI HTTP adapter scaffold。
- Wails target 保持 Go + TypeScript only；`frontend_mode = "external"` 只生成 API artifacts，外部 frontend 需要加载 Wails runtime。
- gRPC proto 可由 `grpc-proto` target 从 ContractGraph 输出；`grpc-go` / `grpc-python` 可消费同配置内的 `grpc-proto`，也可直接编译手写 proto。

## Examples 与验证事实

- `examples/blueprints/` 是 Blueprint 真源。
- 语言 examples、`examples/api-blueprint.index.json`、可选 full contract/agent/shards 快照与 `examples/grpc/{protos,go,python}/` 是生成快照；`examples/flutter/` 是纯 Dart package 快照，验证使用 `dart pub get`、`dart analyze` 和 `dart test`。
- examples DSL 覆盖 query/json/form/binary/raw/XML、typed error、命名冲突、多 blueprint root、stream、channel、SSE/WebSocket 等公开协议场景；暂不支持的端侧能力必须在 conformance manifest 中显式标注，不静默漏测。
- `scripts/example_validation.py` 负责 snapshot drift、refresh、compile/analyze/import smoke 和旧增强 suite；`python -m scripts.example_conformance` 负责真实互通验证。conformance 第一阶段只启用 Go HTTP server，Go / TypeScript / Kotlin / Flutter client 连接同一服务端；Kotlin 只覆盖 RPC/form/binary/typed-error/naming 等 HTTP 能力，长连接为显式 unsupported/contract 验证。
- conformance harness 位于各语言 preserved 文件中，例如 `examples/golang/conformance/`、`examples/typescript/conformance.ts`、`examples/kotlin/conformance/`、`examples/flutter/test/conformance_test.dart`，刷新生成物不得覆盖这些文件。
- snapshot drift 表示生成结果变化，不自动等于 bug。
- `make example-golang-suite` 和 `make example-java-suite` 是手动增强验证，不进入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- generator-owned artifact 的短期逃生口方案记录在 `docs/plans/generated-artifact-escape-hatches.md`：优先通过 preserved facade、transport hook、codec registry、raw body fallback 和 route wrapper 绕过，不在第一阶段做 template partial override 或 post-generate patch hooks。
- `main.py` 与 `debug.py` 是本地辅助脚本，不属于公共发布面。

## 文档维护规则

- 用户可见能力、CLI、配置、生成目录、安装方式或发布方式变化时，先更新本文件。
- 然后同步更新 `README.md` 与 `README_EN.md`，并保持二者标题层级、表格数量、代码块数量一致。
- 如果细节超过 README 的用户入口边界，优先新增或更新 `docs/zh/*` 与 `docs/en/*`。
- 用户文档应按长期概念组织，不按单次需求变更堆叠补丁式说明。
- 兼容、迁移、legacy 信息只放在明确的 `兼容性说明` / `Compatibility` / `Migration Notes` 段落中。
- 发布流程细节继续维护在 `docs/release-process.md`。

## 发布口径

- 默认发布路线是 direct stable；只有在用户明确要求时才走 RC。
- stable GitHub Release workflow 的正式发布 job 绑定 `production` environment，可配合 required reviewers 做人工审核。
- 发版前文档收束顺序固定为：
  - `PRE_README.MD`
  - `README.md`
  - `README_EN.md`
  - `docs/zh/*` / `docs/en/*`
- 发版前 editorial cleanup 固定检查：
  - README 是否仍像入门页，而不是专题手册。
  - docs 是否按主题结构承载细节，而不是散落单次变更说明。
  - 兼容/legacy 说明是否位于明确段落。
  - 中英文 README 与中英文 docs 对应专题是否保持结构和语义一致。
- 发布前检查主线命令：
  - `make example-compile-check`
  - `make example-refresh`
  - `make example-validation`
  - `uv run python -m scripts.example_conformance check --server go --clients go,typescript,kotlin,flutter`
  - 可选手动增强：`make example-golang-suite`
  - 可选手动增强：`make example-java-suite`
  - `make release-version-show`
  - `make release-preflight RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-local RELEASE_TAG=vX.Y.Z[-rc.N]`
  - `make release-install-check RELEASE_TAG=vX.Y.Z[-rc.N]`
