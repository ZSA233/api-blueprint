package main

import (
	"demo/views/api/_http"
	"demo/views/static/_http"
	"fmt"

	"github.com/gin-gonic/gin"
)

var engine = gin.Default()

func main() {
	apiBP := apihttp.NewBlueprint(engine)
	staticBP := statichttp.NewBlueprint(engine)
	_ = engine.Run("0.0.0.0:2333")
	fmt.Println(apiBP)
	fmt.Println(staticBP)
}
