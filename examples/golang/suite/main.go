package main

import (
	"bytes"
	"compress/gzip"
	"context"
	stdbinary "encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"syscall"
	"time"

	binaryapi "example.com/project/golang/client/routes/api/binary"
	binaryschema "example.com/project/golang/client/routes/api/binary/_gen_binary"
	demo "example.com/project/golang/client/routes/api/demo"
	hello "example.com/project/golang/client/routes/api/hello"
	runtime "example.com/project/golang/client/runtime"
	runtimebinary "example.com/project/golang/client/runtime/binary"
	httptransport "example.com/project/golang/client/transports/http"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("golang example suite passed")
}

func run() error {
	addr, err := reserveLocalAddr()
	if err != nil {
		return err
	}
	server, err := startServer(addr)
	if err != nil {
		return err
	}
	defer server.stop()

	baseURL := "http://" + addr
	if err := waitForServer(baseURL, server); err != nil {
		return err
	}

	transport := httptransport.NewClient(httptransport.HttpConfig{BaseURL: baseURL})
	binaryClient := binaryapi.NewBinaryClient(transport)
	demoClient := demo.NewDemoClient(transport)
	helloClient := hello.NewHelloClient(transport)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := checkGeneratedClient(ctx, demoClient, helloClient); err != nil {
		return err
	}
	if err := checkUnsupportedConnections(ctx, demoClient); err != nil {
		return err
	}
	if err := checkBinaryHTTP(baseURL); err != nil {
		return err
	}
	if err := checkGeneratedBinaryClient(ctx, binaryClient); err != nil {
		return err
	}
	if err := checkTypeScriptBinaryClient(baseURL); err != nil {
		return err
	}
	if err := checkPythonBinaryClient(baseURL); err != nil {
		return err
	}
	return nil
}

type serverProcess struct {
	cmd    *exec.Cmd
	output *bytes.Buffer
	done   chan error
}

func startServer(addr string) (*serverProcess, error) {
	suiteDir, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	serverDir := filepath.Clean(filepath.Join(suiteDir, "..", "server"))
	output := new(bytes.Buffer)
	cmd := exec.Command("go", "run", ".")
	cmd.Dir = serverDir
	cmd.Stdout = output
	cmd.Stderr = output
	cmd.Env = append(os.Environ(), "API_BLUEPRINT_EXAMPLE_ADDR="+addr)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("start example server: %w", err)
	}
	server := &serverProcess{cmd: cmd, output: output, done: make(chan error, 1)}
	go func() {
		server.done <- cmd.Wait()
	}()
	return server, nil
}

func (server *serverProcess) stop() {
	if server == nil || server.cmd == nil || server.cmd.Process == nil {
		return
	}
	_ = syscall.Kill(-server.cmd.Process.Pid, syscall.SIGKILL)
	if server.done != nil {
		<-server.done
	}
}

func waitForServer(baseURL string, server *serverProcess) error {
	deadline := time.Now().Add(20 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		select {
		case err := <-server.done:
			server.done <- err
			return fmt.Errorf("example server exited before readiness: %w\n%s", err, server.output.String())
		default:
		}
		resp, err := http.Get(baseURL + "/api/hello/string")
		if err == nil {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
			lastErr = fmt.Errorf("unexpected health status %d", resp.StatusCode)
		} else {
			lastErr = err
		}
		time.Sleep(200 * time.Millisecond)
	}
	return fmt.Errorf("example server did not become ready: %w\n%s", lastErr, server.output.String())
}

func reserveLocalAddr() (string, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", err
	}
	addr := listener.Addr().String()
	if err := listener.Close(); err != nil {
		return "", err
	}
	return addr, nil
}

func checkGeneratedClient(ctx context.Context, demoClient *demo.DemoClient, helloClient *hello.HelloClient) error {
	postRsp, err := demoClient.TestPost(ctx, &demo.REQ_TestPost_JSON{Req1: "suite", Req2: 7})
	if err != nil {
		return fmt.Errorf("test_post: %w", err)
	}
	if !reflect.DeepEqual(postRsp.List, []string{"test_post", "suite"}) {
		return fmt.Errorf("test_post list = %#v", postRsp.List)
	}
	if postRsp.Map["req2"] == nil || postRsp.Map["req2"].Haha != 7 {
		return fmt.Errorf("test_post map = %#v", postRsp.Map)
	}

	putRsp, err := demoClient.Z1put(
		ctx,
		&demo.REQ_Z1put_QUERY{Arg1: "query", Arg2: 3.5},
		&demo.REQ_Z1put_JSON{Req1: "body", Req2: 9},
	)
	if err != nil {
		return fmt.Errorf("1put: %w", err)
	}
	if !reflect.DeepEqual(putRsp.List, []string{"query", "body"}) {
		return fmt.Errorf("1put list = %#v", putRsp.List)
	}
	if putRsp.Anon_kv == nil || putRsp.Anon_kv.Kv1 != 9 || !reflect.DeepEqual(putRsp.Anon_kv.Kv2, []float64{3.5, 9}) {
		return fmt.Errorf("1put anon_kv = %#v", putRsp.Anon_kv)
	}

	stringRsp, err := helloClient.String(ctx)
	if err != nil {
		return fmt.Errorf("hello string: %w", err)
	}
	if stringRsp == nil || *stringRsp != "hello-string" {
		return fmt.Errorf("hello string = %#v", stringRsp)
	}
	uintRsp, err := helloClient.Uint64(ctx)
	if err != nil {
		return fmt.Errorf("hello uint64: %w", err)
	}
	if uintRsp == nil || *uintRsp != 9007199254740991 {
		return fmt.Errorf("hello uint64 = %#v", uintRsp)
	}
	enumRsp, err := helloClient.StringEmun(ctx)
	if err != nil {
		return fmt.Errorf("hello string enum: %w", err)
	}
	if enumRsp == nil || *enumRsp != runtime.MapEnumA {
		return fmt.Errorf("hello string enum = %#v", enumRsp)
	}
	mapRsp, err := helloClient.MapEnum(ctx)
	if err != nil {
		return fmt.Errorf("hello map enum: %w", err)
	}
	if (*mapRsp)[runtime.MapEnumA] == nil || (*mapRsp)[runtime.MapEnumA].Haha != 11 {
		return fmt.Errorf("hello map enum = %#v", mapRsp)
	}
	listRsp, err := helloClient.ListEnum(ctx)
	if err != nil {
		return fmt.Errorf("hello list enum: %w", err)
	}
	if !reflect.DeepEqual(*listRsp, runtime.RSP_ListEnum{runtime.MapEnumA, runtime.MapEnumB}) {
		return fmt.Errorf("hello list enum = %#v", listRsp)
	}
	return nil
}

func checkUnsupportedConnections(ctx context.Context, demoClient *demo.DemoClient) error {
	if err := demoClient.SubscribeSweepEvents(ctx, &demo.OPEN_SweepEvents{Run_id: "suite"}); !isUnsupportedTransport(err, "stream") {
		return fmt.Errorf("expected stream UnsupportedTransportError, got %T %v", err, err)
	}
	if err := demoClient.OpenAssistantSession(ctx, &demo.OPEN_AssistantSession{Session_id: "suite"}); !isUnsupportedTransport(err, "channel") {
		return fmt.Errorf("expected channel UnsupportedTransportError, got %T %v", err, err)
	}
	return nil
}

func isUnsupportedTransport(err error, kind string) bool {
	var unsupported runtime.UnsupportedTransportError
	return errors.As(err, &unsupported) && unsupported.Kind == kind
}

type binaryEnvelope struct {
	Code    int            `json:"code"`
	Message string         `json:"message"`
	Data    binaryResponse `json:"data"`
}

type binaryResponse struct {
	Trace      string  `json:"trace"`
	Version    uint    `json:"version"`
	ItemCount  uint    `json:"item_count"`
	Payload    string  `json:"payload"`
	ScoreSum   float64 `json:"score_sum"`
	FirstLabel string  `json:"first_label"`
	ItemIDs    []uint  `json:"item_ids"`
	Checksum   uint    `json:"checksum"`
}

func checkBinaryHTTP(baseURL string) error {
	fixture := buildDemoPacketFixture("ABP1", 2, "payload-ok")
	if err := postBinary(baseURL, "identity", fixture, false); err != nil {
		return err
	}
	if err := postBinary(baseURL, "gzip", fixture, true); err != nil {
		return err
	}
	if err := postInvalidBinary(baseURL, buildDemoPacketFixture("BAD!", 2, "payload-ok")); err != nil {
		return err
	}
	if err := postInvalidBinary(baseURL, buildDemoPacketFixture("ABP1", 9, "payload-ok")); err != nil {
		return err
	}
	return nil
}

func checkGeneratedBinaryClient(ctx context.Context, client *binaryapi.BinaryClient) error {
	packet := buildDemoPacket()
	if err := callGeneratedBinary(ctx, client, "go-typed", packet); err != nil {
		return err
	}
	rawBody := runtimebinary.NewRawBody(buildDemoPacketFixture("ABP1", 2, "payload-ok"))
	if err := callGeneratedBinary(ctx, client, "go-raw", rawBody); err != nil {
		return err
	}
	streamBody := binaryschema.NewDemoPacketBody(-1, func(writer *runtimebinary.Writer) error {
		return binaryschema.WriteDemoPacket(packet, writer)
	})
	if err := callGeneratedBinary(ctx, client, "go-stream", streamBody); err != nil {
		return err
	}
	return nil
}

func callGeneratedBinary(ctx context.Context, client *binaryapi.BinaryClient, trace string, body runtimebinary.Body) error {
	rsp, err := client.Packet(ctx, &binaryapi.REQ_Packet_QUERY{Trace: trace}, body)
	if err != nil {
		return fmt.Errorf("generated binary %s: %w", trace, err)
	}
	expected := binaryResponse{
		Trace:      trace,
		Version:    1,
		ItemCount:  2,
		Payload:    "payload-ok",
		ScoreSum:   8,
		FirstLabel: "alpha",
		ItemIDs:    []uint{11, 22},
		Checksum:   12,
	}
	actual := binaryResponse{
		Trace:      rsp.Trace,
		Version:    rsp.Version,
		ItemCount:  rsp.Item_count,
		Payload:    rsp.Payload,
		ScoreSum:   rsp.Score_sum,
		FirstLabel: rsp.First_label,
		ItemIDs:    rsp.Item_ids,
		Checksum:   rsp.Checksum,
	}
	if !reflect.DeepEqual(actual, expected) {
		return fmt.Errorf("generated binary %s response = %#v", trace, actual)
	}
	return nil
}

func checkTypeScriptBinaryClient(baseURL string) error {
	suiteDir, err := os.Getwd()
	if err != nil {
		return err
	}
	typescriptDir := filepath.Clean(filepath.Join(suiteDir, "..", "..", "typescript"))
	outDir, err := os.MkdirTemp("", "api-blueprint-ts-suite-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(outDir)

	if err := runSuiteCommand(
		typescriptDir,
		"compile TypeScript suite",
		"tsc",
		"-p",
		filepath.Join(typescriptDir, "tsconfig.json"),
		"--module",
		"commonjs",
		"--moduleResolution",
		"node",
		"--outDir",
		outDir,
	); err != nil {
		return err
	}
	return runSuiteCommand(typescriptDir, "run TypeScript suite", "node", filepath.Join(outDir, "suite.js"), baseURL)
}

func checkPythonBinaryClient(baseURL string) error {
	suiteDir, err := os.Getwd()
	if err != nil {
		return err
	}
	pythonBin := os.Getenv("API_BLUEPRINT_PYTHON")
	if pythonBin == "" {
		pythonBin = "python3"
	}
	pythonClientDir := filepath.Clean(filepath.Join(suiteDir, "..", "..", "python", "client"))
	return runSuiteCommand(pythonClientDir, "run Python suite", pythonBin, filepath.Join(pythonClientDir, "suite.py"), baseURL)
}

func runSuiteCommand(cwd string, label string, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = cwd
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s: %w\n%s", label, err, string(output))
	}
	return nil
}

func buildDemoPacket() *binaryschema.DemoPacket {
	return &binaryschema.DemoPacket{
		Header: binaryschema.DemoPacketHeader{
			Flags:        binaryschema.DemoFlagsHasPayload | binaryschema.DemoFlagsHasScores,
			Short_code:   0x010203,
			Signed_delta: 7,
			Item_count:   2,
			Payload_len:  uint32(len("payload-ok")),
		},
		Body: binaryschema.DemoPacketBody{
			Items: []binaryschema.DemoPacketItem{
				{Id: 11, Enabled: true, Value: 1.25, Label_len: 5, Label: []byte("alpha")},
				{Id: 22, Enabled: false, Value: 2.5, Label_len: 4, Label: []byte("beta")},
			},
			Payload:  []byte("payload-ok"),
			Scores:   []float64{3.5, 4.5},
			Checksum: 12,
		},
	}
}

func postBinary(baseURL string, trace string, body []byte, gzipBody bool) error {
	resp, err := sendBinary(baseURL, trace, body, gzipBody)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("binary %s status %d: %s", trace, resp.StatusCode, string(raw))
	}
	var envelope binaryEnvelope
	if err := json.NewDecoder(resp.Body).Decode(&envelope); err != nil {
		return fmt.Errorf("decode binary %s response: %w", trace, err)
	}
	if envelope.Code != 0 {
		return fmt.Errorf("binary %s returned code %d message %q", trace, envelope.Code, envelope.Message)
	}
	expected := binaryResponse{
		Trace:      trace,
		Version:    1,
		ItemCount:  2,
		Payload:    "payload-ok",
		ScoreSum:   8,
		FirstLabel: "alpha",
		ItemIDs:    []uint{11, 22},
		Checksum:   12,
	}
	if !reflect.DeepEqual(envelope.Data, expected) {
		return fmt.Errorf("binary %s response = %#v", trace, envelope.Data)
	}
	return nil
}

func postInvalidBinary(baseURL string, body []byte) error {
	resp, err := sendBinary(baseURL, "invalid", body, false)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	var envelope struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&envelope); err != nil {
		return fmt.Errorf("decode invalid binary response: %w", err)
	}
	if envelope.Code == 0 {
		return fmt.Errorf("invalid binary unexpectedly succeeded")
	}
	message := strings.ToLower(envelope.Message)
	if !strings.Contains(message, "magic") && !strings.Contains(message, "const mismatch") && !strings.Contains(message, "exceeds max") {
		return fmt.Errorf("invalid binary message is not diagnostic: %q", envelope.Message)
	}
	return nil
}

func sendBinary(baseURL string, trace string, body []byte, gzipBody bool) (*http.Response, error) {
	var reader io.Reader = bytes.NewReader(body)
	if gzipBody {
		var compressed bytes.Buffer
		gzipWriter := gzip.NewWriter(&compressed)
		if _, err := gzipWriter.Write(body); err != nil {
			return nil, err
		}
		if err := gzipWriter.Close(); err != nil {
			return nil, err
		}
		reader = bytes.NewReader(compressed.Bytes())
	}
	endpoint := baseURL + "/api/binary/packet?trace=" + url.QueryEscape(trace)
	req, err := http.NewRequest(http.MethodPost, endpoint, reader)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	if gzipBody {
		req.Header.Set("Content-Encoding", "gzip")
	}
	return http.DefaultClient.Do(req)
}

func buildDemoPacketFixture(magic string, itemCount uint16, payload string) []byte {
	buf := new(bytes.Buffer)
	writeBytes(buf, []byte(magic)[:4])
	writeUint16(buf, 1)
	writeUint16(buf, 1)
	writeUint32(buf, uint32(binaryschema.DemoFlagsHasPayload|binaryschema.DemoFlagsHasScores))
	writeBytes(buf, []byte{0})
	writeBytes(buf, []byte{0, 0})
	writeUint24(buf, 0x010203)
	writeInt24(buf, 7)
	writeUint16(buf, itemCount)
	writeUint32(buf, uint32(len(payload)))
	writeUint16(buf, 2)
	writeItem(buf, 11, true, 1.25, "alpha")
	writeItem(buf, 22, false, 2.5, "beta")
	writeBytes(buf, []byte(payload))
	writeFloat64(buf, 3.5)
	writeFloat64(buf, 4.5)
	writeUint32(buf, uint32(itemCount)+uint32(len(payload)))
	return buf.Bytes()
}

func writeItem(buf *bytes.Buffer, id uint32, enabled bool, value float64, label string) {
	writeUint32(buf, id)
	if enabled {
		writeBytes(buf, []byte{1})
	} else {
		writeBytes(buf, []byte{0})
	}
	writeFloat64(buf, value)
	writeBytes(buf, []byte{byte(len(label))})
	writeBytes(buf, []byte(label))
}

func writeBytes(buf *bytes.Buffer, value []byte) {
	if _, err := buf.Write(value); err != nil {
		panic(err)
	}
}

func writeUint16(buf *bytes.Buffer, value uint16) {
	var scratch [2]byte
	stdbinary.LittleEndian.PutUint16(scratch[:], value)
	writeBytes(buf, scratch[:])
}

func writeUint24(buf *bytes.Buffer, value uint32) {
	writeBytes(buf, []byte{byte(value), byte(value >> 8), byte(value >> 16)})
}

func writeUint32(buf *bytes.Buffer, value uint32) {
	var scratch [4]byte
	stdbinary.LittleEndian.PutUint32(scratch[:], value)
	writeBytes(buf, scratch[:])
}

func writeInt24(buf *bytes.Buffer, value int32) {
	writeUint24(buf, uint32(value)&0xFFFFFF)
}

func writeFloat64(buf *bytes.Buffer, value float64) {
	var scratch [8]byte
	stdbinary.LittleEndian.PutUint64(scratch[:], math.Float64bits(value))
	writeBytes(buf, scratch[:])
}
