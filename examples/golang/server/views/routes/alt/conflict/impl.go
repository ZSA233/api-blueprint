package conflict

import types "example.com/project/golang/server/views/routes/alt/_gen_types"

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Default(ctx *CTX_Default, req *REQ_Default) (rsp *RSP_Default, err error) {
	classValue := ""
	if req != nil && req.Query != nil {
		classValue = req.Query.Class
	}
	return &types.ConflictModel{
		Default: "alt-default",
		Class:   classValue,
		Enum:    "class",
	}, nil
}
