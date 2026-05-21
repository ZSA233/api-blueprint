from __future__ import annotations

from .helpers import *


def test_typescript_codegen_emits_multipart_and_raw_response_contracts(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")

    output_dir = tmp_path / "typescript"
    writer = TypeScriptWriter(output_dir)
    writer.register(bp)
    writer.gen()

    runtime_client = (output_dir / "api" / "runtime" / "gen_client.ts").read_text(encoding="utf-8")
    runtime_types = (output_dir / "api" / "runtime" / "gen_types.ts").read_text(encoding="utf-8")
    route_types = (output_dir / "api" / "routes" / "api" / "media" / "gen_types.ts").read_text(encoding="utf-8")
    route_client = (output_dir / "api" / "routes" / "api" / "media" / "gen_client.ts").read_text(encoding="utf-8")
    transport = (output_dir / "api" / "transports" / "http" / "gen_transport.ts").read_text(encoding="utf-8")

    assert "export type ApiFilePart" in runtime_client
    assert 'responseType?: "json" | "text" | "blob" | "arrayBuffer" | "stream" | "binary_schema"' in runtime_client
    assert 'import type { ApiFilePart, ApiRawResponse }' in route_types
    assert "image: ApiFilePart;" in runtime_types
    assert "export type PreviewResponse = ApiRawResponse<Blob>;" in route_types
    assert "multipart?: Shared.MediaUpload;" in route_client
    assert "multipart: request.multipart" in route_client
    assert 'responseType: "blob"' in route_client
    assert "{\n\n    return this.request" not in route_client
    assert "({\n\n      routeId" not in route_client
    assert "    });\n\n  }" not in route_client
    assert "function buildMultipartFormData" in transport
    assert "async function throwRawApiErrorIfPresent" in transport
    assert "await throwRawApiErrorIfPresent(response, routeId, responseEnvelope)" in transport
    assert "return buildRawResponse(await response.blob(), response)" in transport
