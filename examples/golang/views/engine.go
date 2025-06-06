package views

import (
	provider "demo/views/provider"
	"strings"

	"github.com/gin-gonic/gin"
)

func makeProviders[Q, F, J, P any](
	provSeq string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
) []provider.Provider {
	values := strings.Split(provSeq, "|")
	providers := make([]provider.Provider, len(values))
	for i, v := range values {
		kv := strings.Split(v, "=")
		key := strings.TrimSpace(kv[0])
		var value string

		if len(kv) == 2 {
			value = strings.TrimSpace(kv[1])
		}
		var prov = provider.Select(key, value, handler)

		if prov == nil {
			prov = provider.SelectInternal(key, value, handler)
		}
		if prov == nil {
			prov = provider.GetProvider(key)
		}
		if prov == nil {
			continue
		}
		providers[i] = prov
	}

	return providers
}

func makeHandlers[Q, F, J, P any](
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	provSeq string,
) []gin.HandlerFunc {
	providers := makeProviders(provSeq, handler)
	var handlers = make([]gin.HandlerFunc, len(providers))
	for i, v := range providers {
		handlers[i] = func(ctx *gin.Context) {
			v.Handle(provider.NewContext[Q, F, J, P](ctx))
		}
	}
	return handlers
}

func GET[Q, F, J, P any](
	relativePath string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers(handler, provSeq)
	engine.GET(relativePath, handlers...)
}

func POST[Q, F, J, P any](
	relativePath string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers(handler, provSeq)
	engine.POST(relativePath, handlers...)
}

func PUT[Q, F, J, P any](
	relativePath string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers(handler, provSeq)
	engine.PUT(relativePath, handlers...)
}

func DELETE[Q, F, J, P any](
	relativePath string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers(handler, provSeq)
	engine.DELETE(relativePath, handlers...)
}

func WS[Q, F, J, P any](
	relativePath string,
	handler func(c *provider.Context[Q, F, J, P], req *provider.REQ[Q, F, J]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers(handler, provSeq)
	engine.GET(relativePath, handlers...)
}
