package demo

import "fmt"

func (session *assistantSessionRouteSession) handleMessageError(message *AssistantClientMessage, err error) error {
	if err == nil {
		return nil
	}
	if IsAssistantClientMessageErrorKind(err, AssistantClientMessageErrorNilProcessor) {
		return err
	}
	if IsAssistantClientMessageErrorKind(
		err,
		AssistantClientMessageErrorNilMessage,
		AssistantClientMessageErrorUnknownType,
		AssistantClientMessageErrorDecodeFailed,
		AssistantClientMessageErrorHandlerFailed,
	) {
		return fmt.Errorf("%s message failed: %w", session.messageType(message, err), err)
	}
	return err
}

func (session *assistantSessionRouteSession) messageType(message *AssistantClientMessage, err error) string {
	_ = session
	if messageErr, ok := AsAssistantClientMessageError(err); ok && messageErr.MessageType() != "" {
		return messageErr.MessageType()
	}
	if message != nil {
		return message.Type
	}
	return "unknown"
}
