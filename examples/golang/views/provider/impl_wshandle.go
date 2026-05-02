package provider

import (
	"context"
	"net/http"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
)

type HTTPWebSocketConnection struct {
	conn *websocket.Conn
}

func NewHTTPWebSocketConnection(conn *websocket.Conn) *HTTPWebSocketConnection {
	return &HTTPWebSocketConnection{conn: conn}
}

func (conn *HTTPWebSocketConnection) Transport() TransportKind {
	return TransportHTTP
}

func (conn *HTTPWebSocketConnection) SessionID() string {
	return ""
}

func (conn *HTTPWebSocketConnection) Subprotocol() string {
	if conn == nil || conn.conn == nil {
		return ""
	}
	return conn.conn.Subprotocol()
}

func (conn *HTTPWebSocketConnection) Underlying() any {
	if conn == nil {
		return nil
	}
	return conn.conn
}

func (conn *HTTPWebSocketConnection) ReadJSON(ctx context.Context, target any) error {
	if conn == nil || conn.conn == nil {
		return nil
	}
	return wsjson.Read(ctx, conn.conn, target)
}

func (conn *HTTPWebSocketConnection) WriteJSON(ctx context.Context, payload any) error {
	if conn == nil || conn.conn == nil {
		return nil
	}
	return wsjson.Write(ctx, conn.conn, payload)
}

func (conn *HTTPWebSocketConnection) Close(code int, reason string) error {
	if conn == nil || conn.conn == nil {
		return nil
	}
	return conn.conn.Close(websocket.StatusCode(code), reason)
}

type WsHandleContext[Q, B, P any] struct {
	Conn     SocketConnection
	Response *P
	Error    error
}

func (prov *WsHandleProvider[Q, B, P]) Handle(anyCtx ContextInterface) {
	ctx := AdaptContext[Q, B, P](anyCtx)
	var err error
	httpCtx, httpErr := ctx.RequireHTTP()
	if httpErr != nil {
		return
	}

	if ctx.Req == nil {
		_ = httpCtx.AbortWithError(http.StatusBadRequest, err)
		return
	}

	req, err := ctx.Req.Request, ctx.Req.Error
	if err != nil {
		_ = httpCtx.AbortWithError(http.StatusBadRequest, err)
		return
	}
	opts := &websocket.AcceptOptions{
		Subprotocols:    prov.Subs,
		CompressionMode: websocket.CompressionContextTakeover,
		// InsecureSkipVerify: true,
	}

	conn, err := websocket.Accept(
		httpCtx.Writer,
		httpCtx.Request,
		opts,
	)
	if err != nil {
		_ = httpCtx.AbortWithError(http.StatusBadRequest, err)
		return
	}
	if conn.Subprotocol() == "" {
		conn.Close(websocket.StatusPolicyViolation, "subprotocol required")
		return
	}
	defer conn.CloseNow()

	ctx.WsHandle = &WsHandleContext[Q, B, P]{
		Conn: NewHTTPWebSocketConnection(conn),
	}

	var rsp *P
	rsp, err = prov.Handler(ctx, req)
	ctx.WsHandle.Response = rsp
	ctx.WsHandle.Error = err
	if err != nil {
		ctx.WsHandle.Conn.Close(int(websocket.StatusInternalError), err.Error())
	} else {
		ctx.WsHandle.Conn.Close(int(websocket.StatusNormalClosure), "")
	}
	// 在ws中，忽略更深层的中间件
}

func WsJSONReadLoop[MSG any](conn SocketConnection, fn func(msg *MSG, err error) (stopped bool), cs ...context.Context) (err error) {
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
		err = conn.ReadJSON(c, msg)
		if fn(msg, err) {
			break
		}

	}
	return
}
