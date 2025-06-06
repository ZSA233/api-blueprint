package provider

import (
	"context"
	"fmt"
	"log"
	"net/http"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
)

type WsHandleContext[Q, F, J, P any] struct {
	Conn     *websocket.Conn
	Response *P
	Error    error
}

func (prov *WsHandleProvider[Q, F, J, P]) Handle(anyCtx ContextInterface) {
	ctx := AdaptContext[Q, F, J, P](anyCtx)
	var err error

	if ctx.Req == nil {
		err = fmt.Errorf("[WsHandleProvider] fail to get req err[%v]", err)
		_ = ctx.Gin.AbortWithError(http.StatusBadRequest, err)
		return
	}

	req, err := ctx.Req.Request, ctx.Req.Error
	if err != nil {
		fmt.Println(err)
		_ = ctx.Gin.AbortWithError(http.StatusBadRequest, err)
		return
	}
	opts := &websocket.AcceptOptions{
		Subprotocols:       prov.Subs,
		CompressionMode:    websocket.CompressionContextTakeover,
		InsecureSkipVerify: true,
	}

	conn, err := websocket.Accept(
		ctx.Gin.Writer,
		ctx.Gin.Request,
		opts,
	)
	if err != nil {
		log.Printf("[WsHandleProvider] websocket upgrade failed: %v", err)
		ctx.Gin.Status(http.StatusBadRequest)
		return
	}
	ctx.WsHandle = &WsHandleContext[Q, F, J, P]{
		Conn: conn,
	}
	defer conn.Close(websocket.StatusInternalError, "internal error")

	var rsp *P
	rsp, err = prov.Handler(ctx, req)
	ctx.WsHandle.Response = rsp
	ctx.WsHandle.Error = err

	conn.Close(websocket.StatusNormalClosure, "")

	ctx.Gin.Next()
}

func WsJSONReadLoop[MSG any](conn *websocket.Conn, fn func(msg *MSG, err error) (stopped bool), cs ...context.Context) (err error) {
	if conn == nil {
		return nil
	}
	var c context.Context
	if len(cs) > 0 {
		c = cs[0]
	} else {
		c = context.Background()
	}
	for {
		msg := new(MSG)
		err = wsjson.Read(c, conn, msg)
		if fn(msg, err) {
			break
		}

	}
	return
}
