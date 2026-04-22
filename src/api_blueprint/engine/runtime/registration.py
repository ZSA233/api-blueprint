from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from api_blueprint.engine.runtime.endpoint import make_endpoint
from api_blueprint.engine.runtime.responses import XMLResponse
from api_blueprint.engine.schema import model_to_pydantic

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.router import Router


async def proxy_upstream_request(router: "Router", request: Request, **kwargs: Any):
    upstream_url = router.bp.upstream
    if upstream_url is None:
        raise Exception("[upstream_handler] 没有设置 upstream，无法转发给上游服务")

    upstream_path = request.url.path
    upstream_full_url = upstream_url.rstrip("/") + upstream_path
    params = dict(request.query_params)
    content_type = request.headers.get("content-type", "")
    body_bytes = await request.body()
    headers = dict(request.headers)
    cookies = request.cookies

    for header_name in ["host", "content-length", "transfer-encoding", "content-encoding", "connection"]:
        headers.pop(header_name, None)

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            request_kwargs = {
                "method": request.method,
                "url": upstream_full_url,
                "headers": headers,
                "params": params,
                "cookies": cookies,
            }

            if content_type.startswith("application/json"):
                try:
                    request_kwargs["json"] = await request.json()
                except Exception:
                    request_kwargs["json"] = None
            else:
                request_kwargs["content"] = body_bytes

            upstream_response = await client.request(**request_kwargs)
    except httpx.RequestError as exc:
        return Response(
            content=f"Bad Gateway: 无法请求上游 ({exc})",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    excluded_headers = {
        "transfer-encoding",
        "content-encoding",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "upgrade",
    }

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )


def register_router(router: "Router", app: FastAPI) -> None:
    copy_extra = router.extra.copy()

    async def handler(request: Request, **kwargs: Any):
        return await proxy_upstream_request(router, request, **kwargs)

    endpoint = make_endpoint(
        handler,
        model_to_pydantic(router.req_query, router=router) if router.req_query else None,
        model_to_pydantic(router.req_form, router=router) if router.req_form else None,
        model_to_pydantic(router.req_json, router=router) if router.req_json else None,
        router.headers,
    )

    rsp_model = None
    rsp_class: type[Response] = JSONResponse
    response_wrapper = router.response_wrapper
    if router.rsp_media_type == "application/xml":
        rsp_class = XMLResponse

    if router.rsp_model is not None:
        rsp_model = model_to_pydantic(response_wrapper.create(router.rsp_model), router=router)

    responses = {}
    for code, errs in (router.bp.errors | router.errors).items():
        examples = {}
        for err in errs:
            extra = err.__extra__
            key, value = response_wrapper.on_error(err)
            examples[key] = {
                "summary": extra.get("description", key),
                "value": value,
            }
        description = str(code) if not errs else "/".join(err.message for err in errs)
        responses[code] = {
            "description": description,
            "content": {
                router.rsp_media_type: {
                    "examples": examples,
                }
            },
        }

    ws_methods = [method for method in router.methods if method == "WS"]
    if ws_methods:
        app.add_api_websocket_route(router.url, endpoint)

    api_methods = [method for method in router.methods if method != "WS"]
    if api_methods:
        app.add_api_route(
            router.url,
            endpoint,
            methods=api_methods,
            tags=router.tags,
            response_model=rsp_model,
            response_class=rsp_class,
            deprecated=router.is_deprecated,
            responses=responses,
            **copy_extra,
        )
