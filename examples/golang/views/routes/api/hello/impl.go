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

func (impl *Router) Abc(
	ctx *CTX_Abc, req *REQ_Abc,
) (rsp *RSP_Abc, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) MapEnum(
	ctx *CTX_MapEnum, req *REQ_MapEnum,
) (rsp *RSP_MapEnum, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) ListEnum(
	ctx *CTX_ListEnum, req *REQ_ListEnum,
) (rsp *RSP_ListEnum, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) String(
	ctx *CTX_String, req *REQ_String,
) (rsp *RSP_String, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Uint64(
	ctx *CTX_Uint64, req *REQ_Uint64,
) (rsp *RSP_Uint64, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) StringEmun(
	ctx *CTX_StringEmun, req *REQ_StringEmun,
) (rsp *RSP_StringEmun, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) HelloWay(
	ctx *CTX_HelloWay, req *REQ_HelloWay,
) (rsp *RSP_HelloWay, err error) {
	return nil, fmt.Errorf("not implemented")
}
