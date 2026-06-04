package account

import (
	types "example.com/project/golang/server/views/routes/legacy/_gen_types"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) AccountProfile(ctx *CTX_AccountProfile, req *REQ_AccountProfile) (rsp *RSP_AccountProfile, err error) {
	return &types.AccountProfile{
		UserId:   "1000010",
		Nickname: "legacy-user",
	}, nil
}
