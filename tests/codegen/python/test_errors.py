from __future__ import annotations

from .helpers import *


def test_python_client_and_server_generate_error_catalog_runtime(tmp_path: Path):
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
        views.GET("/ping").RSP(Result)

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    client_errors = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_errors.py"
    ).read_text(encoding="utf-8")
    client_catalog = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "gen_error_lookup.py"
    ).read_text(encoding="utf-8")
    client_public_errors = (
        client_dir / "api_blueprint_generated" / "api" / "runtime" / "errors.py"
    ).read_text(encoding="utf-8")
    assert "class ApiError(Exception):" in client_errors
    assert "class ApiErrorPayload:" in client_errors
    assert "def is_api_error(" in client_errors
    assert "class ApiToastSpec:" in client_errors
    assert "def resolve_api_toast(" in client_errors
    assert "ERROR_CATALOG_BY_ID" not in client_errors
    assert '"CommonErr.UNKNOWN"' not in client_errors
    assert '"CommonErr.UNKNOWN"' in client_catalog
    assert "API_ERRORS_BY_ID" in client_catalog
    assert "ROUTE_API_ERRORS_BY_CODE" in client_catalog
    assert "def lookup_api_error(" in client_catalog
    assert "TOKEN_EXPIRE: ApiErrorEntry = API_ERRORS_BY_ID[\"CommonErr.TOKEN_EXPIRE\"]" in client_catalog
    assert "class ApiErrors:" in client_catalog
    assert 'default="登录状态已失效，请重新登录"' in client_catalog
    assert "\\u767b" not in client_catalog
    assert "locales" not in client_catalog
    assert "from .gen_errors import *" in client_public_errors
    assert "from .gen_error_lookup import *" in client_public_errors
    client_errors_module = _import_generated_module(
        client_dir,
        "api_blueprint_generated.api.runtime.gen_errors",
    )
    payload = client_errors_module.ApiToastPayload(
        key="auth.token_expire",
        level="warning",
        default="登录状态已失效，请重新登录",
    )
    assert (
        client_errors_module.resolve_api_toast(
            payload,
            lambda key: "Sign in again" if key == "auth.token_expire" else None,
            "fallback",
        )
        == "Sign in again"
    )
    override = client_errors_module.ApiToastPayload(
        key="auth.token_expire.enterprise",
        level="warning",
        default="登录状态已失效，请重新登录",
        text="企业账号登录已失效，请重新绑定后继续使用",
    )
    assert client_errors_module.resolve_api_toast(override, lambda _key: "Sign in again", "fallback") == override.text
    assert (
        client_errors_module.resolve_api_toast(
            client_errors_module.ApiToastPayload(default="默认提示"),
            None,
            "fallback",
        )
        == "默认提示"
    )
    assert client_errors_module.resolve_api_toast(None, None, "fallback") == "fallback"

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    assert (server_dir / "api_blueprint_generated" / "api" / "runtime" / "errors.py").is_file()
    _compile_generated_files(tmp_path)
