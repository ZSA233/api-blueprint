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
	runtime "example.com/project/golang/client/runtime"
	runtimebinary "example.com/project/golang/client/runtime/binary"
	httptransport "example.com/project/golang/client/transports/http"
)

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
	selected := scenarioSet("rpc,binary,form,error,naming")
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
	err := action()
	if err == nil {
		return nil, fmt.Errorf("expected ApiError")
	}
	var apiErr *runtime.ApiError
	if !errors.As(err, &apiErr) {
		return nil, fmt.Errorf("expected ApiError, got %T: %w", err, err)
	}
	if apiErr.RouteID() != "api.demo.get.errordemo" {
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
