from __future__ import annotations

from .helpers import *


def test_golang_writer_generates_message_case_visitors(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class Open(Model):
        session_id = String(description="session id")

    class ServerDelta(Model):
        text = String(description="text")

    class ClientInput(Model):
        text = String(description="text")

    class ClientCancel(Model):
        reason = String(description="reason")

    class CloseInfo(Model):
        reason = String(description="reason")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.CHANNEL("/assistant").OPEN(Open).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=ClientInput,
            cancel=ClientCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=ServerDelta,
        ).CLOSE(CloseInfo)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_models = (output_dir / "routes" / "api" / "demo" / "gen_types.go").read_text(
        encoding="utf-8"
    )
    route_messages = (output_dir / "routes" / "api" / "demo" / "gen_messages.go").read_text(
        encoding="utf-8"
    )
    route_cases = (output_dir / "routes" / "api" / "demo" / "gen_message_cases.go").read_text(
        encoding="utf-8"
    )
    route_impl = (output_dir / "routes" / "api" / "demo" / "gen_impl.go").read_text(encoding="utf-8")
    provider_connection = (output_dir / "providers" / "gen_connection.go").read_text(encoding="utf-8")

    assert "type AssistantClientMessage struct" not in route_models
    assert "func NewAssistantClientMessageCancel" not in route_models
    assert "func DispatchAssistantClientMessage" not in route_models
    assert "type AssistantClientMessageHandlers" not in route_models

    assert '"encoding/json"' in route_messages
    assert "type AssistantClientMessage struct" in route_messages
    assert "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA) (*AssistantClientMessage, error)" in route_messages
    assert "func (msg *AssistantClientMessage) DecodeCancel() (*AssistantClientMessage_Cancel_DATA, error)" in route_messages
    assert "func DispatchAssistantClientMessage" not in route_messages
    assert (
        "type CHANNEL_Assistant = providers.Channel[\n"
        "\tOPEN_Assistant,\n"
        "\tAssistantServerMessage,\n"
        "\tAssistantClientMessage,\n"
        "\tCLOSE_Assistant,\n"
        "]"
        in route_models
    )
    assert (
        "type AssistantClientMessageProcessor[C any] interface {\n"
        "\tOnInput(ctx C, msg *AssistantClientMessageInputCase) error\n"
        "\tOnCancel(ctx C, msg *AssistantClientMessageCancelCase) error\n"
        "}"
        in route_cases
    )
    assert "OnAssistantInput" not in route_cases
    assert "OnAssistantCancel" not in route_cases
    assert "type AssistantClientMessageCase interface {" in route_cases
    assert "func VisitAssistantClientMessage[C any](" in route_cases
    assert "processor AssistantClientMessageProcessor[C]," in route_cases
    assert "return wrapAssistantClientMessageHandlerError(message.Type, processor.OnInput(ctx, &AssistantClientMessageInputCase{message: message}))" in route_cases
    assert 'newAssistantClientMessageError(AssistantClientMessageErrorUnknownType, message.Type, fmt.Errorf("unsupported AssistantClientMessage type %q", message.Type))' in route_cases
    assert "type AssistantClientMessageInputCase struct {" in route_cases
    assert "func (msg *AssistantClientMessageInputCase) RawData() []byte" in route_cases
    assert "func (msg *AssistantClientMessageInputCase) Decode() (*AssistantClientMessage_Input_DATA, error)" in route_cases
    assert "data, err := msg.message.DecodeInput()" in route_cases
    assert "return nil, newAssistantClientMessageError(AssistantClientMessageErrorDecodeFailed, msg.Type(), err)" in route_cases
    assert "type AssistantClientMessageError struct {" in route_cases
    assert "Kind AssistantClientMessageErrorKind" in route_cases
    assert "Type string" in route_cases
    assert "Err  error" in route_cases
    assert "AssistantClientMessageErrorNilMessage" in route_cases and '"nil_message"' in route_cases
    assert "AssistantClientMessageErrorNilProcessor" in route_cases and '"nil_processor"' in route_cases
    assert "AssistantClientMessageErrorUnknownType" in route_cases and '"unknown_type"' in route_cases
    assert "AssistantClientMessageErrorDecodeFailed" in route_cases and '"decode_failed"' in route_cases
    assert "AssistantClientMessageErrorHandlerFailed" in route_cases and '"handler_failed"' in route_cases
    assert "func AsAssistantClientMessageError(err error) (*AssistantClientMessageError, bool)" in route_cases
    assert "func IsAssistantClientMessageErrorKind(err error, kinds ...AssistantClientMessageErrorKind) bool" in route_cases
    assert "func (err *AssistantClientMessageError) IsKind(kinds ...AssistantClientMessageErrorKind) bool" in route_cases
    assert "func (err *AssistantClientMessageError) MessageType() string" in route_cases
    assert "func (err *AssistantClientMessageError) Cause() error" in route_cases
    assert 'return fmt.Sprintf("%s: %s: %v", err.Kind, err.Type, err.Err)' in route_cases
    assert "func wrapAssistantClientMessageHandlerError(typ string, err error) error" in route_cases
    assert "return newAssistantClientMessageError(AssistantClientMessageErrorHandlerFailed, typ, err)" in route_cases
    assert "MessageMiddleware" not in provider_connection
    assert "MessageMiddlewareChain" not in provider_connection
    assert "type GenRouterOption func(router *_GenRouter)" not in route_impl
    assert "func NewGenRouter(opts ...GenRouterOption) _GenRouter" not in route_impl
    assert "assistantFlow *AssistantFlow" not in route_impl
    assert "func WithAssistantFlow(flow *AssistantFlow) GenRouterOption" not in route_impl
    assert "return flow.Serve(ctx, channel)" not in route_impl
    assert 'return fmt.Errorf("not implemented")' in route_impl
    assert not (output_dir / "routes" / "api" / "demo" / "gen_assistant_flow.go").exists()

    template_dir = PROJECT_ROOT / "src" / "api_blueprint" / "writer" / "templates" / "golang" / "server" / "views" / "route"
    assert not (template_dir / "__gen_channel_flow.go.j2").exists()
    assert not (template_dir / "__gen_stream_sender.go.j2").exists()
    assert not (template_dir / "dynamic" / "channel_flow.go.j2").exists()
    assert not (template_dir / "dynamic" / "stream_sender.go.j2").exists()
