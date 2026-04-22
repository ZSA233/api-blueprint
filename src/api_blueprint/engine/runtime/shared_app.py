from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles


_SHARED_APP: FastAPI | None = None


def get_shared_app(title: str) -> FastAPI:
    global _SHARED_APP
    if _SHARED_APP is None:
        _SHARED_APP = build_default_app(title)
    return _SHARED_APP


def reset_shared_app() -> None:
    global _SHARED_APP
    _SHARED_APP = None


def build_default_app(title: str) -> FastAPI:
    app = FastAPI(
        title=title,
        docs_url=None,
        redoc_url=None,
    )
    here = Path(__file__).resolve().parents[1]
    app.mount("/static", StaticFiles(directory=here.parent / "static"), name="static")

    @app.get("/redoc", include_in_schema=False)
    def redoc():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title="API Docs",
            redoc_js_url="/static/redoc.standalone.js",
        )

    @app.get("/docs", include_in_schema=False)
    def docs():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="API Docs",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
        )

    return app
