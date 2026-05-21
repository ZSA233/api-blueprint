from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HelloChannelMsgTypeEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HELLOCHANNELMSGTYPEENUM_UNSPECIFIED: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_PING: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_PONG: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_JOIN: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_LEAVE: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_FORGEROUND: _ClassVar[HelloChannelMsgTypeEnum]
    HELLOCHANNELMSGTYPEENUM_UPGRADE: _ClassVar[HelloChannelMsgTypeEnum]

class MapEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MAPENUM_UNSPECIFIED: _ClassVar[MapEnum]
    MAPENUM_A: _ClassVar[MapEnum]
    MAPENUM_B: _ClassVar[MapEnum]

class HelloWayEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HELLOWAYENUM_UNSPECIFIED: _ClassVar[HelloWayEnum]
    HELLOWAYENUM_ASD: _ClassVar[HelloWayEnum]
HELLOCHANNELMSGTYPEENUM_UNSPECIFIED: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_PING: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_PONG: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_JOIN: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_LEAVE: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_FORGEROUND: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_UPGRADE: HelloChannelMsgTypeEnum
MAPENUM_UNSPECIFIED: MapEnum
MAPENUM_A: MapEnum
MAPENUM_B: MapEnum
HELLOWAYENUM_UNSPECIFIED: HelloWayEnum
HELLOWAYENUM_ASD: HelloWayEnum

class AbcRequest(_message.Message):
    __slots__ = ("arg1", "arg3", "arg2", "type")
    ARG1_FIELD_NUMBER: _ClassVar[int]
    ARG3_FIELD_NUMBER: _ClassVar[int]
    ARG2_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    arg1: bool
    arg3: str
    arg2: float
    type: HelloChannelMsgTypeEnum
    def __init__(self, arg1: bool = ..., arg3: _Optional[str] = ..., arg2: _Optional[float] = ..., type: _Optional[_Union[HelloChannelMsgTypeEnum, str]] = ...) -> None: ...

class AbcResponse(_message.Message):
    __slots__ = ("value",)
    class ValueEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ApiHelloMap
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ApiHelloMap, _Mapping]] = ...) -> None: ...
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.MessageMap[str, ApiHelloMap]
    def __init__(self, value: _Optional[_Mapping[str, ApiHelloMap]] = ...) -> None: ...

class ApiHelloMap(_message.Message):
    __slots__ = ("haha",)
    HAHA_FIELD_NUMBER: _ClassVar[int]
    haha: int
    def __init__(self, haha: _Optional[int] = ...) -> None: ...

class MapEnumRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MapEnumResponse(_message.Message):
    __slots__ = ("value",)
    class ValueEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ApiHelloMap
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ApiHelloMap, _Mapping]] = ...) -> None: ...
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.MessageMap[str, ApiHelloMap]
    def __init__(self, value: _Optional[_Mapping[str, ApiHelloMap]] = ...) -> None: ...

class ListEnumRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListEnumResponse(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.RepeatedScalarFieldContainer[MapEnum]
    def __init__(self, value: _Optional[_Iterable[_Union[MapEnum, str]]] = ...) -> None: ...

class StringRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StringResponse(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: str
    def __init__(self, value: _Optional[str] = ...) -> None: ...

class Uint64Request(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Uint64Response(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class StringEmunRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StringEmunResponse(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: MapEnum
    def __init__(self, value: _Optional[_Union[MapEnum, str]] = ...) -> None: ...

class HelloWayRequest(_message.Message):
    __slots__ = ("arg1",)
    ARG1_FIELD_NUMBER: _ClassVar[int]
    arg1: HelloWayEnum
    def __init__(self, arg1: _Optional[_Union[HelloWayEnum, str]] = ...) -> None: ...

class HelloWayResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
