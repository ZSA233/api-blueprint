# gRPC

`api-gen-grpc` 编排已有 `.proto` 目录树的编译，不会从 Blueprint DSL 生成 proto/service。

## Target 模式

推荐使用 `[grpc]` 与 `[[grpc.targets]]`：

```toml
[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["commonpb/common.proto", "greeterpb/greeter.proto"]

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "grpc/python"
files = ["**/*.proto"]
python_package_root = "examplegrpc_pb"
```

- `id`：只负责 target 选择。
- `source_root`：解释 `files` 的相对路径，同时作为 `protoc` 工作根。
- `import_roots`：只补充 proto import 查找路径。
- `out_dir`：最终生成目录。
- `python_package_root`：只对 Python target 生效。

## CLI

```sh
api-gen-grpc -c api-blueprint.toml --list-targets
api-gen-grpc -c api-blueprint.toml --target go.*
api-gen-grpc -c api-blueprint.toml --explain-target go.greeter
```

## Go target

Go target 会从 `out_dir` 向上查找最近的 `go.mod`，解析 module path，并校验选中 proto 的 `option go_package` 与输出目录一致。

公开 target 配置不再要求手填 `module` 或 `layout`。

## Python target

Python target 默认按 source-relative 方式生成。

设置 `python_package_root` 后，生成结果会稳定落在：

```text
out_dir/<python_package_root>/...
```

生成代码内部 import 也会统一走该包根。

## Legacy jobs

`[[grpc.jobs]]` 仍然可用，但只作为 legacy/raw mode 保留。旧配置可继续通过：

```sh
api-gen-grpc -c api-blueprint.toml --list-jobs
api-gen-grpc -c api-blueprint.toml --job legacy.name
```

## 外部工具链

- Python target 需要 `grpcio-tools`。
- Go target 需要 `protoc`、`protoc-gen-go`、`protoc-gen-go-grpc` 在 `PATH` 中可用。
