package provider

type ReqContext[Q, F, J, P any] struct {
	Request *REQ[Q, F, J]
	Error   error
}

func (prov *ReqProvider[Q, F, J, P]) Handle(anyCtx ContextInterface) {
	ctx := AdaptContext[Q, F, J, P](anyCtx)
	req, err := prov.makeReq(ctx)
	ctx.Req = &ReqContext[Q, F, J, P]{
		Request: req,
		Error:   err,
	}

	ctx.Gin.Next()
}
