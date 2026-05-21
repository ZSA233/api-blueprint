from __future__ import annotations

from .helpers import *


def test_golang_client_codegen_emits_multipart_and_raw_response_contracts(tmp_path):
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    runtime_text = (output_dir / "runtime" / "gen_client.go").read_text(encoding="utf-8")
    runtime_types = (output_dir / "runtime" / "gen_types.go").read_text(encoding="utf-8")
    route_types = (output_dir / "routes" / "api" / "media" / "gen_types.go").read_text(encoding="utf-8")
    route_client = (output_dir / "routes" / "api" / "media" / "gen_client.go").read_text(encoding="utf-8")
    transport = (output_dir / "transports" / "http" / "gen_transport.go").read_text(encoding="utf-8")

    assert "type MultipartFile struct" in runtime_text
    assert "type RawResponse struct" in runtime_text
    assert "type StreamResponse struct" in runtime_text
    assert "Image MultipartFile" in runtime_types
    assert (
        "func (client *GenMediaClient) Preview(ctx context.Context, multipartBody PreviewForm, "
        "opts ...runtime.RequestOption) (*runtime.RawResponse, error)"
    ) in route_client
    assert "Multipart:        multipartBody" in route_client
    assert 'BodyKind:         runtime.RequestBodyKind("multipart")' in route_client
    assert 'ResponseKind:     runtime.ResponseKind("bytes")' in route_client
    assert (
        "func (client *GenMediaClient) Mjpeg(ctx context.Context, opts ...runtime.RequestOption) "
        "(*runtime.StreamResponse, error)"
    ) in route_client
    assert "func encodeMultipart" in transport
    assert "func decodeRawResponse" in transport
    assert "decodeEnvelopeAPIError(data, request.RouteID, request.ResponseEnvelope)" in transport
