# Swift Conformance Runtime 缺口审查

- 状态：已修复
- 发现日期：2026-05-30
- 背景：接入 Swift client 到 examples conformance 矩阵时，真实 Python FastAPI server + generated Swift client 暴露了多个 Swift HTTP runtime 行为缺口。
- 风险分级：高
- 问题性质：生成物可用性、跨端一致性、协议边界回归风险
- 存在性判断：已确认。问题均由真实 conformance 场景复现，不是静态推测。

## 问题

1. Swift `apiDecodeValue` 对 JSON 顶层标量没有使用 fragments，`stringEmun` 这类 enum/scalar response 会触发 `NSJSONSerialization` 异常。
2. multipart DTO 的 `APIFilePart` 经过 generic JSON object 转换后退化为字典，HTTP transport 无法按文件 part 发送。
3. `Content-Disposition` 只解析 `filename=`，没有解析 RFC 5987 `filename*=`，导致非 ASCII 下载文件名不一致。
4. raw bytes/file route 在 HTTP 200 返回 JSON typed-error envelope 时被当作 raw success body，没有还原 `APIError`。
5. Swift `APIErrorPayload` 没有保留 `toast.text`，typed error toast 只能看到 default，无法与其他 client 的 toast fallback 语义对齐。

## 复现场景

```sh
uv run python -m scripts.example_conformance run \
  --servers python \
  --clients swift \
  --scenario rpc,raw,xml,static,header,scalar,enum,map,deprecated,form,binary,audit-binary,binary-response,media,request-options,media-filename-edge,media-error,error,naming
```

修复前该命令会分别在 `enum`、`media`、`media-error` 或 `error` 场景失败。

## 影响范围

- 影响 Swift client generated runtime 和 URLSession HTTP transport。
- 不改变 wire protocol、route id、DTO 字段 wire name、error code 或 response envelope 契约。
- 不涉及 UI、鉴权、缓存、session owner、retry 或 token storage。

## 兼容性 / 修复风险

- `APIErrorPayload` 新增 optional `toastText` 字段，属于向后兼容扩展。
- multipart helper 会保留 `APIFilePart` 原对象，仅影响 multipart 文件字段的正确发送。
- raw JSON error envelope 检测只在 raw bytes/file/byte_stream 分支遇到 JSON response 时触发，成功 raw media 不受影响。
- Swift `URLSession` 对 `multipart/x-mixed-replace` 可能只交付 part body 而不暴露 boundary，conformance harness 接受 boundary 或 JPEG part body 两种平台行为。

## 是否建议修复

建议修复，并作为 Swift client 接入 conformance 的前置条件。

## 后续处置建议

- Swift SSE/WebSocket 暂不加入可运行 conformance 场景，等 generated transport 真正支持可验证生命周期后再扩展。
- 若后续改造 Swift multipart DTO 生成方式，应保留 `APIFilePart` 不被 JSON 中间表示吞掉这一契约。

## 修复记录 / Resolution

- 修复日期：2026-05-30
- 修复摘要：
  - Swift decode helper 支持 JSON fragments。
  - multipart helper 保留 `APIFilePart`。
  - URLSession transport 支持 `filename*=`。
  - raw response 分支识别 JSON typed-error envelope 并保留 raw body。
  - `APIErrorPayload` 增加 `toastText`。
  - 新增 `examples/swift/Conformance` 并接入 `scripts/example_conformance` Swift client 矩阵。
- 验证命令：
  - `swift build`（`examples/swift`）
  - `swift build -c release`（`examples/swift/Conformance`）
  - `uv run pytest tests/scripts/example_conformance -q`
  - `uv run pytest tests/codegen/shared tests/codegen/flutter tests/codegen/typescript tests/codegen/go/client -q`
  - `uv run pytest tests/codegen/swift tests/codegen/shared/test_generated_ownership.py tests/contract/graph/test_artifacts.py -q`
  - `uv run pytest tests/cli/config tests/cli/apigen -q`
  - `uv run api-gen check -c examples/api-blueprint.toml`
  - `uv run python scripts/example_validation.py --mode compile --scope blueprint`
  - `uv run python -m scripts.example_conformance run --servers python --clients swift --scenario rpc,raw,xml,static,header,scalar,enum,map,deprecated,form,binary,audit-binary,binary-response,media,request-options,media-filename-edge,media-error,error,naming`
