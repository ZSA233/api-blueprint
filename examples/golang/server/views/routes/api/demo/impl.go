package demo

import (
	"fmt"

	providers "example.com/project/golang/server/views/providers"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Abc(ctx *CTX_Abc, req *REQ_Abc) (rsp *RSP_Abc, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) TestPost(ctx *CTX_TestPost, req *REQ_TestPost) (rsp *RSP_TestPost, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Z1put(ctx *CTX_Z1put, req *REQ_Z1put) (rsp *RSP_Z1put, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Delete(ctx *CTX_Delete, req *REQ_Delete) (rsp *RSP_Delete, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Ws(ctx *CTX_Ws, req *REQ_Ws) (rsp *RSP_Ws, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) SweepEvents(
	ctx *CTX_SweepEvents,
	stream providers.Stream[OPEN_SweepEvents, SweepStreamMessage, CLOSE_SweepEvents],
) error {
	open := stream.Open()
	serverData := SweepStreamMessage_State_DATA{
		Status: "sweep " + open.RunId + " started",
	}
	serverMessage, err := NewSweepStreamMessageState(&serverData)
	if err != nil {
		return err
	}
	if err := stream.Send(serverMessage); err != nil {
		return err
	}
	return stream.Close(&CLOSE_SweepEvents{Code: 1000, Reason: "example stream complete"})
}

func (impl *Router) AssistantSession(
	ctx *CTX_AssistantSession,
	channel providers.Channel[OPEN_AssistantSession, AssistantServerMessage, AssistantClientMessage, CLOSE_AssistantSession],
) error {
	open := channel.Open()
	clientMessage, err := channel.Recv(ctx)
	if err != nil {
		return err
	}
	if clientMessage == nil {
		return channel.Abort(1003, "empty client message")
	}

	replyText := "session " + open.SessionId + " received a message"
	switch clientMessage.Type {
	case AssistantClientMessageTypeInput:
		input, err := clientMessage.DecodeInput()
		if err != nil {
			return err
		}
		replyText = "session " + open.SessionId + ": " + input.Text
	case AssistantClientMessageTypeCancel:
		cancel, err := clientMessage.DecodeCancel()
		if err != nil {
			return err
		}
		reason := cancel.Reason
		if reason == "" {
			reason = "client cancelled"
		}
		return channel.Close(&CLOSE_AssistantSession{Code: 1000, Reason: reason})
	default:
		return channel.Abort(1003, "unsupported client message type")
	}

	serverData := AssistantServerMessage_Delta_DATA{
		Text: replyText,
	}
	serverMessage, err := NewAssistantServerMessageDelta(&serverData)
	if err != nil {
		return err
	}
	if err := channel.Send(serverMessage); err != nil {
		return err
	}
	return channel.Close(&CLOSE_AssistantSession{Code: 1000, Reason: "example channel complete"})
}

func (impl *Router) PostDeprecated(ctx *CTX_PostDeprecated, req *REQ_PostDeprecated) (rsp *RSP_PostDeprecated, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Raw(ctx *CTX_Raw, req *REQ_Raw) (rsp *RSP_Raw, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) MapModel(ctx *CTX_MapModel, req *REQ_MapModel) (rsp *RSP_MapModel, err error) {
	return nil, fmt.Errorf("not implemented")
}
