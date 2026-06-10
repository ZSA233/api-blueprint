# Examples 验证

`examples/` 同时承载 Blueprint、Flutter、Wails、Kotlin、Java 与 gRPC 的公开示例。多数示例目录是生成快照，不应手写业务逻辑。

## 真源与快照

- `examples/blueprints/`：Blueprint 真源。
- `examples/api-blueprint.index.json`：轻量接口目录快照；日常理解项目时优先用 `api-gen inspect` 按需查询，完整 contract、agent 与 shards 快照是可选输出，主要用于离线导航、归档和 drift 验证。
- `examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/flutter/`、`examples/kotlin/`、`examples/java/client/`、`examples/java/server/`、`examples/python/`：Blueprint 生成快照。
- `examples/golang/conformance/`、`examples/typescript/conformance.ts`、`examples/kotlin/conformance/`、`examples/java/conformance/`、`examples/python/conformance/`、`examples/flutter/test/conformance_test.dart`、`examples/swift/Conformance/`：手写 preserved conformance harness，用于调用生成物并连接真实服务端；刷新生成快照时必须保留。
- `examples/java/suite/`：手写 Gradle Java 17 application，用于运行 generated Java client 与 Java Spring controller/delegate artifacts 的 compile/smoke。
- `examples/java/spring-server/`：手写 Spring Boot 宿主示例，实现 generated `java-server` delegate 并运行 `GenSpringMvcContractAssertions`。
- `examples/wails-harness/v2/`、`examples/wails-harness/v3/`：手写最小 Wails harness，消费共享生成产物。
- `examples/wails-hello/`：独立 Wails v3 hello 示例；`blueprints/` 是真源，`golang/` 与 `typescript/` 是生成快照，`app/` 是手写 Wails app shell。
- `examples/grpc/protos/`、`examples/grpc/go/`、`examples/grpc/python/`：`grpc-proto`、`grpc-go` 与 `grpc-python` targets 从 ContractGraph 生成的 proto、Go stub 和 Python stub 快照。

## 常用命令

```sh
make example-compile-check
make example-refresh
make example-validation
make example-conformance
make example-golang-suite
make example-java-suite
make example-java-spring-server
make wails-hello-compile-check
make wails-hello-check
```

- `example-compile-check`：功能开发期使用，允许 snapshot drift，只验证重生成产物仍可编译或导入。
- `example-refresh`：接受预期生成变化，刷新仓库里的 snapshots。
- `example-validation`：严格模式，要求本地生成器输出与已提交 snapshots 收敛。
- `example-conformance`：真实协议互通验证；它在临时 workspace 重生成 examples，检查 snapshot drift 和语言编译，再按 server/client/scenario 能力交集启动真实服务端并运行客户端。
- `example-golang-suite`：手动端到端增强验证；它在临时 workspace 重生成 Go server/client，启动真实 Go server 进程，再通过 generated Go client 和原生 HTTP binary 请求验证回路。它不接入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- `example-java-suite`：手动 Java 增强验证；它在临时 workspace 重生成 `java.client` 与 `java.server`，运行 `examples/java/suite`，验证 generated Spring Controller、delegate、provider policy 注解、JavaBean request/response 类型、adapter helper 和 generated Java client 最小热路径。它不启动真实 Spring Boot server，也不接入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- `example-java-spring-server`：手动 Spring Boot 宿主验证；它检查并重生成 `examples/java/spring-server`，再运行宿主 `@SpringBootTest`，注入 `RequestMappingHandlerMapping` 并调用 generated contract assertions。
- `wails-hello-compile-check`：只验证独立 Wails hello 示例，允许 snapshot drift，适合快速开发验证。
- `wails-hello-check`：只严格验证独立 Wails hello 示例，包含重生成、snapshot drift、TypeScript、Go、`wails3 doctor` 和 `wails3 build`。

也可以直接使用脚本的 scope：

```sh
uv run python scripts/example_validation.py --scope wails-hello --mode check
uv run python scripts/example_validation.py --scope wails-hello --mode compile
uv run python scripts/example_validation.py --scope wails-hello --mode refresh
uv run python scripts/example_validation.py --scope blueprint --mode golang-suite
uv run python scripts/example_validation.py --scope blueprint --mode java-suite
make example-java-spring-server
```

## Conformance 互通验证

`scripts/example_conformance/` 是独立于旧 validation scope 的真实互通管理器：

```sh
uv run python -m scripts.example_conformance list
uv run python -m scripts.example_conformance generate --keep-workspace
uv run python -m scripts.example_conformance run --servers go,kotlin --clients typescript,flutter --scenario request-options,media-filename-edge,media-error
uv run python -m scripts.example_conformance check --servers go,java,kotlin,python --clients go,typescript,kotlin,flutter,swift,java,python
uv run python -m scripts.example_conformance refresh --servers go --clients go,typescript,kotlin,flutter
```

Makefile 对同一 CLI 做薄封装，便于快速选择矩阵：

```sh
make example-conformance-list
make example-conformance-run EXAMPLE_CONFORMANCE_SERVERS=go,kotlin EXAMPLE_CONFORMANCE_CLIENTS=flutter EXAMPLE_CONFORMANCE_SCENARIOS=request-options,media-filename-edge,media-error
make example-conformance-check EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all EXAMPLE_CONFORMANCE_SCENARIOS=rpc,binary
make example-conformance-refresh
```

- `list`：列出启用服务端、客户端 capability 和场景。
- `generate`：在临时 workspace 生成所有 examples 产物，不修改仓库。
- `run`：只跑真实互通，可用 `--servers`、`--clients` 与 `--scenario` 过滤；`--server` 仍可作为单服务端兼容快捷方式。
- `check`：临时生成、做 snapshot drift、编译/分析，再跑互通。
- `refresh`：刷新仓库 examples，然后做编译/分析和互通。
- `EXAMPLE_CONFORMANCE_SERVERS`：选择服务端矩阵项，默认 `go`；可设为 `all` 跑 Go / Java / Kotlin / Python server。
- `EXAMPLE_CONFORMANCE_CLIENTS`：选择客户端矩阵项，默认 `go,typescript,kotlin,flutter`；可设为 `all` 跑 Go / TypeScript / Kotlin / Flutter / Swift / Java / Python client，其中 Swift 需要可用 Swift toolchain 或设置 `API_BLUEPRINT_SWIFT_BIN`。
- `EXAMPLE_CONFORMANCE_SCENARIOS`：选择场景矩阵项，空值表示全部场景。
- `EXAMPLE_CONFORMANCE_SWIFT_RUNTIME_PROFILE`：选择 Swift conformance 临时 workspace 的 runtime profile，默认 `modern`；可设为 `ios14-compat` 验证 iOS 14 兼容 transport，不会刷新或提交第二套 Swift snapshot。
- `EXAMPLE_CONFORMANCE_KEEP_WORKSPACE=1`：对 `generate`、`run`、`check` 保留临时 workspace，便于排查失败。

`example-compile-check` 在 Swift toolchain 可用时会编译 `examples/swift` modern 快照、`examples/swift/Narrow`，并额外生成临时 `ios14-compat` Swift package 做 `swift build` smoke。需要验证 SwiftPM 在 iOS Simulator SDK 下也能构建时，可设置 `API_BLUEPRINT_SWIFT_IOS_SMOKE=1`；该检查依赖本机 `xcodebuild`，因此默认关闭。

conformance 成功时输出按阶段收敛为一行状态，例如生成、snapshot、编译和 server 启动；运行层级是 `server -> client -> setup/scenario`。每个 client 会先输出 `client/setup`，表示正在冷启动或准备测试执行环境，例如 Go build、TypeScript compile、`dart pub get` 或 Gradle `installDist`；之后每个 `client/scenario` 会逐项执行并在该项完成时立即输出结果。生成器、`dart pub get`、Gradle、`go test` 等详细输出默认隐藏。某个阶段失败时，runner 会把该阶段捕获到的 stdout/stderr 回放到 stderr；client 场景失败时还会回放当前 server log，便于直接定位服务端或互通问题。状态文本在 TTY 下自动着色；可用 `FORCE_COLOR=1` 强制开启，或用 `NO_COLOR=1` 关闭。

当前服务端矩阵启用 Go HTTP、Kotlin Ktor 与 Python FastAPI；Java server target 不再作为 conformance HTTP server 启动，`example-java-suite` 覆盖 generated Spring controller/delegate smoke，`example-java-spring-server` 展示真实 Spring Boot 宿主测试。客户端矩阵启用 Go、TypeScript、Kotlin、Flutter、Swift、Java 与 Python。runner 会按 server capability、client capability 和 scenario registry 的交集执行，暂不支持的组合必须写入 manifest 并输出 skipped 或显式 unsupported，不能静默漏测。Swift 覆盖 HTTP RPC、urlencoded、multipart media、binary_schema、bytes/file/byte_stream raw response、request options、typed error、命名/多 root、SSE、WebSocket 和单模型 channel 场景。TypeScript / Kotlin / Flutter / Swift 覆盖 SSE 和 WebSocket 真实互通；Java / Python client 暂以默认 transport 的 unsupported contract 覆盖长连接场景。

场景 registry 会把 DSL 覆盖类别映射到自动化用例：query/json/form/binary/raw/XML、static/no-envelope、request options header/timeout、media filename edge、raw media typed error、scalar、enum、map、deprecated、typed error、命名冲突、多 blueprint root、response envelope、binary response、audit-binary、SSE、WebSocket、单模型 channel 与第二个 binary schema。server-only safety probes 覆盖 bad JSON、bad query、malformed WebSocket frame、WebSocket early close 和 bad binary，目标是确认服务端不会 5xx 崩溃、进程退出或连接悬挂。

`docs/reviews/resolved/0001-20260521-examples-conformance安全审查.md` 记录了本轮安全审查闭环：高风险服务端稳定性项、Python strict DTO 和普通 examples conformance 覆盖缺口已经补齐；后续若发现新的生成器风险，应新建下一条 review 记录，不继续拖住已 resolved 的 0001。

## Drift 语义

snapshot drift 表示“本地生成器输出和已提交快照不一致”。它是变更信号，不自动等于 bug。

如果 drift 是预期行为：

```sh
make example-refresh
make example-validation
```

如果 drift 不是预期行为，应回到 writer、模板、DSL 或配置层修复，不要直接手改生成快照。

## 外部工具链

严格 examples 验证可能需要：

- `go`
- `go-enum`
- `npm`
- Dart SDK
- Java 17
- Gradle 或 `API_BLUEPRINT_GRADLE_BIN`
- Wails v2 CLI `wails` 或 `API_BLUEPRINT_WAILS_V2_BIN`
- Wails v3 CLI `wails3` 或 `API_BLUEPRINT_WAILS_V3_BIN`
- `protoc`
- `protoc-gen-go`
- `protoc-gen-go-grpc`
- `grpcio-tools`
- Python server WebSocket 运行时依赖 `websockets` 模块；项目开发环境通过 `pyproject.toml` 管理。

## 发布前要求

`make release-preflight` 必须包含严格 `make example-validation`。release branch CI 也必须跑严格 `example-validation`。进入发布前，所有预期 snapshot 变化都应已经通过 `make example-refresh` 接受并提交。
