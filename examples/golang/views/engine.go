package views

import (
	provider "demo/views/provider"
	"strings"

	"github.com/gin-gonic/gin"
)

func makeProviders[Q, B, P any](
	provSeq string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
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

func makeHandlers[Q, B, P any](
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	provSeq string,
) []gin.HandlerFunc {
	providers := makeProviders[Q, B, P](provSeq, handler)
	var handlers = make([]gin.HandlerFunc, len(providers))
	indexer := new(provider.Indexer[Q, B, P])
	for i, v := range providers {
		handlers[i] = func(ctx *gin.Context) {
			v.Handle(provider.NewContext(ctx, indexer))
		}

		switch v.GetName() {
		case provider.PROV_REQ:
			indexer.Req = v.(*provider.ReqProvider[Q, B, P])
		case provider.PROV_RSP:
			indexer.Rsp = v.(*provider.RspProvider[Q, B, P])
		}
	}
	return handlers
}

func GET[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers[Q, B, P](handler, provSeq)
	engine.GET(relativePath, handlers...)
}

func POST[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers[Q, B, P](handler, provSeq)
	engine.POST(relativePath, handlers...)
}

func PUT[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers[Q, B, P](handler, provSeq)
	engine.PUT(relativePath, handlers...)
}

func DELETE[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers[Q, B, P](handler, provSeq)
	engine.DELETE(relativePath, handlers...)
}

func WS[Q, B, P any](
	relativePath string,
	handler func(c *provider.Context[Q, B, P], req *provider.REQ[Q, B]) (rsp *P, err error),
	engine *gin.Engine,
	provSeq string,
) {
	handlers := makeHandlers[Q, B, P](handler, provSeq)
	engine.GET(relativePath, handlers...)
}
