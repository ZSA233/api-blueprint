# Examples 质量、真流式 byte_stream 与生成物整洁性优化计划

## 状态

已完成并归档。

本计划承接 `docs/reviews/resolved/0004-20260521-examples覆盖性能能力缺口与生成物整洁性审查.md`，目标是在发布前闭环 examples 覆盖、benchmark 可用性、`byte_stream` 跨端语义和生成物整洁性。

## 背景

media/raw、binary response、生成物 ownership 与客户端 request options 已完成主路径实现，但审查发现仍有以下质量缺口：

- Java binary benchmark 仍引用旧 `Api*` / 非 `Gen*` 生成物命名。
- request options 目前主要靠 codegen 断言，缺少跨端运行级 conformance。
- media/raw 的 filename 与错误路径边界覆盖不足。
- `byte_stream` 在 Java/Kotlin/Flutter 中仍是 buffered 模型，和 Go/Python/TypeScript 的真流式语义不一致。
- TypeScript 等生成物存在多余空行，刷新 examples 时会产生无意义 diff 噪音。

人工确认后，本轮选择统一 `byte_stream` 为真流式语义，允许 Java/Kotlin/Flutter 出现 public API 破坏性调整。

## 实施范围

### Benchmark

- 修复 Java binary benchmark，使其使用 `GenBinaryTypes`、`GenApiBinaryBody` 与 `Gen*` runtime 文件。
- 增加 benchmark smoke 测试，至少覆盖：
  - `binary --target java --count 1`
  - `binary --target all --count 1`
- 保留 protocol benchmark 直打 server 的定位。
- 新增 generated client SDK benchmark/smoke，覆盖 request options、binary response、multipart/raw response 的最小热路径。

### Request Options Conformance

- 新增 `request-options` scenario，使用 generated clients 真实传递 default headers、per-call headers、global timeout、per-call timeout。
- 新增可控慢 route，例如 `/api/demo/request-options`：
  - 返回 header echo。
  - 支持 `delay_ms`。
  - 各 server harness 行为一致。
- 各 client harness 验证：
  - per-call header 覆盖 default header。
  - per-call timeout 能覆盖较短 global timeout。
  - 短 per-call timeout 对慢请求会失败。
- Wails 单独通过 generated transport/unit 测试确认 `timeoutMs` 只让前端 promise reject，不声明 native cancellation。

### 真流式 byte_stream

- Java：
  - `GenApiStreamResponse` 改为 `InputStream` / `AutoCloseable` wrapper。
  - 保留 `of(byte[], contentType)` 与 `readAllBytes()` 便利方法。
  - JDK client 对 `byte_stream` 使用 `BodyHandlers.ofInputStream()`。
  - Spring server 使用 streaming response body 写出，不再强制缓冲。
- Kotlin：
  - `ApiStreamResponse` 改为 chunk stream wrapper，使用 `Flow<ByteArray>` 或等价 closeable stream API。
  - 提供 `readAllBytes()`。
  - OkHttp client 不在 `execute` 中调用 `bytes()` 消费 stream。
  - Ktor server 通过 streaming writer 输出 chunk。
- Flutter：
  - `ApiStreamResponse.body` 改为 `Stream<List<int>>`。
  - 提供 `readAllBytes()`。
  - HTTP transport 对 `byte_stream` 直接返回 `StreamedResponse.stream`。
  - 非 stream 响应保持现有 buffered 解码。
- Go/Python/TypeScript 保持现有真流式方向，并补齐 conformance 对“只读首 chunk 后关闭/取消”的验证。
- 更新 MJPEG / byte stream conformance，避免依赖 Java/Kotlin/Flutter 全量 body。

### Media/raw 边界

- 新增 media filename edge route：
  - 返回 `Content-Disposition: attachment; filename*=UTF-8''...`。
  - 各客户端验证非 ASCII 文件名解析。
- 新增 raw/media error route：
  - raw success 不套 JSON envelope。
  - typed error 仍按 JSON envelope 被客户端识别。

### 生成物整洁性

- 清理 TypeScript `gen_client.ts.j2` 的 request object 空白控制。
- 无 request data 时生成紧凑签名，不产生空 object 内空行。
- 扫描 Java/Kotlin/Flutter/Python/TypeScript 生成物并增加格式 invariant：
  - 无尾随空白。
  - 无 3 个以上连续空行。
  - 关键 request block 不生成空洞。

### 文档与归档

- 用户可见行为变化先更新 `PRE_README.MD`。
- 再同步更新 `README.md` / `README_EN.md` 的入口级说明。
- 更新 `docs/zh|en/configuration.md`、`generators.md`、`examples-validation.md`。
- 完成后在 `docs/reviews/resolved/0004...` 追加 Resolution，并移动到 `docs/reviews/resolved/`。
- 本计划完成后移动到 `docs/plans/resolved/`。

## 验证计划

```bash
uv run pytest tests/codegen/shared tests/codegen/java tests/codegen/kotlin tests/codegen/flutter tests/codegen/typescript tests/codegen/python tests/codegen/go tests/codegen/wails -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
git diff --check
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope wails-hello
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope grpc
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_conformance run --servers go,java,kotlin,python --clients go,typescript,kotlin,flutter,java,python --scenario request-options,media,media-filename-edge,media-error,binary-response,audit-binary
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
```

generated client benchmark/smoke 命令按实现后的 CLI 名称补充执行。

## 验收标准

- Java binary benchmark 和 `binary --target all --count 1` 不再因旧命名失败。
- request options 有真实 generated client 运行级覆盖。
- media/raw filename edge 与 typed error 边界有 conformance 覆盖。
- `byte_stream` 在 Java/Kotlin/Flutter/Go/Python/TypeScript 中统一为真流式语义。
- 生成物格式 invariant 能阻止空洞 request block、尾随空白和连续多空行回归。
- examples refresh、conformance、compileall、`api-gen check`、`git diff --check` 通过。

## Resolution

修复日期：2026-05-21

实施摘要：

- 修复 Java binary benchmark 的 `Gen*` 命名引用，并增加 benchmark smoke 覆盖。
- 新增 generated client SDK `sdk-smoke` benchmark 入口。
- 新增 `request-options`、`media-filename-edge`、`media-error` conformance 场景。
- Java/Kotlin/Flutter `byte_stream` 改为真流式 API；Go/Python/TypeScript 保持真流式方向并纳入互通覆盖。
- raw/media typed error 在 raw success route 上继续按 JSON error envelope 被客户端识别。
- 清理 TypeScript request block 空行，并把 Flutter 纳入生成源码尾部空行归一化。
- 更新 `PRE_README.MD`、README 中英入口说明，以及 configuration/generators/examples-validation/benchmarks 专题文档。

验证命令：

```bash
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run pytest tests/codegen/shared tests/codegen/java tests/codegen/kotlin tests/codegen/flutter tests/codegen/typescript tests/codegen/python tests/codegen/go tests/codegen/wails tests/scripts -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
git diff --check
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope wails-hello
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope grpc
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_conformance run --servers go,java,kotlin,python --clients go,typescript,kotlin,flutter,java,python --scenario request-options,media,media-filename-edge,media-error,binary-response,audit-binary
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target java --count 1
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark sdk-smoke --servers go --clients python --scenario request-options,binary-response,media
```

相关 commit / PR：本地未提交。
