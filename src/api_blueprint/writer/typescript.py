from __future__ import annotations

from api_blueprint.writer import BaseBlueprint, BaseWriter, templates, utils
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import (
    Field, Model, Array, Null, Map, FieldWrappedModel,
    Enum as ModelEnum, AnonKV,
    iter_model_vars, model_to_pydantic,
    iter_field_model_type, unwrap_model_type,
    AnyModel,
)
from api_blueprint.engine.router import Router
from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.wrapper import ResponseWrapper, NoneWrapper
from api_blueprint.engine.utils import snake_to_pascal_case, inc_to_letters, is_parametrized
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any, Dict, Generator, Iterable,
    List, Optional, Set, Tuple, Type, TypeVar, Union,
    get_origin, get_args,
)
from collections import OrderedDict
from pydantic.fields import FieldInfo
from contextlib import contextmanager
import logging
import enum
import json
import re
import os


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TypeScriptWriter")
logger.setLevel(logging.INFO)

LANG: str = "typescript"

def _cap_token(tok: str) -> str:
    if not tok:
        return ""
    if tok.isupper():
        # REQ/RSP/JSON/QUERY/WS 等
        return tok[:1].upper() + tok[1:].lower()
    # 保留内部 CamelCase，仅保证首字母大写
    return tok[:1].upper() + tok[1:]

def _to_ts_name(name: str, invalid_prefix: str = "Func") -> str:
    """
    Convert internal proto names (e.g. REQ_Abc_JSON) to TypeScript friendly PascalCase.
    Examples:
      RSP_ListMarketOrders_JSON -> RspListMarketOrdersJson
      REQ_Ws_QUERY             -> ReqWsQuery
      WsMessage                -> WsMessage (unchanged)
    """
    if not name:
        return "AnonType"

    # 已经是 PascalCase 的，直接返回（WsMessage/GeneralWrapper/ProxyConfig 等）
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
        return name

    # 支持 path 形式（如果未来有 a/b/c 这种）
    tokens: list[str] = []
    for seg in name.split("/"):
        if not seg:
            continue
        tokens.extend([t for t in re.split(r"[^0-9A-Za-z]+", seg) if t])

    out = "".join(_cap_token(t) for t in tokens)
    if not out:
        return "AnonType"
    if not out[0].isalpha():
        out = invalid_prefix + out
    return out


def _to_ts_identifier(name: str) -> str:
    """
    Determine a safe identifier for object keys; wrap with quotes when required.
    """
    if not name:
        return '"_"'
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return json.dumps(name)


def _to_camel(name: str) -> str:
    if not name:
        return name
    return name[0].lower() + name[1:]


@dataclass
class TypeScriptResolvedType:
    text: str
    deps: Set['TypeScriptProto'] = field(default_factory=set)


class TypeScriptTypeResolver:
    SIMPLE_TYPE_MAPPING: Dict[str, str] = {
        "string": "string",
        "str": "string",
        "int": "number",
        "int64": "number",
        "int32": "number",
        "int16": "number",
        "int8": "number",
        "uint": "number",
        "uint64": "number",
        "uint32": "number",
        "uint16": "number",
        "uint8": "number",
        "float": "number",
        "float64": "number",
        "float32": "number",
        "boolean": "boolean",
        "bool": "boolean",
        "byte": "number",
        "null": "null",
        "any": "any",
    }

    def __init__(self, registry: "TypeScriptProtoRegistry"):
        self.registry = registry

    def resolve(self, field: Union[Field, Model, Type[Any], Any]) -> TypeScriptResolvedType:
        kind = self._infer_kind(field)
        if kind in self.SIMPLE_TYPE_MAPPING:
            return TypeScriptResolvedType(self.SIMPLE_TYPE_MAPPING[kind])

        resolver = {
            "array": self._resolve_array,
            "enum": self._resolve_enum,
            "map": self._resolve_map,
            "anonkv": self._resolve_anon_kv,
            "object": self._resolve_object,
        }.get(kind)

        if resolver is not None:
            return resolver(field)

        if self._is_model(field):
            return self._resolve_object(field)

        return TypeScriptResolvedType("any")

    def _infer_kind(self, field: Union[Field, Model, Type[Any], Any]) -> str:
        if isinstance(field, AnonKV):
            return "anonkv"

        candidate = field
        if isinstance(field, (Field, Model)):
            candidate = field
        elif isinstance(field, type):
            candidate = field

        type_name = getattr(candidate, "__type__", None)
        if type_name:
            return type_name.lower()

        if isinstance(candidate, type):
            return candidate.__name__.lower()

        origin = get_origin(candidate)
        if origin:
            return self._infer_kind(origin)

        return candidate.__class__.__name__.lower()

    def _resolve_array(self, field: Union[Field, Type[Field], Any]) -> TypeScriptResolvedType:
        array_field = self._ensure_instance(field, Array)
        if not isinstance(array_field, Array):
            return TypeScriptResolvedType("any[]")
        elem = array_field.elem_type()
        if self._is_generic(elem):
            elem = elem()
        elem_type = self.resolve(elem)
        return TypeScriptResolvedType(f"Array<{elem_type.text}>", set(elem_type.deps))

    def _resolve_enum(self, field: Union[Field, Type[Field], enum.EnumMeta]) -> TypeScriptResolvedType:
        enum_cls = None
        if isinstance(field, ModelEnum):
            enum_cls = field.enum_type()
        elif isinstance(field, type) and issubclass(field, enum.Enum):
            enum_cls = field
        elif isinstance(field, Field) and isinstance(field.__class__, enum.EnumMeta):
            enum_cls = field.__class__

        if enum_cls is None:
            return TypeScriptResolvedType("string")

        values = [member.value for member in list(enum_cls)]
        if not values:
            return TypeScriptResolvedType("string")

        proto = self.registry.ensure_enum(enum_cls)
        return TypeScriptResolvedType(proto.name, {proto})

    def _resolve_map(self, field: Union[Map, Type[Map]]) -> TypeScriptResolvedType:
        map_field = self._ensure_instance(field, Map)
        if not isinstance(map_field, Map):
            return TypeScriptResolvedType("Record<string, any>")

        key_type = self.resolve(map_field.key_type())
        value_type = self.resolve(map_field.value_type())
        key_text = self._normalize_record_key(key_type.text)
        deps = set(key_type.deps) | set(value_type.deps)
        return TypeScriptResolvedType(f"Record<{key_text}, {value_type.text}>", deps)

    def _resolve_anon_kv(self, field: AnonKV) -> TypeScriptResolvedType:
        return self.resolve(field.get_obj())

    def _resolve_object(self, field: Union[Model, Type[Model]]) -> TypeScriptResolvedType:
        model_cls = unwrap_model_type(field)
        proto = self.registry.ensure(model_cls, tag="shared")
        return TypeScriptResolvedType(proto.name, {proto} if proto else set())

    def _ensure_instance(self, field: Any, expected: Type[Any]) -> Any:
        if isinstance(field, expected):
            return field
        if isinstance(field, type) and issubclass(field, expected):
            return field()
        if self._is_generic(field):
            return field()
        return field

    def _is_model(self, field: Any) -> bool:
        if isinstance(field, Model):
            return True
        if isinstance(field, type) and issubclass(field, Model):
            return True
        origin = get_origin(field)
        if origin:
            return self._is_model(origin)
        return False

    def _is_generic(self, field: Any) -> bool:
        return get_origin(field) is not None

    def _normalize_record_key(self, key: str) -> str:
        if key in {"number", "string", "symbol"}:
            return key
        if key == "boolean":
            return "string"
        return "string"


@dataclass
class TypeScriptProtoField:
    identifier: str
    json_name: str
    type: TypeScriptResolvedType
    optional: bool
    description: Optional[str] = None


@dataclass(eq=False)
class TypeScriptProto:
    name: str
    model: Optional[AnyModel]
    kind: str
    module: str
    alias_type: Optional[TypeScriptResolvedType] = None
    enum_members: Optional[List[Tuple[str, Any]]] = None
    fields: List[TypeScriptProtoField] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    routes: Set[str] = field(default_factory=set)
    generic_params: "OrderedDict[Any, str]" = field(default_factory=OrderedDict)

    def add_tag(self, tag: Optional[str]):
        if tag:
            self.tags.add(tag)

    def add_route(self, route: Optional[str]):
        if route:
            self.routes.add(route)

    def type_reference(self, args: Optional[List[str]] = None, default_any: bool = True) -> str:
        if not self.generic_params:
            return self.name
        if args is None:
            if default_any:
                args = ["any"] * len(self.generic_params)
            else:
                args = []
        return f"{self.name}<{', '.join(args)}>"

    def dependencies(self) -> Set['TypeScriptProto']:
        deps: Set[TypeScriptProto] = set()
        for field in self.fields:
            deps |= {dep for dep in field.type.deps if dep}
        if self.alias_type:
            deps |= {dep for dep in self.alias_type.deps if dep}
        deps.discard(self)
        return deps


class TypeScriptProtoRegistry:
    def __init__(self):
        self._resolver = TypeScriptTypeResolver(self)
        self._protos: Dict[Any, TypeScriptProto] = {}
        self._building: Set[Any] = set()
        self._aliases: Dict[Tuple[str, str], TypeScriptProto] = {}
        self._enums: Dict[Type[enum.Enum], TypeScriptProto] = {}

    def resolver(self) -> TypeScriptTypeResolver:
        return self._resolver

    def protos(self) -> Iterable[TypeScriptProto]:
        for proto in self._protos.values():
            yield proto
        for proto in self._aliases.values():
            yield proto
        for proto in self._enums.values():
            yield proto

    def filter(
        self,
        *,
        tag: Optional[str] = None,
        module: Optional[str] = None,
    ) -> List[TypeScriptProto]:
        result = []
        for proto in self.protos():
            if tag and tag not in proto.tags:
                continue
            if module and proto.module != module:
                continue
            result.append(proto)
        return sorted(result, key=lambda proto: proto.name)

    def ensure(
        self,
        model: Optional[Union[Type[Model], Model]],
        *,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        route: Optional[str] = None,
        module: Optional[str] = None,
    ) -> Optional[TypeScriptProto]:
        if model is None:
            return None

        if isinstance(model, FieldWrappedModel):
            ts_name = _to_ts_name(name or getattr(model, "__name__", "AnonMap"))
            alias_module = module or "shared"
            proto = self._aliases.get((alias_module, ts_name))
            if proto:
                proto.add_tag(self._filter_tag(tag, model))
                proto.add_route(route)
                return proto
            alias_type = self._resolver.resolve(model.__field_type__)
            proto = TypeScriptProto(
                name=ts_name,
                model=None,
                kind="alias",
                alias_type=alias_type,
                module=module or "shared",
            )
            proto.add_tag(self._filter_tag(tag, model))
            proto.add_route(route)
            self._aliases[(alias_module, ts_name)] = proto
            return proto

        cls = unwrap_model_type(model)
        # 参数化的泛型类型需要解剖出来
        key = cls
        proto = self._protos.get(key)
        if proto:
            proto.add_tag(self._filter_tag(tag, cls))
            proto.add_route(route)
            return proto

        ts_name = _to_ts_name(name or getattr(cls, "__name__", "AnonModel"))
        target_module = module or ("shared" if not getattr(cls, "__auto__", False) else "shared")
        proto = TypeScriptProto(
            name=ts_name, 
            model=cls, 
            kind="interface", 
            module=target_module,
        )
        proto.add_tag(self._filter_tag(tag, cls))
        proto.add_route(route)
        self._protos[key] = proto
        self._building.add(key)
        try:
            self._build_proto(proto)
        finally:
            self._building.remove(key)
        return proto

    def register_alias(
        self,
        name: str,
        type_expr: TypeScriptResolvedType,
        *,
        tag: Optional[str] = None,
        route: Optional[str] = None,
        module: Optional[str] = None,
    ) -> TypeScriptProto:
        alias_module = module or "shared"
        ts_name = _to_ts_name(name)
        proto = self._aliases.get((alias_module, ts_name))
        if proto:
            proto.alias_type = type_expr
            proto.add_tag(tag)
            proto.add_route(route)
            return proto
        proto = TypeScriptProto(
            name=ts_name,
            model=None,
            kind="alias",
            alias_type=type_expr,
            module=alias_module,
        )
        proto.add_tag(tag)
        proto.add_route(route)
        self._aliases[(alias_module, ts_name)] = proto
        return proto

    def ensure_enum(
        self,
        enum_cls: Type[enum.Enum],
        *,
        module: str = "shared",
    ) -> TypeScriptProto:
        proto = self._enums.get(enum_cls)
        if proto:
            return proto
        members: List[Tuple[str, Any]] = [
            (member.name, member.value)
            for member in enum_cls
        ]
        proto = TypeScriptProto(
            name=enum_cls.__name__,
            model=None,
            kind="enum",
            module=module,
            enum_members=members,
        )
        proto.add_tag("shared")
        self._enums[enum_cls] = proto
        return proto

    def _filter_tag(self, tag: Optional[str], model: Optional[Union[Type[Model], Model]]) -> Optional[str]:
        if tag != "shared" or model is None:
            return tag
        model_cls = unwrap_model_type(model)
        name = getattr(model_cls, "__name__", "") or ""
        prefixes = ("REQ_", "RSP_", "CTX_")
        if any(name.startswith(prefix) for prefix in prefixes):
            return None
        return tag

    def _build_proto(self, proto: TypeScriptProto):
        if proto.model is None:
            return

        annotations = getattr(proto.model, "__annotations__", {})
        proto.generic_params = self._collect_generic_params(proto.model, annotations)

        pyd_model = model_to_pydantic(proto.model)
        resolver = self._resolver

        for name, field in iter_model_vars(proto.model):
            if not isinstance(field, (Field, Model)):
                continue
            model_field = pyd_model.model_fields[name]
            field_value = field or Null()
            ts_type = self._resolve_field_type(
                name,
                field_value,
                annotations,
                proto.generic_params,
                resolver,
                proto.module,
            )
            extra = getattr(field_value, "__extra__", {}) or {}
            alias = extra.get("alias") or name
            optional = (not model_field.is_required()) or extra.get("omitempty", False)
            identifier = _to_ts_identifier(alias)
            proto.fields.append(
                TypeScriptProtoField(
                    identifier=identifier,
                    json_name=alias,
                    type=ts_type,
                    optional=optional,
                    description=model_field.description or "",
                )
            )

            if isinstance(field_value, Model) and field_value.__class__ is not proto.model:
                self.ensure(field_value.__class__, tag="shared")

    def _collect_generic_params(
        self,
        model: Type[Model],
        annotations: Dict[str, Any],
    ) -> "OrderedDict[Any, str]":
        generics: "OrderedDict[Any, str]" = OrderedDict()
        generic_chars = "TUVWXYZABCDEFGHIJKLMNOPQRS"
        for name in annotations.keys():
            anno = annotations.get(name)
            if isinstance(anno, TypeVar) and anno not in generics:
                alias = inc_to_letters(len(generics), generic_chars)
                generics[anno] = alias
        return generics

    def _resolve_field_type(
        self,
        name: str,
        field: Union[Field, Model],
        annotations: Dict[str, Any],
        generic_params: "OrderedDict[Any, str]",
        resolver: TypeScriptTypeResolver,
        module: str,
    ) -> TypeScriptResolvedType:
        if type(field) is Field:
            anno = annotations.get(name)
            if anno in generic_params:
                return TypeScriptResolvedType(generic_params[anno])
        if isinstance(field, Model):
            target_module = module if getattr(field.__class__, "__auto__", False) else "shared"
            proto = self.ensure(field.__class__, tag="shared" if target_module == "shared" else None, module=target_module)
            if proto is None:
                return TypeScriptResolvedType("any")
            return TypeScriptResolvedType(proto.name, {proto})
        return resolver.resolve(field)


class TypeScriptRoute:
    def __init__(
        self,
        router: Router,
        registry: TypeScriptProtoRegistry,
        *,
        route_prefix: str,
    ):
        self.router = router
        self.registry = registry
        self.route_prefix = route_prefix

        self.func_name = self._func_name()
        self.group_prefix = self._group_prefix()
        self.group_slug = self._group_slug()
        self.group_alias = self._group_alias()
        self.group_pascal = self._group_pascal()
        self.method_name = _to_camel(self.func_name)
        self.url = router.url
        self.summary = router.extra.get("summary")
        self.description = router.extra.get("description")
        self.tags = router.tags
        self.deprecated = router.is_deprecated

        self.http_methods = [m for m in router.methods if m != "WS"]
        self.supports_ws = any(m == "WS" for m in router.methods)

        self.query_proto = self._ensure_model(router.req_query, "REQ", "QUERY")
        self.form_proto = self._ensure_model(router.req_form, "REQ", "FORM")
        self.json_proto = self._ensure_model(router.req_json, "REQ", "JSON")
        self.bin_proto = router.req_bin is not None

        self.response_media_type = router.rsp_media_type
        self.response_payload_proto = self._ensure_model(router.rsp_model, "RSP", "JSON")
        wrapper_cls = router.response_wrapper or NoneWrapper
        self.wrapper_proto = self.registry.ensure(
            wrapper_cls,
            tag="wrapper",
        )
        self.response_alias = self._ensure_response_alias()

    @property
    def http_method(self) -> str:
        if self.http_methods:
            return self.http_methods[0]
        if self.supports_ws:
            return "WS"
        return "GET"

    @property
    def has_body(self) -> bool:
        return bool(self.json_proto or self.form_proto or self.bin_proto)

    @property
    def query_type_expr(self) -> Optional[str]:
        return self._type_expr(self.query_proto)

    @property
    def json_type_expr(self) -> Optional[str]:
        return self._type_expr(self.json_proto)

    @property
    def form_type_expr(self) -> Optional[str]:
        return self._type_expr(self.form_proto)

    @property
    def response_type_expr(self) -> str:
        return self._type_expr(self.response_alias) or "void"

    @property
    def response_type_name(self) -> str:
        return self.response_alias.name if self.response_alias else "void"

    def _func_name(self) -> str:
        if not self.router.leaf.strip("/"):
            return "Root"
        return snake_to_pascal_case(self.router.leaf, "", "Z")

    def _group_prefix(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            return re.sub(r"[^0-9A-Za-z]+", "_", branch).upper()
        root = (self.router.group.root or "").strip("/")
        if root:
            return re.sub(r"[^0-9A-Za-z]+", "_", root).upper()
        return "ROOT"

    def _group_slug(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            slug = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
        else:
            root = (self.router.group.root or "").strip("/")
            if root:
                # slug = re.sub(r"[^0-9A-Za-z]+", "_", root.lower()) or "root"
                slug = "(root)"
            else:
                slug = "root"
        if slug == "shared":
            slug = "shared_group"
        return slug

    def _group_alias(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            alias = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
        else:
            root = (self.router.group.root or "").strip("/")
            if root:
                alias = re.sub(r"[^0-9A-Za-z]+", "_", root.lower()) or "root"
            else:
                alias = "root"
        if alias == "shared":
            alias = "shared_group"
        return alias

    def _group_pascal(self) -> str:
        return snake_to_pascal_case(self.group_slug, '', "Group")

    def _ensure_model(
        self,
        model: Optional[Union[Type[Model], Model]],
        prefix: str,
        suffix: str,
    ) -> Optional[TypeScriptProto]:
        if model is None:
            return None
        auto_flag = getattr(model, "__auto__", False)
        is_route_model = auto_flag or isinstance(model, FieldWrappedModel)
        if is_route_model:
            explicit = self._route_model_name(prefix, suffix)
        else:
            model_name = getattr(model, "__name__", None)
            explicit = model_name or self._route_model_name(prefix, suffix)
        tag = "route" if is_route_model else "shared"
        module = self.group_slug if is_route_model else "shared"
        return self.registry.ensure(
            model,
            name=explicit,
            tag=tag,
            route=self.func_name,
            module=module,
        )

    def _route_model_name(self, prefix: str, suffix: str) -> str:
        parts = [prefix, self.func_name]
        if suffix:
            parts.append(suffix)
        return "_".join(parts)

    def _type_expr(self, proto: Optional[TypeScriptProto]) -> Optional[str]:
        if proto is None:
            return None
        namespace = "Models" if proto.module == self.group_slug else "Shared"
        return f"{namespace}.{proto.name}"

    def _ensure_response_alias(self) -> Optional[TypeScriptProto]:
        alias_base = self._route_model_name("RSP", "")
        if self.response_media_type != "application/json":
            alias_type = TypeScriptResolvedType("string")
        else:
            payload_proto = self.response_payload_proto
            payload_type = "void"
            payload_deps: Set[TypeScriptProto] = set()
            if payload_proto:
                payload_type = payload_proto.name
                payload_deps.add(payload_proto)

            alias_text = payload_type
            deps = set(payload_deps)
            if self.wrapper_proto and self.wrapper_proto.fields:
                alias_text = self.wrapper_proto.type_reference([payload_type])
                deps.add(self.wrapper_proto)
            alias_type = TypeScriptResolvedType(alias_text, deps)
        return self.registry.register_alias(
            alias_base,
            alias_type,
            tag="route",
            route=self.func_name,
            module=self.group_slug,
        )


class TypeScriptRouterGroup:
    def __init__(self, bp: "TypeScriptBlueprint", group: RouterGroup):
        self.bp = bp
        self.group = group

    @property
    def routers(self) -> List[Router]:
        return list(self.group)


@dataclass
class TypeScriptViewGroup:
    slug: str
    alias: str
    prefix: str
    routes: List[TypeScriptRoute] = field(default_factory=list)

    @property
    def client_class(self) -> str:
        base = snake_to_pascal_case(self.alias or "root", '', "Group")
        if not base.endswith("Client"):
            base += "Client"
        return base


class TypeScriptBlueprint(BaseBlueprint["TypeScriptWriter"]):
    def __init__(self, writer: "TypeScriptWriter", bp: "Blueprint"):
        super().__init__(writer, bp)
        self.router_groups: Optional[List[TypeScriptRouterGroup]] = None
        self.registry = TypeScriptProtoRegistry()
        self.routes: List[TypeScriptRoute] = []
        self.groups: "OrderedDict[str, TypeScriptViewGroup]" = OrderedDict()

    @property
    def package(self) -> str:
        return self.bp.root.strip("/") or "root"

    def get_router_groups(self) -> List[TypeScriptRouterGroup]:
        groups = self.router_groups
        if groups is None:
            group_set: Set[RouterGroup] = set()
            groups = []
            for group, _router in self.iter_router():
                if group in group_set:
                    continue
                group_set.add(group)
                groups.append(TypeScriptRouterGroup(self, group))
            self.router_groups = groups
        return groups

    def collect(self):
        self.routes = []
        self.groups = OrderedDict()
        for group in self.get_router_groups():
            for router in group.routers:
                self._register_route(router)

    def _register_route(self, router: Router):
        self._register_common_models(router)
        ts_route = TypeScriptRoute(
            router,
            self.registry,
            route_prefix=self.package,
        )
        self.routes.append(ts_route)
        group = self.groups.get(ts_route.group_slug)
        if group is None:
            group = TypeScriptViewGroup(
                slug=ts_route.group_slug, 
                alias=ts_route.group_alias, 
                prefix=ts_route.group_prefix,
            )
            self.groups[ts_route.group_slug] = group
        group.routes.append(ts_route)

    def _register_common_models(self, router: Router):
        def collect(model: Optional[Union[Type[Model], Model]]):
            if model is None:
                return
            model_cls = unwrap_model_type(model)
            for nested in iter_field_model_type(model):
                if nested is model_cls:
                    continue
                self.registry.ensure(nested, tag="shared")

            # 对于非自动生成的Model需要放到com包中(关于参数化的泛型类型不作为独立类型处理)
            if getattr(model_cls, '__auto__', None) is False and not is_parametrized(model_cls):
                self.registry.ensure(model_cls, tag="shared")

        collect(router.req_query)
        collect(router.req_form)
        collect(router.req_json)
        collect(router.rsp_model)
        for recv in router.recvs:
            collect(recv)
        for send in router.sends:
            collect(send)

    def shared_sections(self) -> List[Tuple[str, List[TypeScriptProto]]]:
        sections: List[Tuple[str, List[TypeScriptProto]]] = []
        shared_models = [
            proto
            for proto in self.registry.filter(module="shared")
            if "wrapper" not in proto.tags
        ]
        if shared_models:
            sections.append(("Shared Models", shared_models))
        wrappers = self.registry.filter(tag="wrapper", module="shared")
        if wrappers:
            sections.append(("Response Wrappers", wrappers))
        return sections

    def group_sections(self, module: str) -> List[Tuple[str, List[TypeScriptProto]]]:
        protos = self.registry.filter(module=module)
        if not protos:
            return []
        return [("Route Contracts", protos)]

    def module_dirs(self, base_dir: Path) -> Dict[str, Path]:
        dirs: Dict[str, Path] = {"shared": base_dir / "shared"}
        for slug in self.groups.keys():
            dirs[slug] = base_dir / slug
        return dirs

    def _relative_import_path(self, current_dir: Path, target_file: Path) -> str:
        rel = os.path.relpath(target_file.with_suffix(""), start=current_dir)
        return rel.replace("\\", "/")

    def build_imports(
        self,
        module: str,
        module_dirs: Dict[str, Path],
    ) -> List[Dict[str, Any]]:
        current_dir = module_dirs[module]
        protos = self.registry.filter(module=module)
        deps_map: Dict[str, Set[str]] = OrderedDict()
        for proto in protos:
            for dep in proto.dependencies():
                dep_module = dep.module
                if dep_module == module or dep_module not in module_dirs:
                    continue
                path = self._relative_import_path(current_dir, module_dirs[dep_module] / "models.ts")
                deps_map.setdefault(path, set()).add(dep.name)
        return [
            {"path": path, "names": sorted(names)}
            for path, names in sorted(deps_map.items(), key=lambda kv: kv[0])
        ]

    def gen(self):
        self.collect()
        base_dir = self.writer.working_dir / self.package
        base_dir.mkdir(parents=True, exist_ok=True)
        module_dirs = self.module_dirs(base_dir)

        shared_dir = module_dirs["shared"]
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared_sections = self.shared_sections()
        shared_imports = self.build_imports("shared", module_dirs)
        shared_context = {
            "sections": shared_sections,
            "imports": shared_imports,
            "exports": [],
        }
        for tmpl in ["gen_models.ts", "models.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=tmpl.startswith("gen_")) as f:
                if f:
                    f.write(templates.render(LANG, tmpl, shared_context))

        for out_tmpl, tmpl in [
            ("gen_client.ts", 'gen_shared_client.ts'), 
            ("client.ts", 'client.ts'),
        ]:
            with self.writer.write_file(shared_dir / out_tmpl, overwrite=out_tmpl.startswith("gen_")) as f:
                if f:
                    f.write(templates.render(LANG, tmpl, {}))

        for tmpl in ["gen_index.ts", "index.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=True) as f:
                if f:
                    f.write(templates.render(LANG, tmpl, {
                        "client_class": None,
                        "extra_exports": ['export * from "./gen_client";'],
                    }))


        for group in self.groups.values():
            group_dir = module_dirs[group.slug]
            group_dir.mkdir(parents=True, exist_ok=True)
            sections = self.group_sections(group.slug)
            imports = self.build_imports(group.slug, module_dirs)
            models_context = {
                "sections": sections,
                "imports": imports,
                "exports": [],
            }
            for tmpl in ["gen_models.ts", "models.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as f:
                    if f:
                        f.write(templates.render(LANG, tmpl, models_context))


            client_context = {
                "routes": group.routes,
                "writer": self.writer,
                "client_class": group.client_class,
            }
            for tmpl in ["gen_client.ts", "client.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as f:
                    if f:
                        f.write(templates.render(LANG, tmpl, client_context))

            for tmpl in ["gen_index.ts", "index.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as f:
                    if f:
                        f.write(templates.render(LANG, tmpl, {
                            "client_class": group.client_class,
                            "extra_exports": [],
                        }))


        exports = [{"alias": "Shared", "path": "./shared"}]
        second_exports: List[Tuple[str, TypeScriptViewGroup]] = []
        seen_alias = set()
        for slug, group in self.groups.items():
            if slug != group.alias:
                # (root)的命名退让
                second_exports.append((slug, group))
                continue
            alias = snake_to_pascal_case(group.alias, '', "Group")
            exports.append({"alias": alias, "path": f"./{slug}"})
            seen_alias.add(alias)

        for slug, group in second_exports:
            alias = snake_to_pascal_case(group.alias, '', "Group")
            if alias in seen_alias:
                # 尝试100次，如果还是冲突，则放弃
                for i in range(1, 100):
                    alias = snake_to_pascal_case(f'{group.alias}{i}', '', "Group")
                    if alias not in seen_alias:
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique alias for group {group.alias}")
            exports.append({"alias": alias, "path": f"./{slug}"})
            seen_alias.add(alias)

        exports = sorted(exports, key=lambda x: x["alias"])
        with self.writer.write_file(base_dir / "gen_index.ts", overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, "gen_root_index.ts", {"modules": exports}))

        for out_tmpl, tmpl in [
            ("gen_index.ts", 'gen_root_index.ts'), 
            ("index.ts", 'index.ts'),
        ]:           
            with self.writer.write_file(base_dir / out_tmpl, overwrite=out_tmpl.startswith("gen_")) as f:
                if f:
                    f.write(templates.render(LANG, tmpl, {"modules": exports}))
        

class TypeScriptWriter(BaseWriter[TypeScriptBlueprint]):
    def __init__(self, working_dir: Union[str, Path] = ".", *, base_url: Optional[str] = None):
        super().__init__(working_dir)
        self.base_url = base_url or ""
        self._written_files: Set[str] = set()

    def gen(self):
        for bp in self.bps:
            bp.build()
            bp.gen()

    @contextmanager
    def write_file(self, filepath: Union[str, Path], overwrite: bool = False):
        filepath = str(filepath)
        wrote = False
        with utils.ensure_filepath_open(filepath, "w", overwrite=overwrite) as f:
            if f:
                wrote = True
            yield f
        if wrote:
            logger.info(f"[+] Written: {filepath}")
        else:
            logger.info(f"[.] Skipped: {filepath}")
