package demo

import (
	"fmt"
)

type Router struct{}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Abc(
	ctx *CTX_Abc, req *REQ_Abc,
) (rsp *RSP_Abc, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) TestPost(
	ctx *CTX_TestPost, req *REQ_TestPost,
) (rsp *RSP_TestPost, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) F1put(
	ctx *CTX_F1put, req *REQ_F1put,
) (rsp *RSP_F1put, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Delete(
	ctx *CTX_Delete, req *REQ_Delete,
) (rsp *RSP_Delete, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Ws(
	ctx *CTX_Ws, req *REQ_Ws,
) (rsp *RSP_Ws, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) PostDeprecated(
	ctx *CTX_PostDeprecated, req *REQ_PostDeprecated,
) (rsp *RSP_PostDeprecated, err error) {
	return nil, fmt.Errorf("not implemented")
}
