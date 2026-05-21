from __future__ import annotations

from .helpers import *


def test_typescript_writer_generates_error_catalog_runtime(tmp_path: Path):
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    bp = Blueprint(root="/api", errors=[CommonErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    output_dir = tmp_path / "typescript"
    output_dir.mkdir()
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    errors_text = (output_dir / "api" / "runtime" / "gen_errors.ts").read_text(encoding="utf-8")
    catalog_text = (output_dir / "api" / "runtime" / "gen_error_lookup.ts").read_text(encoding="utf-8")
    public_errors = (output_dir / "api" / "runtime" / "errors.ts").read_text(encoding="utf-8")
    runtime_index = (output_dir / "api" / "runtime" / "gen_index.ts").read_text(encoding="utf-8")
    assert "export class ApiError extends Error" in errors_text
    assert "export interface ApiErrorPayload" in errors_text
    assert "export function isApiError(" in errors_text
    assert "export interface ApiToastSpec" in errors_text
    assert "export function resolveApiToast(" in errors_text
    assert "ErrorCatalogByID" not in errors_text
    assert '"CommonErr.UNKNOWN"' not in errors_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "ApiErrorsByID" in catalog_text
    assert "RouteApiErrorsByCode" in catalog_text
    assert "lookupApiError(payload" in catalog_text
    assert "TOKEN_EXPIRE: 55555" in catalog_text
    assert 'default: "登录状态已失效，请重新登录"' in catalog_text
    assert "\\u767b" not in catalog_text
    assert "locales" not in catalog_text
    assert 'export * from "./gen_errors";' in public_errors
    assert 'export * from "./gen_error_lookup";' in public_errors
    assert 'export * from "./errors";' in runtime_index
