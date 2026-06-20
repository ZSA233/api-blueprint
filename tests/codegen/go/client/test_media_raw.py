from __future__ import annotations

import os
import re

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
    assert re.search(r"Multipart:\s+multipartBody", route_client)
    assert re.search(r'BodyKind:\s+runtime\.RequestBodyKind\("multipart"\)', route_client)
    assert re.search(r'ResponseKind:\s+runtime\.ResponseKind\("bytes"\)', route_client)
    assert (
        "func (client *GenMediaClient) Mjpeg(ctx context.Context, opts ...runtime.RequestOption) "
        "(*runtime.StreamResponse, error)"
    ) in route_client
    assert "func encodeMultipart" in transport
    assert "reader, pipeWriter := io.Pipe()" in transport
    assert "writer := multipart.NewWriter(pipeWriter)" in transport
    assert "_ = pipeWriter.CloseWithError(err)" in transport
    assert "return reader, contentType, -1, nil" in transport
    assert "func multipartStructValue" in transport
    assert "var buffer bytes.Buffer" not in transport
    assert "multipart.NewWriter(&buffer)" not in transport
    assert "func decodeRawResponse" in transport
    assert "decodeEnvelopeAPIError(data, request.RouteID, request.ResponseEnvelope)" in transport


@pytest.mark.toolchain_smoke
def test_golang_client_multipart_reader_is_streamed_when_body_is_consumed(tmp_path):
    bp = Blueprint(root="/api")
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    test_file = output_dir / "transports" / "http" / "gen_transport_streaming_test.go"
    test_file.write_text(
        r'''
package http

import (
	"io"
	"strings"
	"testing"
	"time"

	runtime "example.com/generated/client/runtime"
)

type blockingMultipartReader struct {
	started chan struct{}
	release chan struct{}
	sent    bool
}

func (reader *blockingMultipartReader) Read(p []byte) (int, error) {
	if reader.sent {
		return 0, io.EOF
	}
	close(reader.started)
	<-reader.release
	reader.sent = true
	return copy(p, "stream-data"), nil
}

func TestEncodeMultipartStreamsReaderWhenBodyIsConsumed(t *testing.T) {
	fileReader := &blockingMultipartReader{
		started: make(chan struct{}),
		release: make(chan struct{}),
	}
	body, contentType, contentLength, err := encodeMultipart(struct {
		Title string                `form:"title"`
		Image runtime.MultipartFile `form:"image"`
	}{
		Title: "preview",
		Image: runtime.MultipartFile{
			Filename:    "image.txt",
			ContentType: "text/plain",
			Reader:      fileReader,
		},
	})
	if err != nil {
		t.Fatalf("encodeMultipart returned error: %v", err)
	}
	if contentLength != -1 {
		t.Fatalf("expected streaming multipart content length -1, got %d", contentLength)
	}
	if !strings.HasPrefix(contentType, "multipart/form-data; boundary=") {
		t.Fatalf("unexpected content type: %q", contentType)
	}
	select {
	case <-fileReader.started:
		t.Fatal("file reader was consumed before the request body was read")
	default:
	}

	done := make(chan []byte, 1)
	failed := make(chan error, 1)
	go func() {
		data, err := io.ReadAll(body)
		if err != nil {
			failed <- err
			return
		}
		done <- data
	}()

	select {
	case <-fileReader.started:
		close(fileReader.release)
	case <-time.After(time.Second):
		t.Fatal("file reader was not consumed after reading the request body")
	}
	select {
	case err := <-failed:
		t.Fatalf("read multipart body: %v", err)
	case data := <-done:
		text := string(data)
		if !strings.Contains(text, "stream-data") {
			t.Fatalf("multipart body did not contain file data: %q", text)
		}
		if !strings.Contains(text, `name="title"`) || !strings.Contains(text, "preview") {
			t.Fatalf("multipart body did not contain form field: %q", text)
		}
	case <-time.After(time.Second):
		t.Fatal("timed out reading multipart body")
	}
}
'''.lstrip(),
        encoding="utf-8",
    )
    (output_dir / "go.mod").write_text(
        "module example.com/generated/client\n\ngo 1.23.8\n",
        encoding="utf-8",
    )
    go_env = os.environ.copy()
    go_env.pop("GOROOT", None)
    result = subprocess.run(
        ["go", "test", "./transports/http"],
        cwd=output_dir,
        env=go_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
