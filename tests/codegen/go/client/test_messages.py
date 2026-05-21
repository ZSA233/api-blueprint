from __future__ import annotations

from .helpers import *


def test_golang_client_generates_named_message_keyframe_helpers(tmp_path):
    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class AssistantInput(Model):
        text = String(description="text")

    class AssistantCancel(Model):
        reason = String(description="reason")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    class AssistantDone(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )
        views.STREAM("/single-events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantSingleMessage",
            delta=AssistantDelta,
        )
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=AssistantInput,
            cancel=AssistantCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    route_dir = output_dir / "routes" / "api" / "demo"
    types_text = (route_dir / "gen_types.go").read_text(encoding="utf-8")
    messages_text = (route_dir / "gen_messages.go").read_text(encoding="utf-8")
    cases_text = (route_dir / "gen_message_cases.go").read_text(encoding="utf-8")

    assert "type AssistantClientMessage struct" not in types_text
    assert "type AssistantClientMessage struct" in messages_text
    assert "type AssistantSingleMessage struct" in messages_text
    assert "const AssistantClientMessageTypeCancel = \"cancel\"" in messages_text
    assert "const AssistantSingleMessageTypeDelta = \"delta\"" in messages_text
    assert "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA)" in messages_text
    assert "func (msg *AssistantClientMessage) DecodeCancel()" in messages_text
    assert "func VisitAssistantSingleMessage[C any](" in cases_text
    assert "type AssistantClientMessageProcessor[C any] interface" in cases_text
    assert "OnInput(ctx C, msg *AssistantClientMessageInputCase) error" in cases_text
    assert "func VisitAssistantClientMessage[C any](" in cases_text
    assert "func AsAssistantClientMessageError(err error)" in cases_text
    assert "AssistantClientMessageErrorHandlerFailed" in cases_text
    assert "func (msg *AssistantClientMessageCancelCase) Decode()" in cases_text
