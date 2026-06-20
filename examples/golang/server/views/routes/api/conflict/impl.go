package conflict

import types "example.com/project/golang/server/views/routes/api/_gen_types"

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
		Default: "api-default",
		Class:   classValue,
		Enum:    "default",
	}, nil
}
