package hello

import "strings"

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Greet(
	ctx *CTX_Greet, req *REQ_Greet,
) (rsp *RSP_Greet, err error) {
	name := "World"
	if req != nil && req.Q != nil && strings.TrimSpace(req.Q.Name) != "" {
		name = strings.TrimSpace(req.Q.Name)
	}

	return &RSP_Greet{
		Message: "hello world, " + name,
	}, nil
}
