from __future__ import annotations

from typing import Any, Protocol


class StaticService(Protocol):
    async def doc_json(self) -> Any:
        ...

    async def dochaha(self) -> Any:
        ...


class StaticServiceStub:
    async def doc_json(self) -> Any:
        raise NotImplementedError("doc_json")

    async def dochaha(self) -> Any:
        raise NotImplementedError("dochaha")
