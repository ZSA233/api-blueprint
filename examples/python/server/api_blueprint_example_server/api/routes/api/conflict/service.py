from __future__ import annotations

from .gen_service import *
from .gen_types import *


class ConflictServiceImpl(ConflictServiceStub):
    async def default(
        self,
        query: DefaultQuery,
    ) -> DefaultResponse:
        """Naming conflict example
        GET /api/conflict/default
        """
        return await super().default(
            query=query,
        )
