package api

import (
	types "example.com/project/golang/server/views/routes/api/_gen_types"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) HelloChannel(
	ctx *CTX_HelloChannel,
	channel CHANNEL_HelloChannel,
) error {
	if _, err := channel.Recv(ctx); err != nil {
		return err
	}
	if err := channel.Send(ctx, &types.HelloChannelMessage{
		Type: "pong",
		Data: map[string]string{"source": "go"},
	}); err != nil {
		return err
	}
	return channel.Close(ctx, &types.DefaultConnectionClose{Code: 1000, Reason: "single channel complete"})
}
