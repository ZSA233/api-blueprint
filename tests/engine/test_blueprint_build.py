from __future__ import annotations

from fastapi import FastAPI

from api_blueprint.engine import Blueprint, reset_shared_app


def test_example_blueprints_build_into_shared_fastapi_app(example_entrypoints):
    _config, entrypoints = example_entrypoints

    for bp in entrypoints:
        bp.build()

    apps = {bp.app for bp in entrypoints}
    assert len(apps) == 1

    app = entrypoints[0].app
    paths = {route.path for route in app.routes if getattr(route, "path", None)}
    assert "/docs" in paths
    assert "/redoc" in paths
    assert "/openapi.json" in paths
    assert "/api/demo/abc" in paths
    assert "/api/hello/hello-way" in paths
    assert "/static/doc.json" in paths
    assert len(paths) == 22

    for bp in entrypoints:
        bp.build()

    paths_after_rebuild = {route.path for route in app.routes if getattr(route, "path", None)}
    assert paths_after_rebuild == paths


def test_explicit_fastapi_app_breaks_default_shared_app_behavior():
    reset_shared_app()
    app_a = FastAPI()
    app_b = FastAPI()

    bp_a = Blueprint(root="/a", app=app_a)
    bp_b = Blueprint(root="/b", app=app_b)

    assert bp_a.app is app_a
    assert bp_b.app is app_b
    assert bp_a.app is not bp_b.app
