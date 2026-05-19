from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
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
HELLOCHANNELMSGTYPEENUM_UNSPECIFIED: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_PING: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_PONG: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_JOIN: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_LEAVE: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_FORGEROUND: HelloChannelMsgTypeEnum
HELLOCHANNELMSGTYPEENUM_UPGRADE: HelloChannelMsgTypeEnum

class HelloChannelMessage(_message.Message):
    __slots__ = ("type", "data")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    type: HelloChannelMsgTypeEnum
    data: str
    def __init__(self, type: _Optional[_Union[HelloChannelMsgTypeEnum, str]] = ..., data: _Optional[str] = ...) -> None: ...
