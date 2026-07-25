from __future__ import annotations

from .gen_service import *
from .gen_types import *


class HelloServiceImpl(HelloServiceStub):
    async def abc(
        self,
        query: AbcQuery,
    ) -> dict[str, ApiHelloMap]:
        """这是abc的summary
        GET /api/hello/abc
        """
        return await super().abc(
            query=query,
        )

    async def map_enum(self) -> dict[MapEnum, ApiHelloMap]:
        """map-enum
        GET /api/hello/map-enum
        """
        return await super().map_enum()

    async def list_enum(self) -> list[MapEnum]:
        """list-enum
        GET /api/hello/list-enum
        """
        return await super().list_enum()

    async def string(self) -> str:
        """string
        GET /api/hello/string
        """
        return await super().string()

    async def uint64(self) -> int:
        """uint64
        GET /api/hello/uint64
        """
        return await super().uint64()

    async def string_emun(self) -> MapEnum:
        """string-enum
        GET /api/hello/string-emun
        """
        return await super().string_emun()

    async def hello_way(
        self,
        query: HelloWayQuery,
    ) -> Any:
        """hello-way
        GET /api/hello/hello-way
        """
        return await super().hello_way(
            query=query,
        )
