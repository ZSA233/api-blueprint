from __future__ import annotations

from fastapi import FastAPI

from api_blueprint.engine import Blueprint, reset_shared_app
from api_blueprint.engine.model import String


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
    assert "/api/demo/error-demo" in paths
    assert "/api/demo/request-options" in paths
    assert "/api/demo/sweep-events" in paths
    assert "/api/demo/assistant-session" in paths
    assert "/api/binary/packet" in paths
    assert "/api/media/preview" in paths
    assert "/api/media/mjpeg" in paths
    assert "/api/media/download-filename-edge" in paths
    assert "/api/media/error-frame" in paths
    assert "/api/hello/hello-way" in paths
    assert "/static/doc.json" in paths
    assert len(paths) == 38

    openapi = app.openapi()
    assert "text/event-stream" in openapi["paths"]["/api/demo/sweep-events"]["get"]["responses"]["200"]["content"]

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


def test_response_envelope_omitempty_fields_are_optional_in_openapi():
    app = FastAPI()
    bp = Blueprint(root="/api", app=app)
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    bp.build()
    openapi = app.openapi()
    path_spec = openapi["paths"]["/api/demo/ping"]["get"]
    response_schema = path_spec["responses"]["200"]["content"]["application/json"]["schema"]
    rsp_schema_ref = response_schema["$ref"]
    rsp_schema_name = rsp_schema_ref.rsplit("/", 1)[-1]
    required = openapi["components"]["schemas"][rsp_schema_name]["required"]

    assert "code" in required
    assert "message" in required
    assert "data" not in required
    assert "error" not in required
