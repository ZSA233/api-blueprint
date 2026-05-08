from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket
from starlette.responses import StreamingResponse

from ...routes.api.service import ApiService, ApiServiceStub
from ...routes.api.demo.service import DemoService, DemoServiceStub
from ...routes.api.hello.service import HelloService, HelloServiceStub


def create_router(
    api_service: ApiService | None = None,
    demo_service: DemoService | None = None,
    hello_service: HelloService | None = None,
) -> APIRouter:
    router = APIRouter()
    api_service_impl = api_service or ApiServiceStub()
    demo_service_impl = demo_service or DemoServiceStub()
    hello_service_impl = hello_service or HelloServiceStub()

    @router.websocket("/api/ws")
    async def api_connect_ws_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        service = api_service_impl
        await service.ws()
        await websocket.close()

    @router.api_route("/api/demo/abc", methods=["GET"])
    async def demo_abc(
        query: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        return await service.abc(
            query=query,
        )

    @router.api_route("/api/demo/test_post", methods=["POST"])
    async def demo_test_post(
        json: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        return await service.test_post(
            json=json,
        )

    @router.api_route("/api/demo/1put", methods=["PUT"])
    async def demo_z1put(
        query: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        return await service.z1put(
            query=query,
            json=json,
        )

    @router.api_route("/api/demo/delete$", methods=["DELETE"])
    async def demo_delete(
        query: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        return await service.delete(
            query=query,
        )

    @router.websocket("/api/demo/ws")
    async def demo_connect_ws_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        service = demo_service_impl
        await service.ws()
        await websocket.close()

    @router.api_route("/api/demo/sweep-events", methods=["GET"])
    async def demo_subscribe_sweep_events(
        open_data: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        result = await service.sweep_events(
            open_data=open_data,
        )
        if hasattr(result, "__aiter__"):
            return StreamingResponse(result)
        return result

    @router.websocket("/api/demo/assistant-session")
    async def demo_open_assistant_session_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        service = demo_service_impl
        await service.assistant_session()
        await websocket.close()

    @router.api_route("/api/demo/post_deprecated", methods=["POST"])
    async def demo_post_deprecated(
        json: dict[str, Any] | None = None,
    ) -> Any:
        service = demo_service_impl
        return await service.post_deprecated(
            json=json,
        )

    @router.api_route("/api/demo/raw", methods=["POST"])
    async def demo_raw() -> Any:
        service = demo_service_impl
        return await service.raw()

    @router.api_route("/api/demo/map_model", methods=["POST"])
    async def demo_map_model() -> Any:
        service = demo_service_impl
        return await service.map_model()

    @router.api_route("/api/hello/abc", methods=["GET"])
    async def hello_abc(
        query: dict[str, Any] | None = None,
    ) -> Any:
        service = hello_service_impl
        return await service.abc(
            query=query,
        )

    @router.api_route("/api/hello/map-enum", methods=["GET"])
    async def hello_map_enum() -> Any:
        service = hello_service_impl
        return await service.map_enum()

    @router.api_route("/api/hello/list-enum", methods=["GET"])
    async def hello_list_enum() -> Any:
        service = hello_service_impl
        return await service.list_enum()

    @router.api_route("/api/hello/string", methods=["GET"])
    async def hello_string() -> Any:
        service = hello_service_impl
        return await service.string()

    @router.api_route("/api/hello/uint64", methods=["GET"])
    async def hello_uint64() -> Any:
        service = hello_service_impl
        return await service.uint64()

    @router.api_route("/api/hello/string-emun", methods=["GET"])
    async def hello_string_emun() -> Any:
        service = hello_service_impl
        return await service.string_emun()

    @router.api_route("/api/hello/hello-way", methods=["GET"])
    async def hello_hello_way(
        query: dict[str, Any] | None = None,
    ) -> Any:
        service = hello_service_impl
        return await service.hello_way(
            query=query,
        )

    return router
