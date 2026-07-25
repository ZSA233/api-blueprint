from __future__ import annotations

from .gen_service import *
from .gen_types import *


class AccountServiceImpl(AccountServiceStub):
    async def account_profile(self) -> AccountProfileResponse:
        """Rootless account profile example
        GET /account/profile
        """
        return await super().account_profile()
