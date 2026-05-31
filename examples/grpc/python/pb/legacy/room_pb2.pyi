from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RoomListRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RoomListResponse(_message.Message):
    __slots__ = ("rooms",)
    ROOMS_FIELD_NUMBER: _ClassVar[int]
    rooms: _containers.RepeatedCompositeFieldContainer[RoomSummary]
    def __init__(self, rooms: _Optional[_Iterable[_Union[RoomSummary, _Mapping]]] = ...) -> None: ...

class RoomSummary(_message.Message):
    __slots__ = ("room_id", "title")
    ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    room_id: str
    title: str
    def __init__(self, room_id: _Optional[str] = ..., title: _Optional[str] = ...) -> None: ...
