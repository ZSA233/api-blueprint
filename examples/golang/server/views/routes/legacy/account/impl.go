package account

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) AccountProfile(ctx *CTX_AccountProfile, req *REQ_AccountProfile) (rsp *RSP_AccountProfile, err error) {
	return nil, fmt.Errorf("not implemented")
}
