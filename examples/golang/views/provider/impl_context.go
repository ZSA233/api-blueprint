package provider

import (
	"fmt"

	"github.com/gin-gonic/gin"
)

const (
	PROV_CONTEXT = "PROVIDER_CONTEXT"
)

type ContextInterface interface {
	GetGin() *gin.Context
}

type Context[Q, F, J, P any] struct {
	Gin      *gin.Context
	Req      *ReqContext[Q, F, J, P]
	Auth     *AuthContext[Q, F, J, P]
	Handle   *HandleContext[Q, F, J, P]
	WsHandle *WsHandleContext[Q, F, J, P]
}

func (ctx *Context[Q, F, J, P]) GetGin() *gin.Context {
	return ctx.Gin
}

func AdaptContext[Q, F, J, P any](anyCtx any) *Context[Q, F, J, P] {
	ctx, ok := anyCtx.(*Context[Q, F, J, P])
	if !ok {
		panic(fmt.Sprintf("[AdaptContext] anyCtx[%T] fail to adapt [%T].", anyCtx, new(Context[Q, F, J, P])))
	}
	return ctx
}

func NewContext[Q, F, J, P any](ctx *gin.Context) *Context[Q, F, J, P] {
	provCtx, found := ctx.Get(PROV_CONTEXT)
	if !found {
		provCtx = &Context[Q, F, J, P]{
			Gin: ctx,
		}
		ctx.Set(PROV_CONTEXT, provCtx)
	}
	return provCtx.(*Context[Q, F, J, P])
}
