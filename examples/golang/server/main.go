package main

import (
	"bytes"
	httptransport "example.com/project/golang/server/views/transports/http"
	"example.com/project/golang/server/views/transports/http/alt"
	"example.com/project/golang/server/views/transports/http/api"
	"example.com/project/golang/server/views/transports/http/static"
	"fmt"
	"io"
	"os"

	"github.com/gin-gonic/gin"
)

var engine = gin.Default()

func main() {
	configureBinaryDecoders()
	addr := os.Getenv("API_BLUEPRINT_EXAMPLE_ADDR")
	if addr == "" {
		addr = "0.0.0.0:2333"
	}
	engine.Use(func(ctx *gin.Context) {
		if ctx.Request.URL.Path == "/api/demo/abc" && ctx.GetHeader("x-token") != "conformance-token" {
			ctx.AbortWithStatusJSON(418, gin.H{"detail": "missing conformance header"})
			return
		}
		if ctx.Request.URL.Path == "/api/demo/request-options" &&
			(ctx.GetHeader("x-options-default") != "default" || ctx.GetHeader("x-options-token") != "per-call") {
			ctx.AbortWithStatusJSON(418, gin.H{"detail": "request options headers missing"})
			return
		}
		ctx.Next()
	})
	altBP := alt.NewBlueprint(engine)
	apiBP := api.NewBlueprint(engine)
	staticBP := static.NewBlueprint(engine)
	_ = engine.Run(addr)
	fmt.Println(altBP)
	fmt.Println(apiBP)
	fmt.Println(staticBP)
}

func configureBinaryDecoders() {
	if os.Getenv("API_BLUEPRINT_ENABLE_BR_STUB") != "1" {
		return
	}
	config := httptransport.DefaultServerConfig()
	config.BinaryContentDecoders = map[string]httptransport.BinaryContentDecoder{
		"br": brStubDecoder,
	}
	httptransport.SetServerConfig(config)
}

func brStubDecoder(reader io.Reader) (io.ReadCloser, error) {
	body, err := io.ReadAll(reader)
	if err != nil {
		return nil, err
	}
	prefix := []byte("BRSTUB\x00")
	if !bytes.HasPrefix(body, prefix) {
		return nil, fmt.Errorf("invalid br stub payload")
	}
	return io.NopCloser(bytes.NewReader(body[len(prefix):])), nil
}
