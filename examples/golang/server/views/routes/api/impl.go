package api

import (
	"fmt"
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
	return fmt.Errorf("not implemented")
}
