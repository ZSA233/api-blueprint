from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ColorEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    COLORENUM_UNSPECIFIED: _ClassVar[ColorEnum]
    COLORENUM_RED: _ClassVar[ColorEnum]
    COLORENUM_GREEN: _ClassVar[ColorEnum]
    COLORENUM_BLUE: _ClassVar[ColorEnum]

class StatusEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUSENUM_UNSPECIFIED: _ClassVar[StatusEnum]
    STATUSENUM_PENDING: _ClassVar[StatusEnum]
    STATUSENUM_RUNNING: _ClassVar[StatusEnum]
    STATUSENUM_FINISHED: _ClassVar[StatusEnum]
COLORENUM_UNSPECIFIED: ColorEnum
COLORENUM_RED: ColorEnum
COLORENUM_GREEN: ColorEnum
COLORENUM_BLUE: ColorEnum
STATUSENUM_UNSPECIFIED: StatusEnum
STATUSENUM_PENDING: StatusEnum
STATUSENUM_RUNNING: StatusEnum
STATUSENUM_FINISHED: StatusEnum

class AbcRequest(_message.Message):
    __slots__ = ("arg1", "arg3", "arg2")
    ARG1_FIELD_NUMBER: _ClassVar[int]
    ARG3_FIELD_NUMBER: _ClassVar[int]
    ARG2_FIELD_NUMBER: _ClassVar[int]
    arg1: bool
    arg3: str
    arg2: float
    def __init__(self, arg1: bool = ..., arg3: _Optional[str] = ..., arg2: _Optional[float] = ...) -> None: ...

class AbcResponse(_message.Message):
    __slots__ = ("bc", "a", "efg", "hijk", "lmnop", "enum_color", "enum_status", "enum_list")
    BC_FIELD_NUMBER: _ClassVar[int]
    A_FIELD_NUMBER: _ClassVar[int]
    EFG_FIELD_NUMBER: _ClassVar[int]
    HIJK_FIELD_NUMBER: _ClassVar[int]
    LMNOP_FIELD_NUMBER: _ClassVar[int]
    ENUM_COLOR_FIELD_NUMBER: _ClassVar[int]
    ENUM_STATUS_FIELD_NUMBER: _ClassVar[int]
    ENUM_LIST_FIELD_NUMBER: _ClassVar[int]
    bc: str
    a: int
    efg: float
    hijk: _containers.RepeatedScalarFieldContainer[int]
    lmnop: _containers.RepeatedCompositeFieldContainer[ApiDemoSubA]
    enum_color: ColorEnum
    enum_status: StatusEnum
    enum_list: _containers.RepeatedScalarFieldContainer[StatusEnum]
    def __init__(self, bc: _Optional[str] = ..., a: _Optional[int] = ..., efg: _Optional[float] = ..., hijk: _Optional[_Iterable[int]] = ..., lmnop: _Optional[_Iterable[_Union[ApiDemoSubA, _Mapping]]] = ..., enum_color: _Optional[_Union[ColorEnum, str]] = ..., enum_status: _Optional[_Union[StatusEnum, str]] = ..., enum_list: _Optional[_Iterable[_Union[StatusEnum, str]]] = ...) -> None: ...

class ApiDemoSubA(_message.Message):
    __slots__ = ("hello", "amap")
    class HelloEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    HELLO_FIELD_NUMBER: _ClassVar[int]
    AMAP_FIELD_NUMBER: _ClassVar[int]
    hello: _containers.ScalarMap[str, int]
    amap: _containers.RepeatedCompositeFieldContainer[ApiDemoMap]
    def __init__(self, hello: _Optional[_Mapping[str, int]] = ..., amap: _Optional[_Iterable[_Union[ApiDemoMap, _Mapping]]] = ...) -> None: ...

class ApiDemoMap(_message.Message):
    __slots__ = ("haha",)
    HAHA_FIELD_NUMBER: _ClassVar[int]
    haha: int
    def __init__(self, haha: _Optional[int] = ...) -> None: ...

class TestPostRequest(_message.Message):
    __slots__ = ("req1", "req2")
    REQ1_FIELD_NUMBER: _ClassVar[int]
    REQ2_FIELD_NUMBER: _ClassVar[int]
    req1: str
    req2: int
    def __init__(self, req1: _Optional[str] = ..., req2: _Optional[int] = ...) -> None: ...

class TestPostResponse(_message.Message):
    __slots__ = ("list", "map")
    class MapEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ApiDemoMap
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ApiDemoMap, _Mapping]] = ...) -> None: ...
    LIST_FIELD_NUMBER: _ClassVar[int]
    MAP_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedScalarFieldContainer[str]
    map: _containers.MessageMap[str, ApiDemoMap]
    def __init__(self, list: _Optional[_Iterable[str]] = ..., map: _Optional[_Mapping[str, ApiDemoMap]] = ...) -> None: ...

class PutDemoRequest(_message.Message):
    __slots__ = ("query", "json")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    JSON_FIELD_NUMBER: _ClassVar[int]
    query: REQFunc1putQUERY
    json: REQFunc1putJSON
    def __init__(self, query: _Optional[_Union[REQFunc1putQUERY, _Mapping]] = ..., json: _Optional[_Union[REQFunc1putJSON, _Mapping]] = ...) -> None: ...

class REQFunc1putQUERY(_message.Message):
    __slots__ = ("arg1", "arg2", "arg3")
    ARG1_FIELD_NUMBER: _ClassVar[int]
    ARG2_FIELD_NUMBER: _ClassVar[int]
    ARG3_FIELD_NUMBER: _ClassVar[int]
    arg1: str
    arg2: float
    arg3: str
    def __init__(self, arg1: _Optional[str] = ..., arg2: _Optional[float] = ..., arg3: _Optional[str] = ...) -> None: ...

class REQFunc1putJSON(_message.Message):
    __slots__ = ("req1", "req2")
    REQ1_FIELD_NUMBER: _ClassVar[int]
    REQ2_FIELD_NUMBER: _ClassVar[int]
    req1: str
    req2: int
    def __init__(self, req1: _Optional[str] = ..., req2: _Optional[int] = ...) -> None: ...

class PutDemoResponse(_message.Message):
    __slots__ = ("list", "anon_kv")
    LIST_FIELD_NUMBER: _ClassVar[int]
    ANON_KV_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedScalarFieldContainer[str]
    anon_kv: ANONFunc1putAnonKv
    def __init__(self, list: _Optional[_Iterable[str]] = ..., anon_kv: _Optional[_Union[ANONFunc1putAnonKv, _Mapping]] = ...) -> None: ...

class ANONFunc1putAnonKv(_message.Message):
    __slots__ = ("kv1", "kv2")
    KV1_FIELD_NUMBER: _ClassVar[int]
    KV2_FIELD_NUMBER: _ClassVar[int]
    kv1: int
    kv2: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, kv1: _Optional[int] = ..., kv2: _Optional[_Iterable[float]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("arg1", "arg2")
    ARG1_FIELD_NUMBER: _ClassVar[int]
    ARG2_FIELD_NUMBER: _ClassVar[int]
    arg1: str
    arg2: float
    def __init__(self, arg1: _Optional[str] = ..., arg2: _Optional[float] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("list", "anon_list")
    LIST_FIELD_NUMBER: _ClassVar[int]
    ANON_LIST_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedScalarFieldContainer[str]
    anon_list: _containers.RepeatedCompositeFieldContainer[ANONDeleteAnonList]
    def __init__(self, list: _Optional[_Iterable[str]] = ..., anon_list: _Optional[_Iterable[_Union[ANONDeleteAnonList, _Mapping]]] = ...) -> None: ...

class ANONDeleteAnonList(_message.Message):
    __slots__ = ("kv1", "kv2")
    KV1_FIELD_NUMBER: _ClassVar[int]
    KV2_FIELD_NUMBER: _ClassVar[int]
    kv1: int
    kv2: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, kv1: _Optional[int] = ..., kv2: _Optional[_Iterable[str]] = ...) -> None: ...

class SweepEventsRequest(_message.Message):
    __slots__ = ("run_id", "replay_from")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    REPLAY_FROM_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    replay_from: str
    def __init__(self, run_id: _Optional[str] = ..., replay_from: _Optional[str] = ...) -> None: ...

class SweepStreamMessage(_message.Message):
    __slots__ = ("state", "progress", "log")
    STATE_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    state: SweepState
    progress: SweepProgress
    log: SweepLog
    def __init__(self, state: _Optional[_Union[SweepState, _Mapping]] = ..., progress: _Optional[_Union[SweepProgress, _Mapping]] = ..., log: _Optional[_Union[SweepLog, _Mapping]] = ...) -> None: ...

class SweepState(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class SweepProgress(_message.Message):
    __slots__ = ("current", "total")
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    current: int
    total: int
    def __init__(self, current: _Optional[int] = ..., total: _Optional[int] = ...) -> None: ...

class SweepLog(_message.Message):
    __slots__ = ("level", "message")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    level: str
    message: str
    def __init__(self, level: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class AssistantClientMessage(_message.Message):
    __slots__ = ("input", "cancel")
    INPUT_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    input: AssistantInput
    cancel: AssistantCancel
    def __init__(self, input: _Optional[_Union[AssistantInput, _Mapping]] = ..., cancel: _Optional[_Union[AssistantCancel, _Mapping]] = ...) -> None: ...

class AssistantInput(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class AssistantCancel(_message.Message):
    __slots__ = ("reason",)
    REASON_FIELD_NUMBER: _ClassVar[int]
    reason: str
    def __init__(self, reason: _Optional[str] = ...) -> None: ...

class AssistantServerMessage(_message.Message):
    __slots__ = ("delta", "done", "log")
    DELTA_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    delta: AssistantDelta
    done: AssistantDone
    log: SweepLog
    def __init__(self, delta: _Optional[_Union[AssistantDelta, _Mapping]] = ..., done: _Optional[_Union[AssistantDone, _Mapping]] = ..., log: _Optional[_Union[SweepLog, _Mapping]] = ...) -> None: ...

class AssistantDelta(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class AssistantDone(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    def __init__(self, message_id: _Optional[str] = ...) -> None: ...

class PostDeprecatedRequest(_message.Message):
    __slots__ = ("req1", "req2")
    REQ1_FIELD_NUMBER: _ClassVar[int]
    REQ2_FIELD_NUMBER: _ClassVar[int]
    req1: str
    req2: int
    def __init__(self, req1: _Optional[str] = ..., req2: _Optional[int] = ...) -> None: ...

class PostDeprecatedResponse(_message.Message):
    __slots__ = ("list",)
    LIST_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, list: _Optional[_Iterable[str]] = ...) -> None: ...

class RawRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RawResponse(_message.Message):
    __slots__ = ("list", "list2")
    class List2Entry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: RawResponseList2Value
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[RawResponseList2Value, _Mapping]] = ...) -> None: ...
    LIST_FIELD_NUMBER: _ClassVar[int]
    LIST2_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedScalarFieldContainer[str]
    list2: _containers.MessageMap[str, RawResponseList2Value]
    def __init__(self, list: _Optional[_Iterable[str]] = ..., list2: _Optional[_Mapping[str, RawResponseList2Value]] = ...) -> None: ...

class RawResponseList2Value(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.RepeatedCompositeFieldContainer[ApiDemoA]
    def __init__(self, value: _Optional[_Iterable[_Union[ApiDemoA, _Mapping]]] = ...) -> None: ...

class ApiDemoA(_message.Message):
    __slots__ = ("bc", "a", "efg", "hijk", "lmnop", "enum_color", "enum_status", "enum_list")
    BC_FIELD_NUMBER: _ClassVar[int]
    A_FIELD_NUMBER: _ClassVar[int]
    EFG_FIELD_NUMBER: _ClassVar[int]
    HIJK_FIELD_NUMBER: _ClassVar[int]
    LMNOP_FIELD_NUMBER: _ClassVar[int]
    ENUM_COLOR_FIELD_NUMBER: _ClassVar[int]
    ENUM_STATUS_FIELD_NUMBER: _ClassVar[int]
    ENUM_LIST_FIELD_NUMBER: _ClassVar[int]
    bc: str
    a: int
    efg: float
    hijk: _containers.RepeatedScalarFieldContainer[int]
    lmnop: _containers.RepeatedCompositeFieldContainer[ApiDemoSubA]
    enum_color: ColorEnum
    enum_status: StatusEnum
    enum_list: _containers.RepeatedScalarFieldContainer[StatusEnum]
    def __init__(self, bc: _Optional[str] = ..., a: _Optional[int] = ..., efg: _Optional[float] = ..., hijk: _Optional[_Iterable[int]] = ..., lmnop: _Optional[_Iterable[_Union[ApiDemoSubA, _Mapping]]] = ..., enum_color: _Optional[_Union[ColorEnum, str]] = ..., enum_status: _Optional[_Union[StatusEnum, str]] = ..., enum_list: _Optional[_Iterable[_Union[StatusEnum, str]]] = ...) -> None: ...

class MapModelRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MapModelResponse(_message.Message):
    __slots__ = ("value",)
    class ValueEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ApiDemoMap
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ApiDemoMap, _Mapping]] = ...) -> None: ...
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.MessageMap[str, ApiDemoMap]
    def __init__(self, value: _Optional[_Mapping[str, ApiDemoMap]] = ...) -> None: ...

class ErrorDemoRequest(_message.Message):
    __slots__ = ("mode",)
    MODE_FIELD_NUMBER: _ClassVar[int]
    mode: str
    def __init__(self, mode: _Optional[str] = ...) -> None: ...

class ErrorDemoResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...
