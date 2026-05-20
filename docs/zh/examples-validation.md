# Examples 验证

`examples/` 同时承载 Blueprint、Flutter、Wails、Kotlin、Java 与 gRPC 的公开示例。多数示例目录是生成快照，不应手写业务逻辑。

## 真源与快照

- `examples/blueprints/`：Blueprint 真源。
- `examples/api-blueprint.index.json`：轻量接口目录快照；日常理解项目时优先用 `api-gen inspect` 按需查询，完整 contract、agent 与 shards 快照是可选输出，主要用于离线导航、归档和 drift 验证。
- `examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/flutter/`、`examples/kotlin/`、`examples/java/client/`、`examples/java/server/`：Blueprint 生成快照。
- `examples/java/suite/`：手写 Gradle Java 17 application，用于运行 generated Java client/server 的核心 round-trip。
- `examples/wails-harness/v2/`、`examples/wails-harness/v3/`：手写最小 Wails harness，消费共享生成产物。
- `examples/wails-hello/`：独立 Wails v3 hello 示例；`blueprints/` 是真源，`golang/` 与 `typescript/` 是生成快照，`app/` 是手写 Wails app shell。
- `examples/grpc/protos/`、`examples/grpc/go/`、`examples/grpc/python/`：`grpc-proto`、`grpc-go` 与 `grpc-python` targets 从 ContractGraph 生成的 proto、Go stub 和 Python stub 快照。

## 常用命令

```sh
make example-compile-check
make example-refresh
make example-validation
make example-golang-suite
make example-java-suite
make wails-hello-compile-check
make wails-hello-check
```

- `example-compile-check`：功能开发期使用，允许 snapshot drift，只验证重生成产物仍可编译或导入。
- `example-refresh`：接受预期生成变化，刷新仓库里的 snapshots。
- `example-validation`：严格模式，要求本地生成器输出与已提交 snapshots 收敛。
- `example-golang-suite`：手动端到端增强验证；它在临时 workspace 重生成 Go server/client，启动真实 Go server 进程，再通过 generated Go client 和原生 HTTP binary 请求验证回路。它不接入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- `example-java-suite`：手动端到端增强验证；它在临时 workspace 重生成 `http.java` 所需 Java client/server，运行 `examples/java/suite`，启动真实 Spring Boot server，再通过 generated Java 17 JDK HTTP client 验证核心 RPC、binary、static 和 unsupported 回路。它不接入默认 `test`、`example-validation`、`release-preflight` 或 CI。
- `wails-hello-compile-check`：只验证独立 Wails hello 示例，允许 snapshot drift，适合快速开发验证。
- `wails-hello-check`：只严格验证独立 Wails hello 示例，包含重生成、snapshot drift、TypeScript、Go、`wails3 doctor` 和 `wails3 build`。

也可以直接使用脚本的 scope：

```sh
uv run python scripts/example_validation.py --scope wails-hello --mode check
uv run python scripts/example_validation.py --scope wails-hello --mode compile
uv run python scripts/example_validation.py --scope wails-hello --mode refresh
uv run python scripts/example_validation.py --scope blueprint --mode golang-suite
uv run python scripts/example_validation.py --scope blueprint --mode java-suite
```

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

## 发布前要求

`make release-preflight` 必须包含严格 `make example-validation`。release branch CI 也必须跑严格 `example-validation`。进入发布前，所有预期 snapshot 变化都应已经通过 `make example-refresh` 接受并提交。
