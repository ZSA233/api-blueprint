from __future__ import annotations

from .gen_service import *
from .gen_types import *


class ConflictServiceImpl(ConflictServiceStub):
    async def default(
        self,
        query: DefaultQuery,
    ) -> DefaultResponse:
        """Alt naming conflict example
        GET /alt/conflict/default
        """
        return await super().default(
            query=query,
        )
