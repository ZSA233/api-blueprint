from __future__ import annotations

import enum
import warnings

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint
import pytest

from api_blueprint.engine.model import (
    AnyPayload,
    AnyValue,
    Array,
    Bool,
    DateTime,
    Enum,
    Int,
    JSONValue,
    Map,
    Object,
    String,
    Struct,
    Timestamp,
    Uint32,
    Model,
    field,
)
from api_blueprint.config.resolved import ResolvedGrpcProtoFileConfig
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
    __module__ = "blueprints.shared.browseragent.task"

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


class LayoutBrowserOptions(Model):
    __module__ = "blueprints.shared.browseragent.browser"

    user = field(1, String(description="user"))


class LayoutTaskSummary(Model):
    __module__ = "blueprints.shared.browseragent.task"

    task_id = field(1, String(description="task id"))
    status = field(2, Enum[TaskStatus](description="status"))


class LayoutLoginRequest(Model):
    __module__ = "blueprints.services.steamagent.browser.steam"

    options = field(1, LayoutBrowserOptions(description="options"))


class FieldSemanticsPayload(Model):
    name = field(1, String(description="name"), optional=True)
    nested = field(2, LayoutBrowserOptions(description="options"), optional=True)
    tags = field(3, Array[String](description="tags"), optional=True)
    attrs = field(4, Map[String, String](description="attrs"), optional=True)
    occurred_at = field(5, DateTime(description="occurred at"))
    payload = field(6, AnyValue(description="payload"))
    metadata = field(7, JSONValue(description="metadata"))


class ChoiceSuccess(Model):
    message = field(1, String(description="message"))


class ChoiceError(Model):
    code = field(1, String(description="code"))


class GenericChoicePayload(Model):
    success = field(1, ChoiceSuccess(description="success"), choice="result")
    error = field(2, ChoiceError(description="error"), choice="result")


class GenericAliasPayload(Model):
    http_only = field(1, Bool(description="http only"), alias="httpOnly")
    default_name = field(2, Bool(description="default name"))


class ExternalTaskStatusPayload(Model):
    __module__ = "blueprints.services.callback"

    status = field(1, Enum[TaskStatus](description="status"))


def _layout(
    *,
    file: str,
    package: str,
    go_package: str,
    schema_modules: tuple[str, ...] = (),
    route_paths: tuple[str, ...] = (),
    service: str | None = None,
    schema_names: tuple[str, ...] = (),
) -> ResolvedGrpcProtoFileConfig:
    return ResolvedGrpcProtoFileConfig(
        file=file,
        package=package,
        go_package=go_package,
        schema_modules=schema_modules,
        schema_names=schema_names,
        route_paths=route_paths,
        route_ids=(),
        service_ids=(),
        service=service,
    )


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


def test_grpc_proto_writer_uses_config_layout_without_proto_metadata():
    bp = Blueprint(root="/services/steamagent/browser")
    with bp.group("/steam/v1") as views:
        views.POST("/login-async", proto_rpc="LoginAsync").REQ(LayoutLoginRequest).RSP(LayoutTaskSummary)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="contracts.grpc",
        go_package_prefix="contracts/grpc",
        proto_files=(
            _layout(
                file="shared/browseragent/browser/v1/browser.proto",
                package="browseragent.browser.v1",
                go_package="appkit/browseragent/pb/browser/v1;browserpb",
                schema_modules=("blueprints.shared.browseragent.browser",),
            ),
            _layout(
                file="shared/browseragent/task/v1/task.proto",
                package="browseragent.task.v1",
                go_package="appkit/browseragent/pb/task/v1;taskpb",
                schema_modules=("blueprints.shared.browseragent.task",),
            ),
            _layout(
                file="services/steamagent/browser/steam/v1/steam.proto",
                package="steamagent.browser.steam.v1",
                go_package="steam-agent/internal/grpc/pb/browser/steam/v1;steampb",
                schema_modules=("blueprints.services.steamagent.browser.steam",),
                route_paths=("/services/steamagent/browser/steam/v1/**",),
                service="SteamBrowser",
            ),
        ),
    )

    steam = files["services/steamagent/browser/steam/v1/steam.proto"]
    assert "package steamagent.browser.steam.v1;" in steam
    assert 'option go_package = "steam-agent/internal/grpc/pb/browser/steam/v1;steampb";' in steam
    assert 'import "shared/browseragent/browser/v1/browser.proto";' in steam
    assert 'import "shared/browseragent/task/v1/task.proto";' in steam
    assert "service SteamBrowser {" in steam
    assert "rpc LoginAsync (LoginAsyncRequest) returns (browseragent.task.v1.LayoutTaskSummary);" in steam
    request = _block(steam, "message LoginAsyncRequest {")
    assert "  browseragent.browser.v1.LayoutBrowserOptions options = 1;" in request


def test_grpc_proto_writer_uses_config_layout_for_same_named_models():
    RequestPayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.request",
            "value": field(1, String(description="value")),
        },
    )
    ResponsePayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.response",
            "message": field(1, String(description="message")),
        },
    )

    bp = Blueprint(root="/api")
    with bp.group("/shared") as views:
        views.POST("/submit").REQ(RequestPayload).RSP(ResponsePayload)

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
        proto_files=(
            _layout(
                file="request.proto",
                package="request.v1",
                go_package="example.com/project/request;requestpb",
                schema_modules=("blueprints.request",),
            ),
            _layout(
                file="response.proto",
                package="response.v1",
                go_package="example.com/project/response;responsepb",
                schema_modules=("blueprints.response",),
            ),
            _layout(
                file="service.proto",
                package="service.v1",
                go_package="example.com/project/service;servicepb",
                route_paths=("/api/shared/**",),
                service="SharedService",
            ),
        ),
    )

    service = files["service.proto"]
    assert 'import "request.proto";' in service
    assert 'import "response.proto";' in service
    assert "rpc Submit (request.v1.SharedPayload) returns (response.v1.SharedPayload);" in service
    assert "message SharedPayload {" in files["request.proto"]
    assert "  string value = 1;" in files["request.proto"]
    assert "message SharedPayload {" in files["response.proto"]
    assert "  string message = 1;" in files["response.proto"]


def test_grpc_proto_writer_uses_field_helper_optional_and_semantic_well_known_types():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/field-semantics").REQ(FieldSemanticsPayload).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    text = files["api/demo.proto"]
    assert 'import "google/protobuf/any.proto";' in text
    assert 'import "google/protobuf/struct.proto";' in text
    assert 'import "google/protobuf/timestamp.proto";' in text
    request = _block(text, "message FieldSemanticsRequest {")
    assert "  optional string name = 1;" in request
    assert "  LayoutBrowserOptions nested = 2;" in request
    assert "  repeated string tags = 3;" in request
    assert "  map<string, string> attrs = 4;" in request
    assert "  google.protobuf.Timestamp occurred_at = 5;" in request
    assert "  google.protobuf.Any payload = 6;" in request
    assert "  google.protobuf.Struct metadata = 7;" in request


def test_grpc_proto_writer_maps_generic_choice_to_oneof():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/choice").REQ(GenericChoicePayload).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    request = _block(files["api/demo.proto"], "message ChoiceRequest {")
    assert "  oneof result {" in request
    assert "    ChoiceSuccess success = 1;" in request
    assert "    ChoiceError error = 2;" in request


def test_grpc_proto_writer_preserves_explicit_alias_as_wire_name():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/alias").REQ(GenericAliasPayload).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
    )

    request = _block(files["api/demo.proto"], "message AliasRequest {")
    assert "  bool httpOnly = 1;" in request
    assert "  bool default_name = 2;" in request
    assert "httponly" not in request


def test_grpc_proto_writer_imports_layout_enum_from_another_file_without_proto_metadata():
    bp = Blueprint(root="/services/callback")
    with bp.group("/events/v1") as views:
        views.POST("/send").REQ(ExternalTaskStatusPayload).RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="contracts.grpc",
        go_package_prefix="contracts/grpc",
        proto_files=(
            _layout(
                file="shared/browseragent/task/v1/task.proto",
                package="browseragent.task.v1",
                go_package="appkit/browseragent/pb/task/v1;taskpb",
                schema_modules=("blueprints.shared.browseragent.task",),
                schema_names=("TaskStatus",),
            ),
            _layout(
                file="services/callback/events/v1/events.proto",
                package="callback.events.v1",
                go_package="callback/events/v1;eventspb",
                schema_modules=("blueprints.services.callback",),
                route_paths=("/services/callback/events/v1/**",),
                service="CallbackEvents",
            ),
        ),
    )

    events = files["services/callback/events/v1/events.proto"]
    assert 'import "shared/browseragent/task/v1/task.proto";' in events
    request = _block(events, "message SendRequest {")
    assert "  browseragent.task.v1.TaskStatus status = 1;" in request
    assert "enum TaskStatus {" not in events

    task = files["shared/browseragent/task/v1/task.proto"]
    assert "enum TaskStatus {" in task
    assert "  TASK_STATUS_UNSPECIFIED = 0;" in task


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


def test_grpc_proto_writer_applies_target_route_selection_rules():
    bp = Blueprint(root="/api")
    with bp.group("/public") as views:
        views.GET("/ping").RSP(message=String(description="message"))
    with bp.group("/private") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    files = render_proto_files(
        graph,
        package="example.api",
        go_package_prefix="example.com/project/grpc/go",
        exclude=("path:/api/private/**",),
    )

    assert list(files) == ["api/public.proto"]
    assert "PublicService" in files["api/public.proto"]


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
