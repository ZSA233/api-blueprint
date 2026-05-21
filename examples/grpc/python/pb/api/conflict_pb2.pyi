from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KeywordEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KEYWORDENUM_UNSPECIFIED: _ClassVar[KeywordEnum]
    KEYWORDENUM_DEFAULT: _ClassVar[KeywordEnum]
    KEYWORDENUM_CLASS: _ClassVar[KeywordEnum]
KEYWORDENUM_UNSPECIFIED: KeywordEnum
KEYWORDENUM_DEFAULT: KeywordEnum
KEYWORDENUM_CLASS: KeywordEnum

class DefaultRequest(_message.Message):
    __slots__ = ()
    CLASS_FIELD_NUMBER: _ClassVar[int]
    def __init__(self, **kwargs) -> None: ...

class DefaultResponse(_message.Message):
    __slots__ = ("default", "enum")
    DEFAULT_FIELD_NUMBER: _ClassVar[int]
    CLASS_FIELD_NUMBER: _ClassVar[int]
    ENUM_FIELD_NUMBER: _ClassVar[int]
    default: str
    enum: KeywordEnum
    def __init__(self, default: _Optional[str] = ..., enum: _Optional[_Union[KeywordEnum, str]] = ..., **kwargs) -> None: ...
