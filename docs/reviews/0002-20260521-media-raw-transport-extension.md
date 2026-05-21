# Media / Raw Transport Extension Review

## 状态

部分修复，继续跟踪。

v1 已实现核心 DSL、ContractGraph、capability check、Python client/server、TypeScript client、Go client/server、examples media 场景与跨端 conformance。Java、Kotlin、Flutter、Wails、gRPC 仍按 unsupported contract 处理，后续按同一 ContractGraph 语义补齐。

## 发现日期

2026-05-21

## 背景

真实使用方反馈 api-blueprint 缺少媒体上传和 raw 成功响应的一等契约表达。原有能力把 `.REQ_BINARY(path)`、form 请求和 HTTP raw response 逃生口混在不同层级，生成器难以判断 route 是 JSON envelope 响应、二进制 schema 请求，还是 bytes/file/stream raw 响应。

## 风险分级

高。

该问题影响协议契约、生成物可用性、跨端一致性和后续 target 扩展。如果继续只靠单端 escape hatch，客户端无法从 ContractGraph 获得正确返回类型，`api-gen check` 也无法提前发现 unsupported target。

## 问题性质

协议契约能力缺口，兼有历史语义混用问题。

- 请求侧缺少明确的 `urlencoded`、`multipart` body kind。
- 字段侧缺少只属于 multipart 的 file part 表达。
- 响应侧缺少 `bytes`、`file`、`byte_stream` raw success kind。
- `.REQ_BINARY(path)` 需要稳定归类为 Markdown Binary Schema 请求体，而不是 raw media response。
- 成功 raw response 不应 JSON envelope；typed error 仍需要沿用 JSON error envelope。

## 存在性判断

存在。

已有代码可以表达 JSON/form/binary schema 和部分 HTTP raw 逃生口，但不能在 ContractGraph manifest 中稳定描述 multipart 文件字段、raw file/bytes/stream response，也不能让 Go/Python/TypeScript client/server 基于同一契约生成一致类型。

## 复现场景

需要定义以下接口时，旧契约无法完整表达或跨端生成不一致：

- `POST /api/media/preview`：multipart 上传图片，返回 `image/jpeg` bytes。
- `GET /api/media/frame`：返回最新 JPEG frame。
- `GET /api/media/download`：返回 xlsx file，并带 `Content-Disposition`。
- `GET /api/media/mjpeg`：返回 MJPEG byte stream。

## 影响范围

- DSL 与 OpenAPI 输出。
- ContractGraph manifest、inspect/check/diff 语义。
- Go server/client、Python server/client、TypeScript client 生成结果。
- 其他语言 target 的 capability check。
- examples snapshot 与 conformance matrix。

## 兼容性 / 修复风险

允许破坏性更新后，主要风险是生成物 public API、manifest 字段和旧 `.REQ_FORM` 推荐路径变化。

- `.REQ_FORM` 保留为 urlencoded 兼容别名，但文档不再推荐。
- `.REQ_BINARY(path)` 语义收敛为 `binary_schema`。
- raw success response 不再经过 JSON envelope，客户端返回值类型会变化。
- 尚未实现 media 的 target 必须显式 unsupported，避免错误生成不可用代码。

## 是否建议修复

建议修复，并且需要把 ContractGraph 语义一次性定稳。

先在 Python、TypeScript、Go 的 client/server 形成闭环，可以验证 DSL、manifest、OpenAPI、server adapter、client transport 和 conformance 的边界；其他语言后续只补 writer/runtime，不重新发明契约。

## 后续处置建议

- 按同一 body/response kind 为 Java/Kotlin/Flutter 补 client/server 或 client 能力。
- 为 Wails/gRPC 明确是否支持 raw media route；如果不支持，继续在 check 阶段报清晰错误。
- 保持 examples media conformance 覆盖 Go/Python server 与 Go/TypeScript/Python client 的互通。
- 后续扩展 `FileField` 时优先补 manifest/OpenAPI/capability，再补 writer。

## 本轮验证记录

- 已执行并通过：`uv run pytest tests/engine/test_media_contract.py tests/engine/test_blueprint_build.py tests/contract/graph tests/codegen/shared tests/codegen/python tests/codegen/typescript tests/codegen/go/client tests/codegen/go/server -q`。
- 已执行并通过：`uv run python -m compileall src/api_blueprint -q`。
- 已执行并通过：`uv run api-gen check -c examples/api-blueprint.toml`。
- 已执行并通过：`uv run python -m scripts.example_validation --mode refresh --scope blueprint`。
- 已执行并通过：`uv run python -m scripts.example_conformance run --servers go,python --clients go,typescript,python --scenario media`。
