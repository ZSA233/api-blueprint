package main

import (
	"example.com/project/golang/server/views/transports/http/alt"
	"example.com/project/golang/server/views/transports/http/api"
	"example.com/project/golang/server/views/transports/http/static"
	"fmt"
	"os"

	"github.com/gin-gonic/gin"
)

var engine = gin.Default()

func main() {
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
