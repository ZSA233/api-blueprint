package static

import (
	"fmt"
)

type Router struct{}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) DocJson(
	ctx *CTX_DocJson, req *REQ_DocJson,
) (rsp *RSP_DocJson, err error) {
	return nil, fmt.Errorf("not implemented")
}
