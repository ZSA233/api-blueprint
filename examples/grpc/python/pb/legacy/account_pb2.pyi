from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class AccountProfileRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AccountProfileResponse(_message.Message):
    __slots__ = ("user_id", "nickname")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    nickname: str
    def __init__(self, user_id: _Optional[str] = ..., nickname: _Optional[str] = ...) -> None: ...
