from __future__ import annotations

from .gen_service import *
from .gen_types import *


class ApiServiceImpl(ApiServiceStub):
    async def hello_channel(self) -> Any:
        """hello_channel
        CHANNEL /api/ws
        """
        return await super().hello_channel(
            channel=channel,
        )
