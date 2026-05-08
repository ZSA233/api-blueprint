# API Blueprint README Fact Base

## README 定位

`README.md` 与 `README_EN.md` 是用户入口页，不是完整参考手册。

README 只回答：

- 这个项目解决什么问题。
- 支持哪些生成目标。
- 如何安装。
- 如何用最小 Blueprint 与最小配置跑起来。
- 常用 CLI 是什么。
- 更详细的配置、生成器、Wails、gRPC、DSL、examples 验证与发布说明去哪里看。

详细语义、目录布局、迁移规则、generator ownership、provider pipeline、Wails socket bridge、gRPC target 推导、example drift 处理等内容必须放到 `docs/` 下的专题文档中，再由 README 链接过去。

## 项目定位

`api-blueprint` 是一个面向 API 契约定义与多语言代码生成的 Python 项目。

主线能力是：

1. 用 Python DSL 定义 `Blueprint`、路由、请求模型、响应模型与错误结构。
2. 在运行时构建 FastAPI/OpenAPI 文档服务。
3. 从 Blueprint 构建唯一协议真源 `ContractGraph`，并通过 `api-gen inspect` 按需查询 routes、schema、errors 和 target artifacts；默认可输出轻量 `api-blueprint.index.json` 接口目录，帮助先定位 route，再用 inspect 查询细节；同时可选输出完整 JSON manifest、AI agent compact manifest、Markdown agent guide、contract shards 与 breaking-change diff。
4. 基于同一份 `ContractGraph` 和共享 planner / capability metadata 输出 Go server/client、TypeScript client、Kotlin Android client、Python client/server、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。

当前对外公开统一 `api-gen` 主命令；Go client 是 preview target，HTTP RPC 可用，legacy WS / STREAM / CHANNEL 先生成 transport-neutral surface 并由默认 HTTP adapter 返回明确 unsupported error。`api-gen check` 与各语言 writer 共享同一份 target capability metadata，避免 check 与生成器支持面漂移。Kotlin / Python / Go client 是新实现的生成器表面，文档应避免把它们描述为完全成熟的生产 SDK。gRPC 产物链路包含 `grpc-proto`、`grpc-go` 与 `grpc-python` targets，其中 Go/Python targets 只编译 protobuf/gRPC stub，不生成业务服务实现。`grpc-go` / `grpc-python` 也可省略 `proto` 并直接使用 `source_root` / `files` 编译手写 proto。

## 仓库事实

- 包名：`api-blueprint`
- 当前对外 CLI：
  - `api-doc-server`
  - `api-gen`
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
- `docs/zh/generators.md` / `docs/en/generators.md`：Go / TypeScript / Kotlin / Python 输出说明。
- `docs/zh/wails.md` / `docs/en/wails.md`：Wails target、overlay service、provider hook、socket bridge。
- `docs/zh/grpc.md` / `docs/en/grpc.md`：`grpc-proto`、`grpc-go`、`grpc-python` targets、proto/service 输出、工具链。
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
7. 深入文档
8. 开发
9. 发布

README 必须保持简洁。Wails 的 RouteExecutor、provider pipeline、Go/TypeScript 内部保留目录、gRPC module 推导等细节不应直接堆在 README 中。

## 结构事实

- `src/api_blueprint/engine/`：DSL、模型、Blueprint、路由与 FastAPI/OpenAPI 语义。
- `src/api_blueprint/contract/`：Blueprint -> ContractGraph 的协议 IR、manifest 与 diff。
- `src/api_blueprint/writer/`：Go / TypeScript / Kotlin / Python / Wails / gRPC proto 与 protoc-backed stub 代码生成。
- `src/api_blueprint/application/`：entrypoint 加载、项目装配、docs server 启动与 1.0 generator 调度。
- `src/api_blueprint/hub/` 与 `src/api_blueprint/static/`：文档服务 UI 资源。
- `examples/blueprints/`：示例蓝图真源。
- `examples/blueprints/api_demo.py`：包含 `STREAM` / `CHANNEL` 长连接 DSL 示例。
- `examples/golang/server/`、`examples/golang/client/`、`examples/typescript/` 与 `examples/kotlin/`：Blueprint 生成产物快照；Go server 的 `out_dir` 是生成包根，示例选择 `golang/server/views`，因此 route/provider/transport/error 产物位于 `views/routes/**`、`views/providers`、`views/transports/**`、`views/runtime/errors/**`，生成器不再隐式追加 `views`。Go client 按 `runtime/**`、`routes/<root>/<group...>/**`、`transports/http/**` 输出，Wails overlay 仍生成在 Go server / TypeScript transport 目录中。Kotlin 新布局按 `<package>/<root>/runtime/*`、`<package>/<root>/routes/<root>/<group...>/*`、`<package>/<root>/transports/http/*` 输出，旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 属于兼容清理对象。
- `examples/wails-harness/v2/` 与 `examples/wails-harness/v3/`：repo-owned 的最小 Wails harness 示例工程；app shell 手写维护，但直接消费共享树里生成的 Wails services 与 TypeScript API 产物。
- `examples/wails-hello/`：独立 Wails v3 hello world 示例；包含自己的 Blueprint、生成快照和手写 Wails app shell，用于演示不开 HTTP 服务的 Wails-only GUI 闭环。
- `examples/grpc/protos/`、`examples/grpc/go/` 与 `examples/grpc/python/`：gRPC proto 与 Go/Python protobuf/gRPC stub 输出快照。
- `tests/`：单元测试、CLI 测试、codegen 测试、example 集成验证、打包与 release contract 测试。

## 用户文档必须覆盖的事实

- 项目主链路是 `Blueprint -> ContractGraph -> shared target planner -> writers`；ContractGraph 是 Go / TypeScript / Kotlin / Python / Wails / gRPC proto 的唯一协议真源。
- Blueprint DSL 把长连接消息流作为与 RPC 并列的一等契约：`STREAM` 表示服务端持续推送，`CHANNEL` 表示双向消息通道；legacy `WS/RECV/SEND` 不属于 1.0 公共主线。
- `STREAM` / `CHANNEL` 使用 `OPEN`、`SERVER_MESSAGE`、`CLIENT_MESSAGE`、typed `CLOSE` 与 `ConnectionScope` 描述 transport-neutral 连接语义；多消息类型必须通过单个判别联合消息契约声明，避免多个裸 event 名。
- `operation_id` 是 RPC / `STREAM` / `CHANNEL` 的正式主线能力，用于稳定生成出来的 handler / client / transport 命名；它改变 operation-derived surface，但不改变 route id、path 或 ContractGraph 中的连接语义。
- 当前公开 target kind：`contract`、`go-server`、`go-client`、`typescript-client`、`kotlin-client`、`python-server`、`python-client`、`http-transport`、`wails-transport`、`grpc-proto`、`grpc-go`、`grpc-python`。
- AI agent 与人类维护者应优先使用 `api-gen inspect routes/route/files/schema/errors` 按需查询 ContractGraph，而不是先读生成物、完整 `contract.json` 或庞大的 `contract.d/`。`route` / `schema` 子命令必须支持一次传多个查询，`files` / `errors` 必须支持重复 `--route`，让 agent 能批量取得相关接口细节。`inspect` 只返回 live ContractGraph 查询结果，不暗示 shard 文件存在，也不返回默认 shard 路径；离线 shard 入口只存在于显式生成的 `api-blueprint.agent.json`、`api-blueprint.agent.md` 与 `api-blueprint.contract.d/`。默认 contract target 只生成轻量 `api-blueprint.index.json`，它只包含 service / route / target 目录和 inspect 命令模板，不内联 schema、error catalog、route artifact 或 shard 明细；完整 `api-blueprint.contract.json` 只在显式 `formats = ["json"]` 或 `api-gen manifest --profile full` 时生成，用于 diff、归档或兜底全量检查。Kotlin / Python 的 artifact/import 索引必须指向完整镜像 route path 的输出路径，例如 `routes/api/demo`；Python 不再使用 `routes/root` sentinel。
- ContractGraph 从 `Blueprint(errors=...)` 和 route `.ERR(...)` 收集语言无关 error catalog，manifest 稳定输出 error group、member key、code、message、`toast.key/default/level`，并在 route summary 中列出可见 error ids。DSL 中 `message` 是协议级默认说明，`Toast(key, default, level)` 是用户展示层兜底；生成器只输出 key/default/level，不生成内置多语言表或 `locales/*.json`。生成物会把 runtime 错误类型/helper 与静态 catalog 数据拆到独立 generated 文件，避免错误码增长后挤压运行时结构文件。业务 i18n 系统按 key 查找当前语言，客户端 helper 的展示优先级是服务端 `toast.text` 覆盖、外部 i18n、`toast.default`、`message`。服务端可用不可变覆盖返回动态 toast 文案；业务错误码不默认改变 HTTP status，也不默认把 `GeneralWrapper.code != 0` 转成异常。
- `manifest.version` 是 manifest schema 兼容版本，初始为 `1.0`；`manifest.generator.version` 来自包版本真源 `release-version.toml` / `src/api_blueprint/_version.py`，例如 `1.0.0`。
- Wails v3 标记为 experimental，Wails v2 标记为 preview。
- `api-gen generate` 从统一 `[[targets]]` 规划依赖；快捷表如 `[[contract]]`、`[[go.server]]`、`[[go.client]]`、`[[python.server]]`、`[[transport.http]]` 会在加载时 normalize 成 canonical targets。生成器拥有的文件会直接写出并记录进度，用户拥有的保留文件才使用 skip 语义。Wails target 只消费已规划的 server/client target 产物并生成 overlay/runtime/binding manifest。
- `api-gen explain-target --target <id>` 输出 effective target summary，而不是原始 TOML 片段；至少要显示当前 target kind 的关键字段和关键生效值，例如 contract target 省略 `formats` 时仍显示 `formats = ["index"]`，Wails target 需显示 `version`、`overlay_name`、`frontend_mode`、`include`、`exclude`。
- `api-gen check` 与 writer 共享 planner / capability metadata；Kotlin / Python 当前 capability 覆盖 `rpc`、`legacy_ws`、`stream`、`channel`，request kinds 覆盖 query/json/form/binary/open，response wrappers 覆盖 none/general/custom。
- Wails `frontend_mode = "external"` 只生成 API artifacts；外部 frontend 需要在挂载应用前加载 Wails runtime，可使用生成的 `ensureWailsRuntime()` helper。
- Wails target 保持 Go + TypeScript only；不要把 Kotlin / Python client 加入 Wails `clients`。
- Wails target 的 `include` / `exclude` 只裁剪 target overlay / facade；未选中 route 的 root 不生成 `transports/<overlay_name>`，但共享 Go / TypeScript 契约层仍完整生成。
- `[[targets]]` 是 canonical target 配置；快捷表会推导 `kind`，`id` 仍必填。`[[contract]]` 是 contract target 快捷表；快捷表中的 Python `module` 映射到 `python_package_root`，Kotlin `module` 映射到 `package`，Go `module` 保持 Go module。transport target 使用 `kind = "http-transport"` / `kind = "wails-transport"` 或 `[[transport.http]]` / `[[transport.wails]]` 并显式声明 `server` 与 `clients`；gRPC 可使用 `[[grpc.proto]]`、`[[grpc.proto.proto_files]]`、`[[grpc.go]]`、`[[grpc.python]]`，也继续兼容 canonical `[[targets]]`。
- Go client 输出为 `runtime/gen_*.go`、`routes/<root>/<group...>/gen_client.go`、`routes/<root>/<group...>/gen_models.go`、保留的 `client.go` façade，以及 `transports/http/gen_config.go` / `gen_transport.go` / 保留的 `client.go`。`base_url` / `base_url_expr` 只进入 HTTP transport config，不进入 route/runtime client。默认 HTTP adapter 实现 RPC query/json/form/binary 请求，连接类 route 返回明确 unsupported error 以便项目替换自定义 transport。
- Go server 的 `out_dir` 是生成包根，不再隐式追加 `views`；core 生成在 `<out_dir>/routes/**`，provider runtime 在 `<out_dir>/providers`，error runtime 与分组错误值生成在 `<out_dir>/runtime/errors/**`，HTTP/Wails adapter 在 `<out_dir>/transports/**`。如果项目需要 import path 包含 `/views`，应把 `out_dir` 显式设置为 `.../views`。TypeScript 输出为 `api/runtime/**`、`api/routes/**`、`api/transports/**`。
- Kotlin client 输出为 `<package>/<root>/runtime/*`、`<package>/<root>/routes/<root>/<group...>/*`、`<package>/<root>/transports/http/*`；第一个 `<root>` 是生成包分段，`routes/<root>/<group...>` 镜像真实 route path。Kotlin 通过 transport abstraction 生成 RPC、legacy WS、STREAM、CHANNEL route surface，支持 query/json/form/binary/open request kind 以及 none/general/custom response wrapper。内置 OkHttp adapter 以 RPC 为主，长连接 bridge 属于 preview surface，接入生产前必须用目标平台 smoke 或自定义 transport 验证。旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 是破坏性旧布局，不再作为文档入口。
- Python client/server 使用 `python_package_root` 作为包根；client 是 async-first，按 `<package_root>/<root>/runtime/*`、`<package_root>/<root>/routes/<root>/<group...>/*`、`<package_root>/<root>/transports/http/*` 输出；root-level route 直接位于 `routes/<root>`，不生成 `routes/root`。默认 httpx adapter 实现 RPC 请求，WS/STREAM/CHANNEL 暴露 bridge interface 但默认 adapter 明确要求自定义连接 transport；server 输出 route service contracts/stubs 与 FastAPI HTTP adapter scaffold。Python 生成器属于新实现表面，应按 preview 口径描述。
- Go `providers` 是生成包根下的全局 transport-neutral runtime，不按 root 拆分；需要按 root/route/transport 切换同名 provider 实现时，使用 route-scoped provider factory，用户自定义 hook 为 `SelectProvider(spec, handler)`，详见 `docs/*/generators.md`。
- Go HTTP adapter 不会覆盖 Gin handler 已经写出的响应；`HTTP_RAW_RESPONSE()` 表示 handler owns HTTP success response，只影响 HTTP adapter finalization。
- Wails 可以运行在不启动 HTTP 服务的 app shell 中；只声明 Wails target 时，Wails app 的 Go import graph 不需要包含 Gin HTTP adapter。
- Wails `STREAM` / `CHANNEL` 默认通过 session-scoped runtime events 实现，event name 只存在于 generated transport/runtime 内部；HTTP `STREAM` 映射到 SSE，HTTP `CHANNEL` 映射到带内部 envelope 的 WebSocket；默认 runtime 只完整支持 `ConnectionScope.SESSION`，`APP` / `TOPIC` 通过自定义 connection hub / manager 扩展。
- Go server 默认生成的连接 handler 仍保持 `not implemented`；仓库示例在用户拥有的 `examples/golang/server/views/routes/api/demo/impl.go` 中手写了 `STREAM` / `CHANNEL` 最小用法，展示 `Open()`、`Send()`、`Recv()`、typed `Close()` 与异常 `Abort()`。
- Wails hello 示例有独立短命令：`make wails-hello-dev` 手动启动，`make wails-hello-check` 严格验证，`make wails-hello-compile-check` 快速编译验证。
- gRPC proto 可由 `grpc-proto` target 从 ContractGraph 输出；`grpc-proto` 支持 `[[targets.proto_files]]` / `[[grpc.proto.proto_files]]` 规则，把 schema module/name 与 route path/id/service 映射到 proto file/package/go_package/service，让 Blueprint DSL 不需要写 `__proto_file__` / `__proto_package__` / `__proto_go_package__`。
- DSL 主线不承载 gRPC/proto/Go/TypeScript/Kotlin 等 target-specific metadata；稳定字段身份使用 `field(number, Field(...), optional=True)`，互斥选择使用 `choice="..."`，通用语义类型使用 `DateTime`、`JSONValue`、`AnyValue`。
- gRPC writer 把 `field()` 的 stable contract field id 映射为 proto field number，把 `choice` 映射为 `oneof`，把 `DateTime` / `JSONValue` / `AnyValue` 映射为 protobuf well-known types；legacy `proto_*` 仅作为迁移逃生口保留，不作为新 DSL 推荐写法。
- `grpc-go` / `grpc-python` targets 可以消费同配置内的 `grpc-proto`，也可以在省略 `proto` 时直接通过 `source_root` / `files` 编译手写 proto。仓库提交 `examples/grpc/protos/`、`examples/grpc/go/` 与 `examples/grpc/python/` 快照，用来展示实际 proto 与 Go/Python stub 产物；旧 raw proto targets/jobs 不属于 1.0 公共主线。
- TypeScript / Kotlin / Python 的 `base_url` / `base_url_expr` 只属于 HTTP transport adapter / factory 默认配置，不应出现在 transport-neutral route/runtime client 中；`base_url_expr` 会原样输出到生成代码，并与 `base_url` 互斥。
- `examples/blueprints/` 是 Blueprint 真源；各 language examples、`examples/api-blueprint.index.json`、可选 full contract/agent/shards 快照与 `examples/grpc/{protos,go,python}/` 是生成快照。主 Go 示例拆分为 `examples/golang/server` 与 `examples/golang/client` 两个 Go module。
- snapshot drift 是“生成结果发生变化”的信号，不自动等于 bug。
- Go / TypeScript / Python 的 `gen_*` 文件由生成器拥有；Kotlin 的 `Gen*.kt` 文件由生成器拥有，并带 `Code generated by api-blueprint; DO NOT EDIT.` header。`impl_*`、Python `client.py` / `service.py`、Kotlin 非 `Gen*` facade / extension 文件是用户扩展点并在重生成时保留。
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
