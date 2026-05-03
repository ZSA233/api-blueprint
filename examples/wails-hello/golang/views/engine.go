package views

import (
	provider "example.com/api-blueprint/wails-hello/golang/views/provider"

	"github.com/gin-gonic/gin"
)

func makeHandler[Q, B, P any](
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	provSeq string,
) gin.HandlerFunc {
	executor := provider.NewRouteExecutor[Q, B, P](provSeq, handler)
	return func(ginCtx *gin.Context) {
		ctx := provider.NewHTTPContext[Q, B, P](ginCtx)
		if err := executor.Run(ctx); err != nil {
			_ = ginCtx.AbortWithError(-1, err)
		}
	}
}

func GET[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	engine.GET(relativePath, makeHandler[Q, B, P](handler, provSeq))
}

func POST[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	engine.POST(relativePath, makeHandler[Q, B, P](handler, provSeq))
}

func PUT[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	engine.PUT(relativePath, makeHandler[Q, B, P](handler, provSeq))
}

func DELETE[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	engine.DELETE(relativePath, makeHandler[Q, B, P](handler, provSeq))
}

func WS[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	engine.GET(relativePath, makeHandler[Q, B, P](handler, provSeq))
}
