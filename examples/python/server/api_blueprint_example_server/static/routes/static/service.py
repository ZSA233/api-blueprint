from __future__ import annotations

from .gen_service import *
from .gen_types import *


class StaticServiceImpl(StaticServiceStub):
    async def doc_json(self) -> DocJsonResponse:
        """doc_json
        GET /static/doc.json
        """
        return await super().doc_json()

    async def dochaha(self) -> DochahaResponse:
        """dochaha
        GET /static/dochaha
        """
        return await super().dochaha()
