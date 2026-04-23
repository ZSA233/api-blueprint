from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class HelloRequest(_message.Message):
    __slots__ = ("name", "locale")
    NAME_FIELD_NUMBER: _ClassVar[int]
    LOCALE_FIELD_NUMBER: _ClassVar[int]
    name: str
    locale: str
    def __init__(self, name: _Optional[str] = ..., locale: _Optional[str] = ...) -> None: ...

class HelloReply(_message.Message):
    __slots__ = ("message", "request_id")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    message: str
    request_id: str
    def __init__(self, message: _Optional[str] = ..., request_id: _Optional[str] = ...) -> None: ...
