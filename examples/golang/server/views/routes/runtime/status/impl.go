package status

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) RuntimeCurrentStatus(ctx *CTX_RuntimeCurrentStatus, req *REQ_RuntimeCurrentStatus) (rsp *RSP_RuntimeCurrentStatus, err error) {
	return nil, fmt.Errorf("not implemented")
}
