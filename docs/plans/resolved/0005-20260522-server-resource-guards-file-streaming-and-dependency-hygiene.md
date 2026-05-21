# Server 资源守卫、文件流式与依赖卫生实施计划

## 状态

已实施并归档。

## 背景

`docs/reviews/0006-20260522-client-server安全并发裁剪与依赖风险审查.md` 确认了默认 server adapter 的中风险问题：

- 请求体、multipart、binary gzip 解压缺少统一生成级上限。
- Java Spring WebSocket 默认 origin 过宽、入站队列无界、异步执行器不可替换。
- Python SSE queue 无界。
- Java/Kotlin/Flutter/Python file part 默认以 bytes 为中心，容易让大文件路径落到内存。
- 部分 examples 缺少可重复依赖审计 lockfile。

## 目标

- 默认改为安全边界明确的 server adapter。
- multipart file part 迁移为 stream/file descriptor 优先，同时保留 bytes helper。
- 保留宿主项目放宽限制或替换 adapter 的逃生通道。
- 保守刷新示例依赖和 lockfile，不跨 major。
- 修复并验证后，将 0006 移动到 resolved。

## Server 安全默认

### Go HTTP

- 新增 `httptransport.ServerConfig`、`DefaultServerConfig()` 与全局设置入口。
- 默认值：
  - request body: `16 MiB`
  - multipart memory: `8 MiB`
  - single file: `32 MiB`
  - decompressed binary: `16 MiB`
- `ParseMultipartForm` 使用配置值。
- multipart file 超过上限返回错误。
- gzip binary decode 使用解压后限制。
- WebSocket 默认使用 coder/websocket 的 origin 校验，禁用 compression；通过 config 显式设置 `OriginPatterns` 或 `InsecureSkipVerify`。

### Java Spring

- 新增 `GenSpringServerConfig`。
- 默认：
  - SSE timeout: `30s`
  - WebSocket allowed origins: 空列表，保留 Spring 同源默认
  - inbound queue capacity: `256`
  - multipart single file: `32 MiB`
- 允许用户通过 Spring bean 或构造注入覆盖 config/executor。
- WebSocket 不再默认 `setAllowedOrigins("*")`。
- 入站队列改为有界，满时关闭连接。

### Kotlin Ktor

- 新增 `ApiServerConfig`。
- 默认：
  - multipart single file: `32 MiB`
  - binary body: `16 MiB`
  - WebSocket message: `1 MiB`
- `register*Routes` 增加 `config: ApiServerConfig = ApiServerConfig()`。
- binary/multipart/WebSocket decode 使用配置上限。

### Python FastAPI

- 新增 `ApiServerConfig` dataclass。
- `create_router(..., config=None)` 使用默认 config。
- 默认：
  - body: `16 MiB`
  - multipart file/part: `32 MiB`
  - SSE queue: `256`
  - WebSocket message: `1 MiB`
- 新增 per-group router factory 时同样接收 config。

## File Part 流式重构

- Java `GenApiFilePart` 支持 `InputStream` / `Path` / bytes，保留 `of(...)` 和 `readAllBytes()`。
- Kotlin `ApiFilePart` 支持 `InputStream` / bytes，保留 `fromBytes` 和 `readAllBytes()`。
- Flutter `ApiFilePart` 支持 `Stream<List<int>>` / bytes，保留 bytes helper。
- Python runtime file part 支持 `UploadFile` / file-like / bytes，保留 `read_all_bytes()`。
- Server multipart decoder 不再无条件把文件展开为 bytes；超过配置上限时拒绝。
- Client multipart encoder 支持 bytes 和 stream/file-like 输入。

## 依赖卫生

- Wails harness frontend 提交 lockfile，使 `npm audit --omit=dev` 可重复。
- Flutter example 提交 `pubspec.lock` 或按 app-like example 管理。
- Go server/gRPC 与 Wails runtime 仅做 patch/minor 范围保守刷新。
- 不跨 Spring / Vite / TypeScript major。

## 测试

- Go server：body limit、multipart limit、gzip decompressed limit、WebSocket origin/compression config。
- Java server：`GenSpringServerConfig`、无默认 `setAllowedOrigins("*")`、bounded queue、custom executor hook、multipart 413。
- Kotlin server：`ApiServerConfig`、binary/multipart/WebSocket message limit、stream file wrapper。
- Python server：`ApiServerConfig`、body/multipart/SSE queue/WebSocket limit、per-group router factory。
- Flutter/Java/Kotlin/Python：file part stream API 与 bytes compatibility helper。
- TypeScript/Python/Flutter：窄入口和裁剪断言。

## 验证命令

```bash
uv run pytest tests/codegen/shared tests/codegen/go tests/codegen/java tests/codegen/kotlin tests/codegen/python tests/codegen/flutter tests/codegen/typescript tests/codegen/wails -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
git diff --check
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope wails-hello
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope grpc
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_conformance run --servers go,java,kotlin,python --clients go,typescript,kotlin,flutter,java,python --scenario request-options,media,media-filename-edge,media-error,binary-response,audit-binary
```

## 归档标准

- 中风险默认行为已有安全配置或明确拒绝路径。
- file part 大文件路径不再默认强制 bytes 展开。
- examples 依赖审计可重复性补齐或有明确记录。
- `0006` 追加 Resolution 后移动到 `docs/reviews/resolved/`。
- 本计划移动到 `docs/plans/resolved/`。

## 实施记录

实施日期：2026-05-22

已完成：

- Go HTTP server 生成 `ServerConfig`，覆盖请求体、multipart memory、单文件、解压后 binary 上限，并把 WebSocket origin/compression 纳入配置。
- Java Spring server 生成 `GenSpringServerConfig`，移除默认 `setAllowedOrigins("*")`，使用有界入站队列、可注入 executor、可配置 SSE timeout，并对超大 multipart 返回 413。
- Kotlin Ktor server 生成 `ApiServerConfig`，对 binary、multipart file、WebSocket message 启用默认上限。
- Python FastAPI server 生成 `ApiServerConfig`，对 body、multipart、SSE queue、WebSocket message 启用默认上限，并补 per-group router factory。
- Java/Kotlin/Flutter multipart file part 已迁移为 stream/file descriptor 优先，保留 bytes helper；Python multipart client/server 支持 file-like / UploadFile 形态和大小上限。
- Wails frontend 与 Flutter example 提交 lockfile；Go、gRPC Go、Wails 依赖做保守 patch/minor 刷新。

验证：

```bash
uv run pytest tests/codegen/shared tests/codegen/go tests/codegen/java tests/codegen/kotlin tests/codegen/python tests/codegen/flutter tests/codegen/typescript tests/codegen/wails -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope wails-hello
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope grpc
```
