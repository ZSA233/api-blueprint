package main

import (
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
	apiBP := api.NewBlueprint(engine)
	staticBP := static.NewBlueprint(engine)
	_ = engine.Run(addr)
	fmt.Println(apiBP)
	fmt.Println(staticBP)
}
