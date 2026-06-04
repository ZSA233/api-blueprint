package room

import (
	types "example.com/project/golang/server/views/routes/legacy/_gen_types"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) RoomList(ctx *CTX_RoomList, req *REQ_RoomList) (rsp *RSP_RoomList, err error) {
	return &RSP_RoomList_BODY{
		Rooms: []*types.RoomSummary{
			{RoomId: "100", Title: "legacy-room"},
		},
	}, nil
}
