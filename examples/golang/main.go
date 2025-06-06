package main

import (
	"demo/views/api"
	"demo/views/static"
	"fmt"

	"github.com/gin-gonic/gin"
)

var engine = gin.Default()

func main() {
	apiBP := api.NewBlueprint(engine)
	staticBP := static.NewBlueprint(engine)
	_ = engine.Run("0.0.0.0:2333")
	fmt.Println(apiBP)
	fmt.Println(staticBP)
}
