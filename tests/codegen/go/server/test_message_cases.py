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
    route_dir = output_dir / "routes" / "api" / "demo"
    client_message = (route_dir / "gen_assistant_client_message_message.go").read_text(encoding="utf-8")
    client_constructors = (route_dir / "gen_assistant_client_message_constructors.go").read_text(
        encoding="utf-8"
    )
    client_processor = (route_dir / "gen_assistant_client_message_processor.go").read_text(encoding="utf-8")
    client_visitor = (route_dir / "gen_assistant_client_message_visitor.go").read_text(encoding="utf-8")
    client_cases = (route_dir / "gen_assistant_client_message_cases.go").read_text(
        encoding="utf-8"
    )
    server_message = (route_dir / "gen_assistant_server_message_message.go").read_text(encoding="utf-8")
    route_impl = (output_dir / "routes" / "api" / "demo" / "gen_impl.go").read_text(encoding="utf-8")
    provider_connection = (output_dir / "providers" / "gen_connection.go").read_text(encoding="utf-8")

    assert not (route_dir / "gen_messages.go").exists()
    assert not (route_dir / "gen_message_cases.go").exists()

    assert "type AssistantClientMessage struct" not in route_models
    assert "func NewAssistantClientMessageCancel" not in route_models
    assert "func DispatchAssistantClientMessage" not in route_models
    assert "type AssistantClientMessageHandlers" not in route_models

    assert '"encoding/json"' in client_message
    assert "type AssistantClientMessage struct" in client_message
    assert "type AssistantServerMessage struct" in server_message
    assert "func NewAssistantClientMessageCancel" in client_constructors
    assert "data *AssistantClientMessage_Cancel_DATA" in client_constructors
    assert (
        "func (msg *AssistantClientMessage) DecodeCancel() (*AssistantClientMessage_Cancel_DATA, error)"
        in client_constructors
    )
    assert "func DispatchAssistantClientMessage" not in client_message
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
        in client_processor
    )
    assert "OnAssistantInput" not in client_processor
    assert "OnAssistantCancel" not in client_processor
    assert "type AssistantClientMessageCase interface {" in client_processor
    assert "func VisitAssistantClientMessage[C any](" in client_visitor
    assert "processor AssistantClientMessageProcessor[C]," in client_visitor
    assert "return wrapAssistantClientMessageHandlerError(" in client_visitor
    assert "processor.OnInput(ctx, &AssistantClientMessageInputCase{message: message})" in client_visitor
    assert (
        'fmt.Errorf("unsupported AssistantClientMessage type %q", message.Type)'
        in client_visitor
    )
    assert "type AssistantClientMessageInputCase struct {" in client_cases
    assert "func (msg *AssistantClientMessageInputCase) RawData() []byte" in client_cases
    assert "func (msg *AssistantClientMessageInputCase) Decode()" in client_cases
    assert "(*AssistantClientMessage_Input_DATA, error)" in client_cases
    assert "data, err := msg.message.DecodeInput()" in client_cases
    assert (
        "return nil, newAssistantClientMessageError(AssistantClientMessageErrorDecodeFailed, msg.Type(), err)"
        in client_cases
    )
    assert "type AssistantClientMessageError struct {" in client_visitor
    assert "Kind AssistantClientMessageErrorKind" in client_visitor
    assert "Type string" in client_visitor
    assert "Err  error" in client_visitor
    assert "AssistantClientMessageErrorNilMessage" in client_visitor and '"nil_message"' in client_visitor
    assert "AssistantClientMessageErrorNilProcessor" in client_visitor and '"nil_processor"' in client_visitor
    assert "AssistantClientMessageErrorUnknownType" in client_visitor and '"unknown_type"' in client_visitor
    assert "AssistantClientMessageErrorDecodeFailed" in client_visitor and '"decode_failed"' in client_visitor
    assert "AssistantClientMessageErrorHandlerFailed" in client_visitor and '"handler_failed"' in client_visitor
    assert "func AsAssistantClientMessageError(err error) (*AssistantClientMessageError, bool)" in client_visitor
    assert "func IsAssistantClientMessageErrorKind(" in client_visitor
    assert "func (err *AssistantClientMessageError) IsKind(" in client_visitor
    assert "func (err *AssistantClientMessageError) MessageType() string" in client_visitor
    assert "func (err *AssistantClientMessageError) Cause() error" in client_visitor
    assert 'return fmt.Sprintf("%s: %s: %v", err.Kind, err.Type, err.Err)' in client_visitor
    assert "func wrapAssistantClientMessageHandlerError(typ string, err error) error" in client_visitor
    assert "return newAssistantClientMessageError(AssistantClientMessageErrorHandlerFailed, typ, err)" in client_visitor
    assert "MessageMiddleware" not in provider_connection
    assert "MessageMiddlewareChain" not in provider_connection
    assert "type GenRouterOption func(router *_GenRouter)" not in route_impl
    assert "func NewGenRouter(opts ...GenRouterOption) _GenRouter" not in route_impl
    assert "assistantFlow *AssistantFlow" not in route_impl
    assert "func WithAssistantFlow(flow *AssistantFlow) GenRouterOption" not in route_impl
    assert "return flow.Serve(ctx, channel)" not in route_impl
    assert 'return fmt.Errorf("not implemented")' in route_impl
    assert not (output_dir / "routes" / "api" / "demo" / "gen_assistant_flow.go").exists()

    template_dir = (
        PROJECT_ROOT
        / "src"
        / "api_blueprint"
        / "writer"
        / "templates"
        / "golang"
        / "server"
        / "views"
        / "route"
    )
    assert not (template_dir / "__gen_channel_flow.go.j2").exists()
    assert not (template_dir / "__gen_stream_sender.go.j2").exists()
    assert not (template_dir / "dynamic" / "channel_flow.go.j2").exists()
    assert not (template_dir / "dynamic" / "stream_sender.go.j2").exists()


def test_golang_writer_shards_large_message_case_files(tmp_path):
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

    class CloseInfo(Model):
        reason = String(description="reason")

    variants: dict[str, type[Model]] = {}
    for index in range(55):
        variants[f"event_{index:02d}"] = type(
            f"ClientEvent{index:02d}",
            (Model,),
            {"__module__": __name__, "value": String(description="value")},
        )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.CHANNEL("/assistant").OPEN(Open).CLIENT_MESSAGE(
            "AssistantClientMessage",
            **variants,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=ServerDelta,
        ).CLOSE(CloseInfo)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_dir = output_dir / "routes" / "api" / "demo"
    cases_001 = (route_dir / "gen_assistant_client_message_cases_001.go").read_text(encoding="utf-8")
    cases_002 = (route_dir / "gen_assistant_client_message_cases_002.go").read_text(encoding="utf-8")
    visitor_text = (route_dir / "gen_assistant_client_message_visitor.go").read_text(encoding="utf-8")

    assert not (route_dir / "gen_assistant_client_message_cases.go").exists()
    assert "type AssistantClientMessageEvent00Case struct" in cases_001
    assert "type AssistantClientMessageEvent49Case struct" in cases_001
    assert "type AssistantClientMessageEvent50Case struct" not in cases_001
    assert "type AssistantClientMessageEvent50Case struct" in cases_002
    assert "type AssistantClientMessageEvent54Case struct" in cases_002
    assert "case AssistantClientMessageTypeEvent54:" in visitor_text
