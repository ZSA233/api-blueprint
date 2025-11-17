from fastapi import FastAPI, APIRouter, Response, Request, status
from api_blueprint.engine.response import XMLResponse
from api_blueprint.engine.model import (
    Field, Model, Error, Map, Array, HeaderModel, model_to_pydantic, 
    unwrap_errors, create_field_wrapped_model,
    create_model, iter_field_model_type, iter_model_vars,
)
from collections import defaultdict
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.engine.endpoint import make_endpoint
from api_blueprint.engine.provider import (
    Provider, ellipsis_replaces, ProviderName, 
    Handle, WsHandle,
)
from fastapi.responses import JSONResponse, Response
from fastapi import params as fa_params
from fastapi.security import api_key as fa_apikey
import fastapi
from typing import (
    List, Dict, Optional, Any, overload,
    TypeVar, Literal, Union, Sequence, Type, DefaultDict,
    TYPE_CHECKING, Self,
)
from pathlib import Path
import httpx


if TYPE_CHECKING:
    from api_blueprint.engine.group import RouterGroup


METHOD_ENUM = Literal['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'WS']


ModelOrField = Union[Model, Field]



class ConflictFieldError(Exception):
    pass


class Router:
    group: 'RouterGroup'
    
    leaf: str
    methods: List[METHOD_ENUM]
    medio_type: str

    req_query: Optional[Model]
    req_form: Optional[Model]
    req_bin: Optional[Model]
    req_json: Optional[Model]

    rsp_model: Optional[Model]
    rsp_wrapper: Optional[ResponseWrapper]
    
    recvs: List[Model]
    sends: List[Model]

    errors: DefaultDict[int, List[Error]]
    extra: Dict[str, Any]

    _handle: Provider = Handle
    _providers: Optional[List[Provider]]
    _tags: Optional[List[str]] = None
    is_deprecated: bool = False

    def __init__(
        self, 
        group: 'RouterGroup', 
        methods: List[METHOD_ENUM], 
        api: str, 
        response_wrapper: Optional[ResponseWrapper] = None,
        headers: Optional[Union[HeaderModel, Type[HeaderModel]]] = None,
        providers: Optional[List[Provider]] = None,
        tags: Optional[List[str]] = None,
        *,
        handle: Provider = Handle,
        **kwargs: Dict[str, Any],
    ):
        self.group = group
        self.leaf = api
        self.methods = methods
        self.extra = kwargs

        self.req_query = None
        self.req_form = None
        self.req_json = None
        self.req_bin = None
        self.rsp_model = None

        self.rsp_wrapper = response_wrapper
        self._headers = headers
        
        self._handle = handle
        self._providers = providers
        self._tags = tags

        self.is_deprecated = False
        self.rsp_media_type = 'application/json'

        self.errors = defaultdict(list)

        self.recvs = []
        self.sends = []

    def __str__(self):
        return f'<Router {self.methods} - {self.url} >'

    @property
    def url(self) -> str:
        return str(Path(self.group.prefix) / self.leaf.lstrip("/"))

    @property
    def root(self):
        return self.group.root

    @property
    def bp(self):
        return self.group.bp

    @property
    def name(self):
        return snake_to_pascal_case(self.leaf)

    @property
    def providers(self) -> List[Provider]:
        provs = self._providers
        if provs is not None:
            provs = ellipsis_replaces(self.bp.providers, self._providers)
        else:
            provs = self.bp.providers
        
        remap_provs = []
        for prov in provs:
            if prov.name == ProviderName.HANDLE.value:
                prov = self._handle
            remap_provs.append(prov)
        return remap_provs

    @property
    def headers(self) -> Optional[HeaderModel]:
        return self._headers or self.bp.headers

    @property
    def response_wrapper(self) -> Type[ResponseWrapper]:
        rsp_wrapper = self.rsp_wrapper
        if rsp_wrapper is None:
            rsp_wrapper = self.bp.response_wrapper
        return rsp_wrapper

    @property
    def tags(self) -> List[str]:
        tags = set()
        if self._tags is not None:
            tags.update(self._tags)
        if self.bp.tags:
            tags.update(self.bp.tags)
        return list(tags)


    def ARGS(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(
                f'REQ_{self.name}_QUERY',
                kwargs,
            )
        
        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(
                f'REQ_{self.name}_QUERY',
                __model,
            )
        self.req_query = __model
        return self


    def REQ_JSON(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(
                f'REQ_{self.name}_JSON',
                kwargs,
            )
        
        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(
                f'REQ_{self.name}_JSON',
                __model,
            )
        self.req_json = __model
        return self

    def REQ(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        return self.REQ_JSON(__model, **kwargs)

    def REQ_FORM(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        if __model is None:
            __model = create_model(
                f'REQ_{self.name}_FORM',
                kwargs,
            )
        
        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(
                f'REQ_{self.name}_FORM',
                __model,
            )
        self.req_form = __model
        return self
    
    def REQ_BIN(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        """ 目前仅用于描述，需要手动实现解析逻辑 """
        if __model is None:
            __model = create_model(
                f'REQ_{self.name}_BIN',
                kwargs,
            )
        
        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(
                f'REQ_{self.name}_BIN',
                __model,
            )
        self.req_bin = __model
        return self

    def _RSP_AS_MODEL(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Optional[Model]:
        if __model is None:
            __model = create_model(
                f'RSP_{self.name}',
                kwargs,
            )
        
        if isinstance(__model, Model):
            __model = __model.__class__
        elif isinstance(__model, Field):
            __model = create_field_wrapped_model(
                f'RSP_{self.name}',
                __model,
            )
        return __model

    def RSP_JSON(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self.rsp_media_type = 'application/json'
        return self

    def RSP(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        return self.RSP_JSON(__model, **kwargs)

    def RSP_XML(self, __model: Optional[Model] = None, **kwargs: Dict[str, ModelOrField]) -> Self:
        self.rsp_model = self._RSP_AS_MODEL(__model, **kwargs)
        self.rsp_media_type = 'application/xml'
        return self

    def ERR(self, *errors: Union[Error, Model]) -> Self:
        self.errors = unwrap_errors(errors)
        return self
    
    def DEPRECATED(self) -> Self:
        self.is_deprecated = True
        return self

    async def upstream_handler(self, request: Request, **kwargs):
        UPSTREAM_URL = self.bp.upstream
        if UPSTREAM_URL is None:
            raise Exception(f'[upstream_handler] 没有设置 upstream，无法转发给上游服务')
        upstream_path = request.url.path
        upstream_full_url = UPSTREAM_URL.rstrip("/") + upstream_path
        params = dict(request.query_params)
        content_type = request.headers.get("content-type", "")
        body_bytes = await request.body()
        headers = dict(request.headers)
        cookies = request.cookies

        for h in [
            "host", "content-length", 
            "transfer-encoding", "content-encoding", 
            "connection"]:
            headers.pop(h, None)

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
                if content_type.startswith("application/json"):
                    try:
                        json_data = await request.json()
                    except Exception:
                        json_data = None

                    upstream_response = await client.request(
                        method=request.method,
                        url=upstream_full_url,
                        headers=headers,
                        params=params,
                        cookies=cookies,
                        json=json_data,
                    )

                elif content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
                    upstream_response = await client.request(
                        method=request.method,
                        url=upstream_full_url,
                        headers=headers,
                        params=params,
                        cookies=cookies,
                        content=body_bytes,
                    )

                else:
                    upstream_response = await client.request(
                        method=request.method,
                        url=upstream_full_url,
                        headers=headers,
                        params=params,
                        cookies=cookies,
                        content=body_bytes,
                    )

        except httpx.RequestError as e:
            return Response(
                content=f"Bad Gateway: 无法请求上游 ({e})",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        
        # 有些头也不宜直接透传，比如 transfer-encoding、content-encoding 等
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
            media_type=upstream_response.headers.get("content-type")
        )


    def do_register(self, app: FastAPI):
        copy_extra = self.extra.copy()
        
        endpoint = make_endpoint(
            self.upstream_handler, 
            model_to_pydantic(self.req_query, router=self) if self.req_query else None,
            model_to_pydantic(self.req_form, router=self) if self.req_form else None,
            model_to_pydantic(self.req_json, router=self) if self.req_json else None,
            self.headers,
        )
        rsp_model: Optional[Type] = None
        rsp_class: Response = JSONResponse
        response_wrapper = self.response_wrapper
        if self.rsp_media_type == 'application/xml':
            rsp_class = XMLResponse
        
        if self.rsp_model is not None:
            rsp_model = model_to_pydantic(response_wrapper.create(self.rsp_model), router=self)

        responses: Dict[int, Dict[str, Any]] = {}
        for code, errs in (self.bp.errors | self.errors).items():
            examples: Dict[str, Any] = {}
            for err in errs:
                extra = err.__extra__
                key, value = response_wrapper.on_error(err)                           
                examples[key] = {
                    'summary': extra.get('description', key),
                    'value': value,
                }
            description = str(code)
            if len(errs):
                description = '/'.join([err.message for err in errs])
            responses[code] = {
                'description': description,
                'content': {
                    self.rsp_media_type: {
                        'examples': examples
                    }
                }
            }

        WS_METHODS = ('WS',)

        if ws_methods := [m for m in self.methods if m in WS_METHODS]:
            app.add_api_websocket_route(
                self.url,
                endpoint,
            )
        
        if api_methods := [m for m in self.methods if m not in WS_METHODS]:
            app.add_api_route(
                self.url,
                endpoint,
                methods=api_methods,
                tags=self.tags,
                response_model=rsp_model,
                response_class=rsp_class,
                deprecated=self.is_deprecated,
                responses=responses,
                **copy_extra
            )


    def RECV(self, *models: List[Model]) -> Self:
        self.recvs.extend(models)
        return self

    def SEND(self, *models: List[Model]) -> Self:
        self.sends.extend(models)
        return self