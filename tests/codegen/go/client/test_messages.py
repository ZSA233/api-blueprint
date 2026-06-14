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
    client_message_text = (route_dir / "gen_assistant_client_message_message.go").read_text(encoding="utf-8")
    client_constructors_text = (route_dir / "gen_assistant_client_message_constructors.go").read_text(
        encoding="utf-8"
    )
    client_processor_text = (route_dir / "gen_assistant_client_message_processor.go").read_text(encoding="utf-8")
    client_visitor_text = (route_dir / "gen_assistant_client_message_visitor.go").read_text(encoding="utf-8")
    client_cases_text = (route_dir / "gen_assistant_client_message_cases.go").read_text(encoding="utf-8")
    single_message_text = (route_dir / "gen_assistant_single_message_message.go").read_text(encoding="utf-8")
    single_constructors_text = (route_dir / "gen_assistant_single_message_constructors.go").read_text(
        encoding="utf-8"
    )
    single_visitor_text = (route_dir / "gen_assistant_single_message_visitor.go").read_text(encoding="utf-8")

    assert not (route_dir / "gen_messages.go").exists()
    assert not (route_dir / "gen_message_cases.go").exists()

    assert "type AssistantClientMessage struct" not in types_text
    assert "type AssistantClientMessage struct" in client_message_text
    assert "type AssistantSingleMessage struct" in single_message_text
    assert "const AssistantClientMessageTypeCancel = \"cancel\"" in client_constructors_text
    assert "const AssistantSingleMessageTypeDelta = \"delta\"" in single_constructors_text
    assert "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA)" in client_constructors_text
    assert "func (msg *AssistantClientMessage) DecodeCancel()" in client_constructors_text
    assert "func VisitAssistantSingleMessage[C any](" in single_visitor_text
    assert "type AssistantClientMessageProcessor[C any] interface" in client_processor_text
    assert "OnInput(ctx C, msg *AssistantClientMessageInputCase) error" in client_processor_text
    assert "func VisitAssistantClientMessage[C any](" in client_visitor_text
    assert "func AsAssistantClientMessageError(err error)" in client_visitor_text
    assert "AssistantClientMessageErrorHandlerFailed" in client_visitor_text
    assert "func (msg *AssistantClientMessageCancelCase) Decode()" in client_cases_text


def test_golang_client_shards_large_named_message_cases(tmp_path):
    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    variants: dict[str, type[Model]] = {}
    for index in range(55):
        variants[f"event_{index:02d}"] = type(
            f"AssistantEvent{index:02d}",
            (Model,),
            {"__module__": __name__, "value": String(description="value")},
        )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            **variants,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
        )

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
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
