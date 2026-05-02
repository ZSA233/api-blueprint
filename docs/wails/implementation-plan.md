# Wails v2/v3 Implementation Plan

## Goal

- Add a public `api-gen-wails` generator that emits Wails-facing Go adapters and TypeScript clients from the existing Blueprint DSL.
- Keep business-layer ergonomics aligned with the existing HTTP Go and TypeScript generators wherever practical.
- Support Wails v3 first and Wails v2 second on the same transport-neutral generation layer.

## Rollout Decisions

- Delivery order is fixed as `shared refactor -> Wails v3 -> Wails v2 -> docs/validation`.
- Compatibility priority is shared business-layer ergonomics first, not transport-native APIs first.
- Go handler compatibility means keeping generated handler names and `Method(ctx, req) (rsp, err)` arity stable.
- TypeScript request/response client names and method signatures stay aligned across HTTP and Wails targets.
- TypeScript WebSocket support is intentionally normalized to `ApiSocketBridge<ServerMessage, ClientMessage>`.
- HTTP TypeScript output keeps an HTTP-only raw escape hatch via `connect<Route>Raw()`. Wails TypeScript output does not expose raw `WebSocket`.
- Wails v3 is documented as `experimental` because upstream v3 remains on the alpha track. Wails v2 is documented as `preview`.

## Phase Status

| Phase | Title | Status | Notes |
| --- | --- | --- | --- |
| 0 | Living Plan | completed | This file is the execution log and compatibility ledger for the Wails rollout. |
| 1 | Shared Transport-Neutral Refactor | completed | Added shared route contracts in `writer/core`, moved HTTP TypeScript generation onto an `ApiTransport`/`ApiSocketBridge` layer, and moved HTTP Go generation onto a transport-neutral runtime context. |
| 2 | Wails v3 Generator | completed | Added public `api-gen-wails`, Wails target resolution/selection, Wails Go adapters, Wails v3 TypeScript transport, and committed `examples/wails/v3/{go,typescript}` snapshots. |
| 3 | Wails v2 Generator | completed | Reused the same abstraction layer for Wails v2 TypeScript transport plus committed `examples/wails/v2/{go,typescript}` snapshots. |
| 4 | Docs And Validation | completed | `PRE_README.MD` plus mirrored `README.md` / `README_EN.md` are updated, and final release/doc/test checks are green. |

## Baseline Evidence

- 2026-05-02: `uv run pytest -q tests/cli/test_commands.py tests/codegen/test_registry.py` passed before the Wails doc/validation close-out.
- 2026-05-02: `uv run api-gen-golang --help` passed before the Wails doc/validation close-out.
- 2026-05-02: `uv run api-gen-typescript --help` passed before the Wails doc/validation close-out.

## Validation Log

- 2026-05-02: `uv run pytest -q tests/codegen/test_registry.py tests/codegen/test_typescript_codegen.py tests/codegen/test_wails_codegen.py tests/cli/test_commands.py tests/cli/test_config_resolution.py` passed.
- 2026-05-02: `tsc -p examples/typescript/tsconfig.json --noEmit` passed.
- 2026-05-02: `tsc -p examples/wails/v3/typescript/tsconfig.json --noEmit` passed.
- 2026-05-02: `tsc -p examples/wails/v2/typescript/tsconfig.json --noEmit` passed.
- 2026-05-02: `go test ./...` passed in `examples/golang`.
- 2026-05-02: `go test ./...` passed in `examples/wails/v3/go`.
- 2026-05-02: `go test ./...` passed in `examples/wails/v2/go`.
- 2026-05-02: `uv run api-gen-wails --help` passed.
- 2026-05-02: `uv run api-gen-wails -c examples/api-blueprint.toml --list-targets` passed.
- 2026-05-02: `uv run api-gen-wails -c examples/api-blueprint.toml --explain-target wails.v3` passed.
- 2026-05-02: `uv run pytest -q tests/codegen tests/cli tests/integration/examples/test_regeneration.py` passed with `56 passed, 1 skipped`; the skipped test requires local Gradle availability for the shared example validation pipeline.
- 2026-05-02: `uv run python scripts/example_validation.py --mode compile` failed in the current environment because Gradle is not installed or `API_BLUEPRINT_GRADLE_BIN` is not set.
- 2026-05-02: `uv run python scripts/release_assets.py validate-docs` passed.
- 2026-05-02: `uv run python scripts/release_assets.py validate-config` passed.
- 2026-05-02: `uv run pytest -q` passed with `93 passed, 1 skipped`; the skipped test is still the Gradle-gated example regeneration integration path.

## Intentional Compatibility Notes

- TypeScript WebSocket clients now expose `ApiSocketBridge<ServerMessage, ClientMessage>` instead of returning raw `WebSocket` objects directly.
- HTTP TypeScript output still exposes `connect<Route>Raw()` when browser-level `WebSocket` access is required.
- Wails TypeScript output targets documented runtime primitives directly instead of consuming Wails CLI-generated JS bindings as generator input.
- Wails v3 TypeScript output targets `window.wails.Call(...)` plus frontend events.
- Wails v2 TypeScript output targets the documented `window.go...` bridge shape plus `window.runtime.EventsOn/EventsOff`.
- Generated Go handler context is now transport-neutral. HTTP-specific behavior is no longer modeled as unconditional direct Gin ownership; HTTP-only access goes through generated escape hatches such as `RequireHTTP()`.

## Known Gaps

- `scripts/example_validation.py` now covers Wails examples too, but the shared Blueprint example pipeline still depends on Gradle because Kotlin snapshots are validated in the same flow.
- Wails v3 should continue to be treated as experimental until upstream v3 leaves the alpha track.

## Execution Rule

- Update this file whenever a Wails rollout phase starts or completes.
- Record every validation command that materially supports the current phase state.
- Add any user-visible compatibility drift here before considering the rollout complete.
