from __future__ import annotations

from typing import Any, Protocol


class ApiService(Protocol):
    async def ws(self) -> Any:
        ...


class ApiServiceStub:
    async def ws(self) -> Any:
        raise NotImplementedError("ws")
