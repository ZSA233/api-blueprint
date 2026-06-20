package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"reflect"
	"strings"
	"time"

	apiclient "example.com/project/golang/client"
	binaryapi "example.com/project/golang/client/routes/api/binary"
	apiconflict "example.com/project/golang/client/routes/api/conflict"
	demo "example.com/project/golang/client/routes/api/demo"
	hello "example.com/project/golang/client/routes/api/hello"
	media "example.com/project/golang/client/routes/api/media"
	runtime "example.com/project/golang/client/runtime"
	runtimebinary "example.com/project/golang/client/runtime/binary"
	httptransport "example.com/project/golang/client/transports/http"
)

var sampleJPEG = []byte{0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 'J', 'F', 'I', 'F', 0x00, 0x01, 0x01, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("go conformance passed")
}

func run() error {
	if len(os.Args) < 2 {
		return fmt.Errorf("base URL argument is required")
	}
	baseURL := strings.TrimRight(os.Args[1], "/")
	selected := scenarioSet("rpc,binary,form,error,naming,raw,xml,static,header,scalar,enum,map,deprecated,empty-response,path-params,audit-binary,binary-response,media,single-channel")
	if len(os.Args) >= 3 && os.Args[2] != "" {
		selected = scenarioSet(os.Args[2])
	}

	client := apiclient.NewHTTP(apiclient.HTTPConfig{BaseURL: baseURL})
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if selected["rpc"] {
		if err := checkRPC(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["raw"] {
		if err := checkRaw(ctx, baseURL); err != nil {
			return err
		}
	}
	if selected["xml"] {
		if err := checkXML(ctx, baseURL); err != nil {
			return err
		}
	}
	if selected["static"] {
		if err := checkStatic(ctx, baseURL); err != nil {
			return err
		}
	}
	if selected["header"] {
		if err := checkHeader(ctx, baseURL); err != nil {
			return err
		}
	}
	if selected["scalar"] {
		if err := checkScalar(ctx, client.Hello); err != nil {
			return err
		}
	}
	if selected["enum"] {
		if err := checkEnum(ctx, client.Hello); err != nil {
			return err
		}
	}
	if selected["map"] {
		if err := checkMap(ctx, baseURL, client.Demo, client.Hello); err != nil {
			return err
		}
	}
	if selected["deprecated"] {
		if err := checkDeprecated(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["empty-response"] {
		if err := checkEmptyResponse(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["path-params"] {
		if err := checkPathParams(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["form"] {
		if err := checkForm(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["binary"] {
		if err := checkBinary(ctx, client.Binary); err != nil {
			return err
		}
	}
	if selected["audit-binary"] {
		if err := checkAuditBinary(ctx, client.Binary); err != nil {
			return err
		}
	}
	if selected["binary-response"] {
		if err := checkBinaryResponse(ctx, client.Binary); err != nil {
			return err
		}
	}
	if selected["media"] {
		if err := checkMedia(ctx, client.Media); err != nil {
			return err
		}
	}
	if selected["request-options"] {
		if err := checkRequestOptions(baseURL); err != nil {
			return err
		}
	}
	if selected["media-filename-edge"] {
		if err := checkMediaFilenameEdge(ctx, client.Media); err != nil {
			return err
		}
	}
	if selected["media-error"] {
		if err := checkMediaError(ctx, client.Media); err != nil {
			return err
		}
	}
	if selected["error"] {
		if err := checkTypedErrors(ctx, client.Demo); err != nil {
			return err
		}
	}
	if selected["naming"] {
		if err := checkNaming(ctx, baseURL); err != nil {
			return err
		}
	}
	if selected["single-channel"] {
		if err := client.Api.OpenHelloChannel(ctx); err == nil {
			return fmt.Errorf("expected go single-channel transport to be unsupported")
		}
	}
	return nil
}

func scenarioSet(raw string) map[string]bool {
	out := map[string]bool{}
	for _, item := range strings.Split(raw, ",") {
		item = strings.TrimSpace(item)
		if item != "" {
			out[item] = true
		}
	}
	return out
}

func checkRPC(ctx context.Context, demoClient *demo.DemoClient) error {
	postRsp, err := demoClient.TestPost(ctx, demo.TestPostJSON{Req1: "go", Req2: 7})
	if err != nil {
		return fmt.Errorf("test_post: %w", err)
	}
	if !reflect.DeepEqual(postRsp.List, []string{"test_post", "go"}) {
		return fmt.Errorf("test_post list = %#v", postRsp.List)
	}
	if postRsp.Map["req2"] == nil || postRsp.Map["req2"].Haha != 7 {
		return fmt.Errorf("test_post map = %#v", postRsp.Map)
	}

	putRsp, err := demoClient.PutDemo(
		ctx,
		demo.PutDemoQuery{Arg1: "query", Arg2: 3.5},
		demo.PutDemoJSON{Req1: "body", Req2: 9},
	)
	if err != nil {
		return fmt.Errorf("put demo: %w", err)
	}
	if !reflect.DeepEqual(putRsp.List, []string{"query", "body"}) {
		return fmt.Errorf("put demo list = %#v", putRsp.List)
	}
	if putRsp.AnonKV == nil || putRsp.AnonKV.Kv1 != 9 {
		return fmt.Errorf("put demo anon_kv = %#v", putRsp.AnonKV)
	}
	return nil
}

func checkForm(ctx context.Context, demoClient *demo.DemoClient) error {
	rsp, err := demoClient.FormSubmit(ctx, demo.FormSubmitForm{
		Title:   "go-form",
		Count:   4,
		Enabled: true,
	})
	if err != nil {
		return fmt.Errorf("form submit: %w", err)
	}
	if rsp.Summary != "go-form" || rsp.Count != 4 || !rsp.Enabled {
		return fmt.Errorf("form submit response = %#v", rsp)
	}
	return nil
}

func checkRaw(ctx context.Context, baseURL string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/api/demo/raw", nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("raw status=%d body=%s", resp.StatusCode, string(raw))
	}
	return nil
}

func checkXML(ctx context.Context, baseURL string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, baseURL+"/api/demo/delete$?arg1=go-xml&arg2=7", nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK || !strings.Contains(string(raw), "go-xml") {
		return fmt.Errorf("xml status=%d body=%s", resp.StatusCode, string(raw))
	}
	return nil
}

func checkStatic(ctx context.Context, baseURL string) error {
	for _, path := range []string{"/static/doc.json", "/static/dochaha"} {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+path, nil)
		if err != nil {
			return err
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			return err
		}
		raw, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			return fmt.Errorf("static %s status=%d body=%s", path, resp.StatusCode, string(raw))
		}
	}
	return nil
}

func checkHeader(ctx context.Context, baseURL string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+"/api/demo/abc", nil)
	if err != nil {
		return err
	}
	req.Header.Set("x-token", "conformance-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("header status=%d body=%s", resp.StatusCode, string(raw))
	}
	return nil
}

func checkScalar(ctx context.Context, helloClient *hello.HelloClient) error {
	text, err := helloClient.String(ctx)
	if err != nil {
		return fmt.Errorf("hello string: %w", err)
	}
	if *text != "hello-string" {
		return fmt.Errorf("hello string = %#v", text)
	}
	value, err := helloClient.Uint64(ctx)
	if err != nil {
		return fmt.Errorf("hello uint64: %w", err)
	}
	if *value != 9007199254740991 {
		return fmt.Errorf("hello uint64 = %#v", value)
	}
	return nil
}

func checkEnum(ctx context.Context, helloClient *hello.HelloClient) error {
	item, err := helloClient.StringEmun(ctx)
	if err != nil {
		return fmt.Errorf("string enum: %w", err)
	}
	if *item != runtime.MapEnumA {
		return fmt.Errorf("string enum = %#v", item)
	}
	items, err := helloClient.ListEnum(ctx)
	if err != nil {
		return fmt.Errorf("list enum: %w", err)
	}
	if !reflect.DeepEqual(*items, []runtime.MapEnum{runtime.MapEnumA, runtime.MapEnumB}) {
		return fmt.Errorf("list enum = %#v", items)
	}
	return nil
}

func checkMap(ctx context.Context, baseURL string, demoClient *demo.DemoClient, helloClient *hello.HelloClient) error {
	model, err := demoClient.MapModel(ctx)
	if err != nil {
		return fmt.Errorf("map model: %w", err)
	}
	if (*model)[1].Haha != 101 {
		return fmt.Errorf("map model = %#v", model)
	}
	if err := checkHelloAbcRaw(ctx, baseURL); err != nil {
		return err
	}
	enumMap, err := helloClient.MapEnum(ctx)
	if err != nil {
		return fmt.Errorf("map enum: %w", err)
	}
	if (*enumMap)[runtime.MapEnumA].Haha != 11 {
		return fmt.Errorf("map enum = %#v", enumMap)
	}
	return nil
}

func checkHelloAbcRaw(ctx context.Context, baseURL string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+"/api/hello/abc?type=ping", nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("hello abc status=%d body=%s", resp.StatusCode, string(raw))
	}
	body := string(raw)
	if !strings.Contains(body, `"hello"`) || !strings.Contains(body, `"ping"`) {
		return fmt.Errorf("hello abc response missing expected map keys: %s", body)
	}
	return nil
}

func checkDeprecated(ctx context.Context, demoClient *demo.DemoClient) error {
	rsp, err := demoClient.PostDeprecated(ctx, demo.PostDeprecatedJSON{Req1: "go-deprecated", Req2: 3})
	if err != nil {
		return fmt.Errorf("deprecated: %w", err)
	}
	if !reflect.DeepEqual(rsp.List, []string{"go-deprecated"}) {
		return fmt.Errorf("deprecated response = %#v", rsp)
	}
	return nil
}

func checkEmptyResponse(ctx context.Context, demoClient *demo.DemoClient) error {
	rsp, err := demoClient.EmptyResponse(ctx)
	if err != nil {
		return fmt.Errorf("empty response: %w", err)
	}
	if rsp == nil {
		return fmt.Errorf("empty response returned nil")
	}
	return nil
}

func checkPathParams(ctx context.Context, demoClient *demo.DemoClient) error {
	rsp, err := demoClient.PathEcho(ctx, demo.PathEchoPath{Item: "alpha", Badge: "gold badge"})
	if err != nil {
		return fmt.Errorf("path echo: %w", err)
	}
	if rsp.Item != "alpha" || rsp.Badge != "gold badge" || rsp.Combined != "alpha:gold badge" {
		return fmt.Errorf("path echo response = %#v", rsp)
	}
	return nil
}

func checkBinary(ctx context.Context, binaryClient *binaryapi.BinaryClient) error {
	for _, item := range []struct {
		trace string
		body  runtimebinary.Body
	}{
		{"go-typed", buildPacket()},
		{"go-raw", runtimebinary.NewRawBody(packetBytes())},
	} {
		rsp, err := binaryClient.Packet(ctx, binaryapi.PacketQuery{Trace: item.trace}, item.body)
		if err != nil {
			return fmt.Errorf("binary %s: %w", item.trace, err)
		}
		if err := assertBinaryResponse(item.trace, rsp); err != nil {
			return err
		}
	}
	return nil
}

func checkAuditBinary(ctx context.Context, binaryClient *binaryapi.BinaryClient) error {
	rsp, err := binaryClient.AuditPacket(ctx, binaryapi.AuditPacketQuery{Trace: "go-audit"}, buildAuditPacket())
	if err != nil {
		return fmt.Errorf("audit binary: %w", err)
	}
	if rsp.Trace != "go-audit" || rsp.ItemCount != 2 || rsp.Checksum != 2 {
		return fmt.Errorf("audit binary response = %#v", rsp)
	}
	return nil
}

func checkBinaryResponse(ctx context.Context, binaryClient *binaryapi.BinaryClient) error {
	rsp, err := binaryClient.AuditPacketResponse(ctx)
	if err != nil {
		return fmt.Errorf("binary response: %w", err)
	}
	expected := buildAuditPacket()
	if !reflect.DeepEqual(rsp, expected) {
		return fmt.Errorf("binary response = %#v", rsp)
	}
	return nil
}

func checkMedia(ctx context.Context, mediaClient *media.MediaClient) error {
	preview, err := mediaClient.MediaPreview(ctx, media.MediaPreviewForm{
		Title: "go-media",
		Image: runtime.MultipartFile{
			Filename:    "preview.jpg",
			ContentType: "image/jpeg",
			Bytes:       sampleJPEG,
		},
	})
	if err != nil {
		return fmt.Errorf("media preview: %w", err)
	}
	if preview.StatusCode != http.StatusOK || preview.ContentType != "image/jpeg" || !bytes.HasPrefix(preview.Body, []byte{0xff, 0xd8}) {
		return fmt.Errorf("media preview response = %#v", preview)
	}

	frame, err := mediaClient.MediaFrame(ctx)
	if err != nil {
		return fmt.Errorf("media frame: %w", err)
	}
	if frame.ContentType != "image/jpeg" || !bytes.Equal(frame.Body, sampleJPEG) {
		return fmt.Errorf("media frame response = %#v", frame)
	}

	download, err := mediaClient.MediaDownload(ctx)
	if err != nil {
		return fmt.Errorf("media download: %w", err)
	}
	if download.Filename != "media-report.xlsx" || !bytes.HasPrefix(download.Body, []byte("PK")) {
		return fmt.Errorf("media download response = %#v", download)
	}

	dynamic, err := mediaClient.MediaDownloadDynamic(ctx)
	if err != nil {
		return fmt.Errorf("media dynamic download: %w", err)
	}
	if dynamic.Filename != "media-report-dynamic.xlsx" || !bytes.HasPrefix(dynamic.Body, []byte("PK")) {
		return fmt.Errorf("media dynamic download response = %#v", dynamic)
	}

	stream, err := mediaClient.MediaMjpeg(ctx)
	if err != nil {
		return fmt.Errorf("media mjpeg: %w", err)
	}
	defer stream.Body.Close()
	chunk, err := io.ReadAll(stream.Body)
	if err != nil {
		return fmt.Errorf("media mjpeg read: %w", err)
	}
	if !bytes.Contains(chunk, []byte("--frame")) {
		return fmt.Errorf("media mjpeg chunk = %q", string(chunk))
	}
	return nil
}

func checkRequestOptions(baseURL string) error {
	timeoutClient := apiclient.NewHTTP(apiclient.HTTPConfig{
		BaseURL: baseURL,
		DefaultHeaders: map[string]string{
			"x-options-default": "default",
			"x-options-token":   "default",
		},
	})
	okCtx, okCancel := context.WithTimeout(context.Background(), time.Second)
	defer okCancel()
	ok, err := timeoutClient.Demo.RequestOptions(
		okCtx,
		demo.RequestOptionsQuery{DelayMs: 30},
		runtime.WithHeader("x-options-token", "per-call"),
	)
	if err != nil {
		return fmt.Errorf("request options ok: %w", err)
	}
	if ok.Status != "ok" || ok.DelayMs != 30 {
		return fmt.Errorf("request options response = %#v", ok)
	}

	shortCtx, shortCancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer shortCancel()
	_, err = timeoutClient.Demo.RequestOptions(
		shortCtx,
		demo.RequestOptionsQuery{DelayMs: 120},
		runtime.WithHeader("x-options-token", "per-call"),
	)
	if err == nil {
		return fmt.Errorf("request options short timeout did not fail")
	}
	return nil
}

func checkMediaFilenameEdge(ctx context.Context, mediaClient *media.MediaClient) error {
	response, err := mediaClient.MediaDownloadFilenameEdge(ctx)
	if err != nil {
		return fmt.Errorf("media filename edge: %w", err)
	}
	if response.Filename != "媒体报告.xlsx" || !bytes.HasPrefix(response.Body, []byte("PK")) {
		return fmt.Errorf("media filename edge response = %#v", response)
	}
	return nil
}

func checkMediaError(ctx context.Context, mediaClient *media.MediaClient) error {
	ok, err := mediaClient.MediaErrorFrame(ctx, media.MediaErrorFrameQuery{Mode: "ok"})
	if err != nil {
		return fmt.Errorf("media error ok: %w", err)
	}
	if ok.ContentType != "image/jpeg" || !bytes.HasPrefix(ok.Body, []byte{0xff, 0xd8}) {
		return fmt.Errorf("media error ok response = %#v", ok)
	}
	rateLimited, err := expectApiErrorForRoute("api.media.get.errorframe", func() error {
		_, err := mediaClient.MediaErrorFrame(ctx, media.MediaErrorFrameQuery{Mode: "rate_limit"})
		return err
	})
	if err != nil {
		return err
	}
	if !runtime.IsApiError(rateLimited, runtime.ApiErrors.DemoErr.RateLimited) {
		return fmt.Errorf("media error ApiError id=%q code=%d", rateLimited.ID(), rateLimited.Code())
	}
	return nil
}

func checkTypedErrors(ctx context.Context, demoClient *demo.DemoClient) error {
	okRsp, err := demoClient.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "ok"})
	if err != nil {
		return fmt.Errorf("error demo ok: %w", err)
	}
	if okRsp == nil || okRsp.Status != "ok" {
		return fmt.Errorf("error demo ok response = %#v", okRsp)
	}

	rateLimited, err := expectApiError(func() error {
		_, err := demoClient.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "rate_limit"})
		return err
	})
	if err != nil {
		return err
	}
	if !runtime.IsApiError(rateLimited, runtime.ApiErrors.DemoErr.RateLimited) {
		return fmt.Errorf("rate limit ApiError id=%q code=%d", rateLimited.ID(), rateLimited.Code())
	}
	if toast := runtime.ResolveApiToast(rateLimited.Toast(), nil, rateLimited.Message()); toast != "请等待 30 秒后重试" {
		return fmt.Errorf("rate limit toast = %q", toast)
	}

	unknown, err := expectApiError(func() error {
		_, err := demoClient.ErrorDemo(ctx, demo.ErrorDemoQuery{Mode: "unknown"})
		return err
	})
	if err != nil {
		return err
	}
	if unknown.ID() != "" || unknown.Code() != 70001 || unknown.Message() != "example undefined business error" {
		return fmt.Errorf("unknown ApiError id=%q code=%d message=%q", unknown.ID(), unknown.Code(), unknown.Message())
	}
	return nil
}

func checkNaming(ctx context.Context, baseURL string) error {
	transportClient := httptransport.NewClient(apiclient.HTTPConfig{BaseURL: baseURL})
	apiConflict := apiconflict.NewClient(transportClient)
	apiRsp, err := apiConflict.Default(ctx, apiconflict.DefaultQuery{Class: "go-api"})
	if err != nil {
		return fmt.Errorf("api conflict: %w", err)
	}
	if apiRsp.Default != "api-default" || apiRsp.Class != "go-api" || apiRsp.Enum != "default" {
		return fmt.Errorf("api conflict response = %#v", apiRsp)
	}

	if err := checkAltConflictRaw(baseURL); err != nil {
		return err
	}
	return nil
}

func checkAltConflictRaw(baseURL string) error {
	resp, err := http.Get(baseURL + "/alt/conflict/default?class_=go-alt")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("alt conflict status=%d body=%s", resp.StatusCode, string(data))
	}
	var envelope struct {
		OK   bool `json:"ok"`
		Data struct {
			Default string `json:"default"`
			Class   string `json:"class_"`
			Enum    string `json:"enum"`
		} `json:"data"`
	}
	if err := json.Unmarshal(data, &envelope); err != nil {
		return err
	}
	if !envelope.OK || envelope.Data.Default != "alt-default" || envelope.Data.Class != "go-alt" || envelope.Data.Enum != "class" {
		return fmt.Errorf("alt conflict response = %#v", envelope)
	}
	return nil
}

func expectApiError(action func() error) (*runtime.ApiError, error) {
	return expectApiErrorForRoute("api.demo.get.errordemo", action)
}

func expectApiErrorForRoute(routeID string, action func() error) (*runtime.ApiError, error) {
	err := action()
	if err == nil {
		return nil, fmt.Errorf("expected ApiError")
	}
	var apiErr *runtime.ApiError
	if !errors.As(err, &apiErr) {
		return nil, fmt.Errorf("expected ApiError, got %T: %w", err, err)
	}
	if apiErr.RouteID() != routeID {
		return nil, fmt.Errorf("ApiError route id = %q", apiErr.RouteID())
	}
	return apiErr, nil
}

func buildPacket() *binaryapi.DemoPacket {
	payload := []byte("payload-ok")
	return &binaryapi.DemoPacket{
		Header: binaryapi.DemoPacketHeader{
			Flags:       binaryapi.DemoPacketFlagsHasPayload | binaryapi.DemoPacketFlagsHasScores,
			ShortCode:   0x010203,
			SignedDelta: 7,
			ItemCount:   2,
			PayloadLen:  uint32(len(payload)),
		},
		Body: binaryapi.DemoPacketBody{
			Items: []binaryapi.DemoPacketItem{
				{ID: 11, Enabled: true, Value: 1.25, LabelLen: 5, Label: []byte("alpha")},
				{ID: 22, Enabled: false, Value: 2.5, LabelLen: 4, Label: []byte("beta")},
			},
			Payload:  payload,
			Scores:   []float64{3.5, 4.5},
			Checksum: 12,
		},
	}
}

func buildAuditPacket() *binaryapi.AuditPacket {
	return &binaryapi.AuditPacket{
		Header: binaryapi.AuditPacketHeader{
			Flags:     binaryapi.AuditPacketFlagsHasItems,
			ItemCount: 2,
		},
		Body: binaryapi.AuditPacketBody{
			Items: []binaryapi.AuditPacketItem{
				{ID: 11, Code: 101},
				{ID: 22, Code: 202},
			},
			Checksum: 2,
		},
	}
}

func packetBytes() []byte {
	var buffer bytes.Buffer
	writer := runtimebinary.NewWriter(&buffer, runtimebinary.LittleEndian)
	if err := binaryapi.WriteDemoPacket(buildPacket(), writer); err != nil {
		panic(err)
	}
	return buffer.Bytes()
}

func assertBinaryResponse(trace string, rsp *binaryapi.PacketResponse) error {
	expected := &binaryapi.PacketResponse{
		Trace:      trace,
		Version:    1,
		ItemCount:  2,
		Payload:    "payload-ok",
		ScoreSum:   8,
		FirstLabel: "alpha",
		ItemIDs:    []uint{11, 22},
		Checksum:   12,
	}
	if !reflect.DeepEqual(rsp, expected) {
		return fmt.Errorf("binary %s response = %#v", trace, rsp)
	}
	return nil
}
