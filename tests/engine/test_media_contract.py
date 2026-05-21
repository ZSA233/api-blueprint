from __future__ import annotations

import pytest
from fastapi import FastAPI

from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import FileField, Model, String


class UploadForm(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], max_size=1024, description="image")


def test_file_field_is_only_allowed_in_multipart_request_models() -> None:
    bp = Blueprint(root="/api", app=FastAPI())
    with bp.group("/media") as views:
        with pytest.raises(ValueError, match="REQ_JSON.*FileField"):
            views.POST("/json").REQ_JSON(UploadForm)
        with pytest.raises(ValueError, match="REQ_URLENCODED.*FileField"):
            views.POST("/form").REQ_URLENCODED(UploadForm)
        with pytest.raises(ValueError, match="ARGS.*FileField"):
            views.GET("/query").ARGS(UploadForm)
        with pytest.raises(ValueError, match="RSP_JSON.*FileField"):
            views.GET("/response").RSP_JSON(UploadForm)


def test_multipart_and_raw_response_openapi_contract() -> None:
    bp = Blueprint(root="/api", app=FastAPI())
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(UploadForm).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="report.xlsx",
        )

    bp.build()
    schema = bp.app.openapi()

    preview = schema["paths"]["/api/media/preview"]["post"]
    multipart = preview["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert multipart["properties"]["image"]["format"] == "binary"
    assert multipart["properties"]["image"]["x-content-types"] == ["image/jpeg"]
    assert multipart["properties"]["image"]["x-max-size"] == 1024
    assert "image/jpeg" in preview["responses"]["200"]["content"]

    download = schema["paths"]["/api/media/download"]["get"]
    assert "Content-Disposition" in download["responses"]["200"]["headers"]
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in download["responses"]["200"]["content"]


def test_rsp_file_default_filename_alias_and_conflict() -> None:
    bp = Blueprint(root="/api", app=FastAPI())
    route = bp.GET("/download").RSP_FILE(content_type="application/octet-stream", default_filename="report.bin")
    assert route.rsp_filename == "report.bin"

    alias = bp.GET("/download-alias").RSP_FILE(content_type="application/octet-stream", filename="legacy.bin")
    assert alias.rsp_filename == "legacy.bin"

    with pytest.raises(ValueError, match="filename and default_filename"):
        bp.GET("/download-conflict").RSP_FILE(
            content_type="application/octet-stream",
            default_filename="new.bin",
            filename="legacy.bin",
        )
