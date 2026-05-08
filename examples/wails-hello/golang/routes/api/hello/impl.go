package hello

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Greet(ctx *CTX_Greet, req *REQ_Greet) (rsp *RSP_Greet, err error) {
	return nil, fmt.Errorf("not implemented")
}
