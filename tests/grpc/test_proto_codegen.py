from __future__ import annotations

import enum
import warnings

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint
import pytest

from api_blueprint.engine.model import Array, Bool, Enum, Int, Map, Object, String, Uint32, Model
from api_blueprint.writer.grpc.proto_writer import render_proto_files


def _block(text: str, header: str) -> str:
    start = text.index(header)
    end = text.index("\n}", start) + 2
    return text[start:end]


class OpenRequest(Model):
    run_id = String(description="run id")


class ServerMessage(Model):
    text = String(description="text")


class ClientMessage(Model):
    text = String(description="text")


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class TaskStatus(enum.IntEnum):
    TASK_STATUS_UNSPECIFIED = 0
    TASK_STATUS_PENDING = 1
    TASK_STATUS_RUNNING = 2


class NestedPayload(Model):
    count = Int(description="count")


class RichPayload(Model):
    name = String(description="name")
    nested = NestedPayload(description="nested")
    colors = Array[Enum[Color]](description="colors")


class MapArrayPayload(Model):
    items = Map[String, Array[NestedPayload]](description="items")


class ANON_Foo_bar(Model):
    value = String(description="value")


class RefPayload(Model):
    nested = ANON_Foo_bar(description="nested")


class SharedOptions(Model):
    __proto_file__ = "shared/browseragent/browser/v1/browser.proto"
    __proto_package__ = "browseragent.browser.v1"
    __proto_go_package__ = "appkit/browseragent/pb/browser/v1;browserpb"

    user = String(description="user", proto_number=1)


class SharedTaskSummary(Model):
    __proto_file__ = "shared/browseragent/task/v1/task.proto"
    __proto_package__ = "browseragent.task.v1"
    __proto_go_package__ = "appkit/browseragent/pb/task/v1;taskpb"

    task_id = String(description="task id", proto_number=1)
    status = Enum[TaskStatus](description="status", proto_number=2)


class ExternalPayload(Model):
    occurred_at = Object(
        description="occurred at",
        proto_type="google.protobuf.Timestamp",
        proto_import="google/protobuf/timestamp.proto",
        proto_number=6,
    )
    attempt = Uint32(description="attempt", proto_number=7)


class ProtoNamePayload(Model):
    top_level_site = String(description="top level site", proto_name="topLevelSite", proto_number=1)
    same_party = Bool(description="same party", proto_optional=True, proto_number=2)


class HelloMessage(Model):
    worker_id = String(description="worker id")


class TaskCallbackMessage(Model):
    task_id = String(description="task id")


class CallbackMessage(Model):
    hello = HelloMessage(description="hello", proto_oneof="msg", proto_number=1)
    task = TaskCallbackMessage(description="task", proto_oneof="msg", proto_number=2)


class DuplicateFieldNumbers(Model):
    first = String(description="first", proto_number=1)
    second = String(description="second", proto_number=1)


def test_grpc_proto_writer_renders_unary_stream_and_bidi_service():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))
        views.STREAM("/events").OPEN(OpenRequest).SERVER_MESSAGE(ServerMessage)
        views.CHANNEL("/chat").OPEN(OpenRequest).SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    assert list(files) == ["api/demo.proto"]
    text = files["api/demo.proto"]
    assert 'syntax = "proto3";' in text
    assert "package example.api.demo;" in text
    assert 'option go_package = "example.com/project/grpc/go/api/demo;demo";' in text
    assert "service DemoService {" in text
    assert "rpc Ping (PingRequest) returns (PingResponse);" in text
    assert "rpc Events (EventsRequest) returns (stream ServerMessage);" in text
    assert "rpc Chat (stream ClientMessage) returns (stream ServerMessage);" in text


def test_grpc_proto_writer_renders_rpc_request_schema_nested_models_and_enums():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/submit").REQ(RichPayload).RSP(RichPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    assert "rpc Submit (SubmitRequest) returns (SubmitResponse);" in text
    request = _block(text, "message SubmitRequest {")
    assert "  string name = 1;" in request
    assert "  NestedPayload nested = 2;" in request
    assert "  repeated Color colors = 3;" in request

    response = _block(text, "message SubmitResponse {")
    assert "  string name = 1;" in response
    assert "  NestedPayload nested = 2;" in response
    assert "  repeated Color colors = 3;" in response

    nested = _block(text, "message NestedPayload {")
    assert "  int64 count = 1;" in nested

    color = _block(text, "enum Color {")
    assert "  COLOR_UNSPECIFIED = 0;" in color
    assert "  COLOR_RED = 1;" in color
    assert "  COLOR_BLUE = 2;" in color


def test_grpc_proto_writer_wraps_repeated_map_values_in_message():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/map-array").RSP(MapArrayPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    response = _block(text, "message MapArrayResponse {")
    assert "  map<string, MapArrayResponseItemsValue> items = 1;" in response
    wrapper = _block(text, "message MapArrayResponseItemsValue {")
    assert "  repeated NestedPayload value = 1;" in wrapper


def test_grpc_proto_writer_normalizes_message_declarations_and_references():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/anon").RSP(RefPayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    response = _block(text, "message AnonResponse {")
    assert "  ANONFooBar nested = 1;" in response
    assert "message ANONFooBar {" in text
    assert "message ANON_Foo_bar {" not in text


def test_grpc_proto_writer_derives_service_packages_to_avoid_cross_file_name_collisions():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/abc").RSP(message=String(description="message"))
    with bp.group("/hello") as views:
        views.GET("/abc").RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    assert "package example.api.demo;" in files["api/demo.proto"]
    assert "package example.api.hello;" in files["api/hello.proto"]
    assert 'option go_package = "example.com/project/grpc/go/api/demo;demo";' in files["api/demo.proto"]
    assert 'option go_package = "example.com/project/grpc/go/api/hello;hello";' in files["api/hello.proto"]


def test_grpc_proto_writer_renders_metadata_field_numbers_oneof_and_well_known_imports():
    bp = Blueprint(root="/api")
    with bp.group("/callback", proto_service="Callback") as views:
        views.POST("/event", proto_rpc="SendEvent").REQ(ExternalPayload).RSP(CallbackMessage)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/callback.proto"]
    assert 'import "google/protobuf/timestamp.proto";' in text
    assert "service Callback {" in text
    assert "rpc SendEvent (SendEventRequest) returns (SendEventResponse);" in text

    request = _block(text, "message SendEventRequest {")
    assert "  google.protobuf.Timestamp occurred_at = 6;" in request
    assert "  uint32 attempt = 7;" in request

    response = _block(text, "message SendEventResponse {")
    assert "  oneof msg {" in response
    assert "    HelloMessage hello = 1;" in response
    assert "    TaskCallbackMessage task = 2;" in response


def test_grpc_proto_writer_imports_cross_file_message_dependencies():
    class LoginRequest(Model):
        options = SharedOptions(description="options", proto_number=1)

    bp = Blueprint(root="/api")
    with bp.group("/steam") as views:
        views.POST("/login").REQ(LoginRequest).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/steam.proto"]
    assert 'import "shared/browseragent/browser/v1/browser.proto";' in text
    request = _block(text, "message LoginRequest {")
    assert "  browseragent.browser.v1.SharedOptions options = 1;" in request
    assert "shared/browseragent/browser/v1/browser.proto" in files
    assert "package browseragent.browser.v1;" in files["shared/browseragent/browser/v1/browser.proto"]
    assert 'option go_package = "appkit/browseragent/pb/browser/v1;browserpb";' in files[
        "shared/browseragent/browser/v1/browser.proto"
    ]


def test_grpc_proto_writer_uses_cross_file_schema_type_for_rpc_response():
    class LoginRequest(Model):
        options = SharedOptions(description="options", proto_number=1)

    bp = Blueprint(root="/api")
    with bp.group("/steam", proto_service="SteamBrowser") as views:
        views.POST("/login-async", proto_rpc="LoginAsync").REQ(LoginRequest).RSP(SharedTaskSummary)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/steam.proto"]
    assert 'import "shared/browseragent/task/v1/task.proto";' in text
    assert "rpc LoginAsync (LoginAsyncRequest) returns (browseragent.task.v1.SharedTaskSummary);" in text
    assert "message LoginAsyncResponse {" not in text
    task_proto = files["shared/browseragent/task/v1/task.proto"]
    assert "enum TaskStatus {" in task_proto
    assert "  TASK_STATUS_UNSPECIFIED = 0;" in task_proto
    assert "  TASK_STATUS_PENDING = 1;" in task_proto
    assert "  TASK_STATUS_RUNNING = 2;" in task_proto


def test_grpc_proto_writer_renders_proto_name_and_optional_field_metadata():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/proto-name").REQ(ProtoNamePayload).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    request = _block(files["api/demo.proto"], "message ProtoNameRequest {")
    assert "  string topLevelSite = 1;" in request
    assert "  optional bool same_party = 2;" in request


def test_grpc_proto_writer_rejects_duplicate_explicit_field_numbers():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/duplicate").REQ(DuplicateFieldNumbers).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])

    with pytest.raises(ValueError, match="duplicate proto field number"):
        render_proto_files(
            graph,
            package="example.api",
            go_package_prefix="example.com/project/grpc/go",
        )


def test_proto_metadata_does_not_leak_as_pydantic_field_kwargs():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bp = Blueprint(root="/api")
        with bp.group("/callback") as views:
            views.POST("/event").REQ(ExternalPayload).RSP(CallbackMessage)

    leaked = [
        warning
        for warning in caught
        if "Extra keys" in str(warning.message) and "proto_" in str(warning.message)
    ]
    assert leaked == []
