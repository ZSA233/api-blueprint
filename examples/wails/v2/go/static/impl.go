package static

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) DocJson(
	ctx *CTX_DocJson, req *REQ_DocJson,
) (rsp *RSP_DocJson, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Dochaha(
	ctx *CTX_Dochaha, req *REQ_Dochaha,
) (rsp *RSP_Dochaha, err error) {
	return nil, fmt.Errorf("not implemented")
}
