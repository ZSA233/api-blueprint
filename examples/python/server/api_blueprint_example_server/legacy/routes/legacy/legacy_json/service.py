from __future__ import annotations

from .gen_service import *
from .gen_types import *


class LegacyJsonServiceImpl(LegacyJsonServiceStub):
    async def legacy_json_compat(self) -> LegacyJsonCompatResponse:
        """Legacy JSON compatibility example
        GET /legacy-json/compat
        """
        return await super().legacy_json_compat()
