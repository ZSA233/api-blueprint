package demo

type assistantSessionMessageProcessor struct{}

var _ AssistantClientMessageProcessor[assistantSessionMessageScope] = (*assistantSessionMessageProcessor)(nil)

func (processor *assistantSessionMessageProcessor) OnInput(
	scope assistantSessionMessageScope,
	msg *AssistantClientMessageInputCase,
) error {
	input, err := msg.Decode()
	if err != nil {
		return err
	}
	open := scope.Channel.Open()
	sessionID := ""
	if open != nil {
		sessionID = open.SessionId
	}
	message, err := NewAssistantServerMessageDelta(&AssistantServerMessage_Delta_DATA{
		Text: "session " + sessionID + ": " + input.Text,
	})
	if err != nil {
		return err
	}
	return scope.Channel.Send(scope.Context, message)
}

func (processor *assistantSessionMessageProcessor) OnCancel(
	scope assistantSessionMessageScope,
	msg *AssistantClientMessageCancelCase,
) error {
	cancel, err := msg.Decode()
	if err != nil {
		return err
	}
	reason := "client cancelled"
	if cancel != nil && cancel.Reason != "" {
		reason = cancel.Reason
	}
	return scope.Channel.Close(scope.Context, &CLOSE_AssistantSession{Code: 1000, Reason: reason})
}
