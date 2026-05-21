from api_blueprint.includes import *

from blueprints.app import apibp


class MediaPreviewRequest(Model):
    title = String(description="preview title", omitempty=True)
    image = FileField(content_types=["image/jpeg", "image/png"], max_size=5 * 1024 * 1024, description="source image")


with apibp.group("/media") as views:
    views.POST(
        "/preview",
        operation_id="mediaPreview",
        summary="Multipart media preview",
        description="Accepts multipart upload and returns buffered JPEG bytes.",
    ).REQ_MULTIPART(MediaPreviewRequest).RSP_BYTES(content_type="image/jpeg")

    views.GET(
        "/frame",
        operation_id="mediaFrame",
        summary="Latest media frame",
        description="Returns the latest buffered JPEG frame.",
    ).RSP_BYTES(content_type="image/jpeg")

    views.GET(
        "/download",
        operation_id="mediaDownload",
        summary="Media workbook download",
        description="Returns a generated XLSX file response.",
    ).RSP_FILE(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="media-report.xlsx",
    )

    views.GET(
        "/mjpeg",
        operation_id="mediaMjpeg",
        summary="MJPEG byte stream",
        description="Returns a multipart byte stream with MJPEG boundary chunks.",
    ).RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace; boundary=frame")
