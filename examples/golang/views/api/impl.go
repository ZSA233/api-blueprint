package api

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Ws(
	ctx *CTX_Ws, req *REQ_Ws,
) (rsp *RSP_Ws, err error) {
	return nil, fmt.Errorf("not implemented")
}
