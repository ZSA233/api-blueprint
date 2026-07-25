from __future__ import annotations

from .gen_service import *
from .gen_types import *


class RoomServiceImpl(RoomServiceStub):
    async def room_list(self) -> RoomListResponse:
        """Rootless room list example
        GET /room/list
        """
        return await super().room_list()
