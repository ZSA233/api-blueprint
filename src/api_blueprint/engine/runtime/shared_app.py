from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api_blueprint.engine.runtime.docs import ensure_docs_gzip, install_api_blueprint_docs


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
        title=title or "api-blueprint",
        docs_url=None,
        redoc_url=None,
    )
    ensure_docs_gzip(app)
    here = Path(__file__).resolve().parents[1]
    app.mount("/static", StaticFiles(directory=here.parent / "static"), name="static")
    install_api_blueprint_docs(app)

    return app
