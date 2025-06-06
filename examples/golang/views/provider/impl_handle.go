package provider

import (
	"fmt"
	"net/http"
)

type HandleContext[Q, F, J, P any] struct {
	Response *P
	Error    error
}

func (prov *HandleProvider[Q, F, J, P]) Handle(anyCtx ContextInterface) {
	ctx := AdaptContext[Q, F, J, P](anyCtx)
	var err error

	if ctx.Req == nil {
		err = fmt.Errorf("[HandleProvider] fail to get req err[%v]", err)
		_ = ctx.Gin.AbortWithError(http.StatusBadRequest, err)
		return
	}

	req, err := ctx.Req.Request, ctx.Req.Error
	if err != nil {
		fmt.Println(err)
		_ = ctx.Gin.AbortWithError(http.StatusBadRequest, err)
		return
	}

	var rsp *P
	rsp, err = prov.Handler(ctx, req)
	ctx.Handle = &HandleContext[Q, F, J, P]{
		Response: rsp,
		Error:    err,
	}

	ctx.Gin.Next()
}
