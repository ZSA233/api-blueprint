# API Blueprint Refactor Implementation Plan

## Goal

- Keep public behavior stable while rebuilding internal structure around explicit boundaries.
- Complete engine/codegen/test/docs/validation refactor with verifiable checkpoints.

## Constraints

- Preserve public Python DSL imports, CLI names/options, config keys, and generated output layout.
- Keep `examples/blueprints/` as demo source and `examples/golang/`, `examples/typescript/` as generated snapshots.
- Do not expose Kotlin/Java/grpc as public commands or config yet; reserve internal extension points only.
- Treat current staged generated snapshots as replaceable intermediate state.

## Decisions

- Public compatibility level: keep current public API and generated output shape.
- Future targets: add internal generator target registry entries for `kotlin`, `java`, `grpc`, but only `golang` and `typescript` are implemented.
- Example validation: regenerate into temp dirs, compare snapshots, then run Go and TypeScript compile checks.

## Phase Status

| Phase | Title | Status | Notes |
| --- | --- | --- | --- |
| 0 | Living Plan | completed | Plan file created and now used as ongoing source of truth. |
| 1 | Engine Boundary Split | completed | Added `engine/schema`, `engine/runtime`, `engine/blueprint` with thin compatibility shims. |
| 2 | Config / Entrypoint / CLI Orchestration | completed | Added `config/` package, `application/` services, and thin CLI command modules. |
| 3 | Shared Codegen Core | completed | Added `writer/core/` with base writer abstractions, file helpers, templates, and generator registry. |
| 4 | TypeScript Generator Refactor | completed | Split generator into `writer/typescript/` with registry, naming, route grouping, and renderer components. |
| 5 | Go Generator Refactor | completed | Split generator into `writer/golang/` with blueprint/proto/toolchain separation and explicit adapters. |
| 6 | Test Suite Reorganization | completed | Reorganized tests into engine/cli/codegen/integration/support plus packaging/release coverage. |
| 7 | Example Regeneration Validation | completed | Added `scripts/example_validation.py` and integration coverage for regenerate/diff/compile flow. |
| 8 | CI / Docs / Release Contract Convergence | completed | CI now installs Go/Node explicitly and release/docs contracts include example validation assets. |

## Current Baseline

- `uv run pytest -q`: passing before refactor.
- Project warnings: Pydantic v2 deprecations in `engine/model.py`.
- `examples/golang`: `go test ./...` passes.
- `examples/typescript`: `tsc --noEmit` currently fails because staged generated snapshots contain invalid `base_url` rendering.

## Validation Log

- 2026-04-22: confirmed `uv run pytest -q` passes on pre-refactor baseline.
- 2026-04-22: confirmed `go test ./...` passes in `examples/golang`.
- 2026-04-22: confirmed `tsc -p examples/typescript/tsconfig.json --noEmit` fails on current staged snapshots.
- 2026-04-22: after engine split, `uv run pytest -q tests/core/test_config.py tests/core/test_blueprint_build.py` passes.
- 2026-04-22: after engine split, `uv run pytest -q` passes with no project-side Pydantic deprecation warnings emitted.
- 2026-04-22: added example regeneration integration path and confirmed `uv run python scripts/example_validation.py` passes.
- 2026-04-22: confirmed `uv run pytest -q tests/engine/test_schema.py tests/cli/test_commands.py tests/integration/examples/test_regeneration.py` passes after runtime cache isolation fixes.
- 2026-04-22: confirmed `uv run pytest -q` passes with 25 tests.
- 2026-04-22: confirmed `tsc -p examples/typescript/tsconfig.json --noEmit` passes on generated snapshots.
- 2026-04-22: confirmed `go test ./...` passes in `examples/golang` after regeneration.
- 2026-04-22: confirmed `uv run api-doc-server --help`, `uv run api-gen-golang --help`, and `uv run api-gen-typescript --help` smoke checks pass.
- 2026-04-22: confirmed `uv run python scripts/release_assets.py validate-config` and `validate-docs` pass after CI/docs convergence updates.

## Risks

- Repeated entrypoint loading can still accumulate unrelated user modules if external callers bypass `application.entrypoints.load_entrypoints`.
- Future public generator targets (`kotlin`, `java`, `grpc`) should keep the current “internal placeholder only” rule until their validation and packaging paths are implemented.

## Execution Notes

- Update this file whenever a phase starts or completes.
- Record new validation commands and notable regressions here.
