from __future__ import annotations

from .helpers import *


def test_python_codegen_emits_multipart_and_raw_response_contracts(tmp_path: Path):
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")

    client_dir = tmp_path / "client"
    client_writer = PythonClientWriter(client_dir)
    client_writer.register(bp)
    client_writer.gen()
    _compile_generated_files(client_dir)

    server_dir = tmp_path / "server"
    server_writer = PythonServerWriter(server_dir)
    server_writer.register(bp)
    server_writer.gen()
    _compile_generated_files(server_dir)

    client_types = (client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_types.py").read_text(encoding="utf-8")
    client_route = (client_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_client.py").read_text(encoding="utf-8")
    client_transport = (client_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_client.py").read_text(encoding="utf-8")
    server_service = (server_dir / "api_blueprint_generated" / "api" / "routes" / "api" / "media" / "gen_service.py").read_text(encoding="utf-8")
    server_transport = (server_dir / "api_blueprint_generated" / "api" / "transports" / "http" / "gen_server.py").read_text(encoding="utf-8")

    assert "image: ApiUploadFile" in client_types
    assert "multipart=_api_to_transport(multipart)" in client_route
    assert "response_type: str | None = 'bytes'" in client_route
    assert "ApiRawResponse[bytes]" in client_route
    assert "_multipart_content" in client_transport
    assert "request_kwargs[\"content\"] = content" in client_transport
    assert "async def _iter_file_bytes(" in client_transport
    assert "payload = self._extract_raw_error_payload(response, response_envelope)" in client_transport
    assert "def _extract_raw_error_payload(" in client_transport
    assert "return _raw_response(response)" in client_transport
    assert "bytes | ApiRawResponse[bytes]" in server_service
    assert "str | Path | ApiRawResponse[bytes]" in server_service
    assert "_multipart_body" in server_transport
    assert "filename=None" in server_transport
    assert "FileResponse(" in server_transport
    assert "StreamingResponse(" in server_transport
