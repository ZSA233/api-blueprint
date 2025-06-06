// Code generated by api-gen-golang; DO NOT EDIT.

package api

import (
	"demo/views/api/demo"

	"github.com/gin-gonic/gin"
)

type Blueprint struct {
	DemoRouter *demo.Router
}

func NewBlueprint(eng *gin.Engine) *Blueprint {
	return &Blueprint{
		DemoRouter: demo.NewImpl(eng),
	}
}
