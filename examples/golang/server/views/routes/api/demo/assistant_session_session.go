package demo

import "context"

func (impl *Router) AssistantSession(ctx *CTX_AssistantSession, channel CHANNEL_AssistantSession) error {
	session := newAssistantSessionRouteSession(impl, ctx, channel, &assistantSessionMessageProcessor{})
	return session.Serve()
}

type assistantSessionRouteSession struct {
	impl      *Router
	routeCtx  *CTX_AssistantSession
	channel   CHANNEL_AssistantSession
	processor AssistantClientMessageProcessor[assistantSessionMessageScope]
}

type assistantSessionMessageScope struct {
	Context context.Context
	Route   *CTX_AssistantSession
	Channel CHANNEL_AssistantSession
}

func newAssistantSessionRouteSession(
	impl *Router,
	ctx *CTX_AssistantSession,
	channel CHANNEL_AssistantSession,
	processor AssistantClientMessageProcessor[assistantSessionMessageScope],
) *assistantSessionRouteSession {
	return &assistantSessionRouteSession{
		impl:      impl,
		routeCtx:  ctx,
		channel:   channel,
		processor: processor,
	}
}

func (session *assistantSessionRouteSession) Serve() error {
	if session == nil {
		return nil
	}
	for {
		message, err := session.channel.Recv(session.Context())
		if err != nil {
			return session.normalizeTransportError(err)
		}
		if err := VisitAssistantClientMessage(session.messageScope(), message, session.processor); err != nil {
			if handled := session.handleMessageError(message, err); handled != nil {
				return handled
			}
		}
	}
}

func (session *assistantSessionRouteSession) Context() context.Context {
	if session == nil || session.routeCtx == nil {
		return context.Background()
	}
	return session.routeCtx
}

func (session *assistantSessionRouteSession) messageScope() assistantSessionMessageScope {
	return assistantSessionMessageScope{
		Context: session.Context(),
		Route:   session.routeCtx,
		Channel: session.channel,
	}
}

func (session *assistantSessionRouteSession) normalizeTransportError(err error) error {
	return err
}
