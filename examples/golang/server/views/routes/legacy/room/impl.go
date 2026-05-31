package room

import (
	"fmt"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) RoomList(ctx *CTX_RoomList, req *REQ_RoomList) (rsp *RSP_RoomList, err error) {
	return nil, fmt.Errorf("not implemented")
}
