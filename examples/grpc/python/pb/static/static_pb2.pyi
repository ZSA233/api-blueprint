from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class DocJsonRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DocJsonResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DochahaRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DochahaResponse(_message.Message):
    __slots__ = ("a",)
    A_FIELD_NUMBER: _ClassVar[int]
    a: str
    def __init__(self, a: _Optional[str] = ...) -> None: ...
