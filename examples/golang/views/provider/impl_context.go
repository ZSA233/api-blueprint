package provider

import (
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
)

const (
	PROV_CONTEXT = "PROVIDER_CONTEXT"
)

type TransportKind string

const (
	TransportHTTP  TransportKind = "http"
	TransportWails TransportKind = "wails"
)

type WailsRouteContext struct {
	Service   string
	Operation string
	Headers   map[string]string
	Metadata  map[string]any
}

type ContextInterface interface {
	ContextKind() TransportKind
	GetGin() *gin.Context
}

type Context[Q, B, P any] struct {
	Indexer  *Indexer[Q, B, P]
	Kind     TransportKind
	Gin      *gin.Context
	Wails    *WailsRouteContext
	Req      *ReqContext[Q, B, P]
	Auth     *AuthContext[Q, B, P]
	Handle   *HandleContext[Q, B, P]
	WsHandle *WsHandleContext[Q, B, P]
}

func (ctx *Context[Q, B, P]) ContextKind() TransportKind {
	return ctx.Kind
}

func (ctx *Context[Q, B, P]) GetGin() *gin.Context {
	return ctx.Gin
}

func (ctx *Context[Q, B, P]) RequireHTTP() (*gin.Context, error) {
	if ctx.Gin == nil {
		return nil, fmt.Errorf("[Context] transport[%s] does not expose *gin.Context", ctx.Kind)
	}
	return ctx.Gin, nil
}

func (ctx *Context[Q, B, P]) Deadline() (deadline time.Time, ok bool) {
	if ctx.Gin == nil {
		return time.Time{}, false
	}
	return ctx.Gin.Deadline()
}

func (ctx *Context[Q, B, P]) Done() <-chan struct{} {
	if ctx.Gin == nil {
		return nil
	}
	return ctx.Gin.Done()
}

func (ctx *Context[Q, B, P]) Err() error {
	if ctx.Gin == nil {
		return nil
	}
	return ctx.Gin.Err()
}

func (ctx *Context[Q, B, P]) Value(key any) any {
	if ctx.Gin == nil {
		return nil
	}
	return ctx.Gin.Value(key)
}

func AdaptContext[Q, B, P any](anyCtx any) *Context[Q, B, P] {
	ctx, ok := anyCtx.(*Context[Q, B, P])
	if !ok {
		panic(fmt.Sprintf("[AdaptContext] anyCtx[%T] fail to adapt [%T].", anyCtx, new(Context[Q, B, P])))
	}
	return ctx
}

func NewContext[Q, B, P any](
	ctx *gin.Context,
	indexer *Indexer[Q, B, P],
) *Context[Q, B, P] {
	provCtx, found := ctx.Get(PROV_CONTEXT)
	if !found {
		provCtx = &Context[Q, B, P]{
			Indexer: indexer,
			Kind:    TransportHTTP,
			Gin:     ctx,
		}
		ctx.Set(PROV_CONTEXT, provCtx)
	}
	return provCtx.(*Context[Q, B, P])
}
