from __future__ import annotations

from .gen_service import *
from .gen_types import *


class StatusServiceImpl(StatusServiceStub):
    async def runtime_current_status(self) -> RuntimeCurrentStatusResponse:
        """Runtime root naming example
        GET /runtime/status/current
        """
        return await super().runtime_current_status()
