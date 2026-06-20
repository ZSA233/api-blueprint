package hello

import (
	types "example.com/project/golang/server/views/routes/api/_gen_types"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Abc(ctx *CTX_Abc, req *REQ_Abc) (rsp *RSP_Abc, err error) {
	key := req.Query.Type
	if key == "" {
		key = "ping"
	}
	return &RSP_Abc{
		"hello": {Haha: 1001},
		key:     {Haha: 1},
	}, nil
}

func (impl *Router) MapEnum(ctx *CTX_MapEnum, req *REQ_MapEnum) (rsp *RSP_MapEnum, err error) {
	return &RSP_MapEnum{
		"a": {Haha: 11},
		"b": {Haha: 22},
	}, nil
}

func (impl *Router) ListEnum(ctx *CTX_ListEnum, req *REQ_ListEnum) (rsp *RSP_ListEnum, err error) {
	return &RSP_ListEnum{"a", "b"}, nil
}

func (impl *Router) String(ctx *CTX_String, req *REQ_String) (rsp *RSP_String, err error) {
	value := RSP_String("hello-string")
	return &value, nil
}

func (impl *Router) Uint64(ctx *CTX_Uint64, req *REQ_Uint64) (rsp *RSP_Uint64, err error) {
	value := RSP_Uint64(9007199254740991)
	return &value, nil
}

func (impl *Router) StringEmun(ctx *CTX_StringEmun, req *REQ_StringEmun) (rsp *RSP_StringEmun, err error) {
	value := RSP_StringEmun("a")
	return &value, nil
}

func (impl *Router) HelloWay(ctx *CTX_HelloWay, req *REQ_HelloWay) (rsp *RSP_HelloWay, err error) {
	var value RSP_HelloWay = map[string]string{"arg1": req.Query.Arg1}
	return &value, nil
}

var _ = types.ApiHelloMap{}
