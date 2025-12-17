from api_blueprint.writer import BaseBlueprint, BaseWriter, utils
from typing import (
    List, Optional, Dict, Any, Set, Generator, Union, Literal, TypeVar,
    Generic, Tuple, Type, IO, get_origin, get_args, ForwardRef,
)
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import (
    Field, Model, Array, Null, Map, FieldWrappedModel, Error, Enum, AnonKV, 
    create_model, model_to_pydantic, iter_model_vars,
    Proto, iter_field_model_type, AnyModel, iter_error_models,
    get_forward_ref_type, iter_enum_classes, BASIC_FIELD_TYPES,
)
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.engine.router import Router
from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.utils import (
    snake_to_pascal_case, pascal_to_snake_case, 
    inc_to_letters, join_path_imports, is_parametrized,
)
from itertools import chain
from api_blueprint.writer import templates
from api_blueprint.writer.utils import SafeFmtter
import logging
from pydantic.fields import FieldInfo
import subprocess
import enum
import re
import json
import shutil


logging.basicConfig(
    level=logging.INFO,            
    format="%(message)s",
)


logger = logging.getLogger('GolangWriter')
logger.setLevel(logging.INFO)

LANG: str = 'golang'

class PackageName(str, enum.Enum):
    COM_PROTOS = 'protos'
    COM_ENUMS  = 'enums'
    PROVIDER   = 'provider'
    ERROR      = 'errors'
    VIEWS      = 'views'


PROTO_STRUCT_TYPE = Literal['struct', 'generic', 'alias']


type_reg = re.compile(r'\{(\w+)_((imports|package)\$?)\}')

class GolangType(SafeFmtter):
    parents: Optional[str] = None

    def __init__(self, v):
        super().__init__()

        ps = set()
        for res in type_reg.findall(str(v)):
            parent = res[0]
            ps.add(parent)

        self.parents = list(ps)

    def render(self, formatters: Optional[Dict[str, str]] = None) -> str:
        formatters = formatters or {}

        def repl(match: re.Match) -> str:
            key = f"{match.group(1)}_{match.group(2)}"
            return formatters.get(key, '')

        return type_reg.sub(repl, str(self))


class GolangTypeResolver:

    SIMPLE_TYPE_MAPPING = {
        'string': 'string',
        'str': 'string',
        'int': 'int',
        'int64': 'int64',
        'int32': 'int32',
        'int16': 'int16',
        'int8': 'int8',
        'uint': 'uint',
        'uint64': 'uint64',
        'uint32': 'uint32',
        'uint16': 'uint16',
        'uint8': 'uint8',
        'float': 'float64',
        'float64': 'float64',
        'float32': 'float32',
        'boolean': 'bool',
        'bool': 'bool',
        'byte': 'byte',
        'error': 'error',
        'null': 'nil',
    }

    def resolve(self, field: Union[Field, Model, Type[Any], Any], *, pointer_allowed: bool = True) -> str:
        kind = self._infer_kind(field)
        if kind in self.SIMPLE_TYPE_MAPPING:
            return self.SIMPLE_TYPE_MAPPING[kind]

        resolver = {
            'array': self._resolve_array,
            'enum': self._resolve_enum,
            'map': self._resolve_map,
            'anonkv': self._resolve_anon_kv,
            'object': self._resolve_object,
        }.get(kind)

        if resolver is not None:
            return resolver(field, pointer_allowed=pointer_allowed)

        if self._is_model(field):
            return self._resolve_object(field, pointer_allowed=pointer_allowed)

        return 'any'

    def _infer_kind(self, field: Union[Field, Model, Type[Any], Any]) -> str:
        if isinstance(field, AnonKV):
            return 'anonkv'

        candidate = field
        if isinstance(field, (Field, Model)):
            candidate = field
        elif isinstance(field, type):
            candidate = field

        type_name = getattr(candidate, '__type__', None)
        if type_name:
            return type_name.lower()

        if isinstance(candidate, type):            
            if issubclass(candidate, enum.Enum):
                print(candidate)
                return "enum"

            return candidate.__name__.lower()

        origin = get_origin(candidate)
        if origin:
            return self._infer_kind(origin)

        return candidate.__class__.__name__.lower()

    def _resolve_array(self, field: Union[Field, Type[Field], Any], *, pointer_allowed: bool) -> str:
        array_field = self._ensure_instance(field, Array)
        if not isinstance(array_field, Array):
            return '[]any'
        elem = array_field.elem_type()
        if self._is_generic(elem):
            elem = elem()
        elem_type = self.resolve(elem, pointer_allowed=False)
        if self._is_model(elem):
            return f'[]*{elem_type}'
        return f'[]{elem_type}'

    def _resolve_enum(self, field: Enum | enum.Enum, *, pointer_allowed: bool) -> str:
        if is_parametrized(field):
            field = field()
        base_type_getter = getattr(field, "enum_base_type", None)
        if base_type_getter is None:
            base_type_getter = Enum[field]().enum_base_type
        base_type = base_type_getter()
        return self.resolve(base_type, pointer_allowed=pointer_allowed)

    def _resolve_map(self, field: Union[Map, Type[Map]], *, pointer_allowed: bool) -> str:
        map_field = self._ensure_instance(field, Map)
        if not isinstance(map_field, Map):
            return 'map[string]any'
        key_type = map_field.key_type()
        value_type = map_field.value_type()

        resolved_key = self.resolve(key_type, pointer_allowed=False)
        resolved_value = self.resolve(value_type, pointer_allowed=False)

        if self._is_model(value_type):
            resolved_value = f'*{resolved_value}'

        return f'map[{resolved_key}]{resolved_value}'

    def _resolve_anon_kv(self, field: AnonKV, *, pointer_allowed: bool) -> str:
        return self.resolve(field.get_obj(), pointer_allowed=pointer_allowed)

    def _resolve_object(self, field: Union[Model, Type[Model]], *, pointer_allowed: bool) -> str:
        model_cls = field if isinstance(field, type) else field.__class__
        pointer = '*' if pointer_allowed else ''
        return GolangType(f'{pointer}{{protos_package$}}{model_cls.__name__}')

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

class GolangTagBuilder:

    DEFAULT_TAG_FIELDS = ('json', 'xml', 'form')

    @staticmethod
    def binding(field_info: FieldInfo, omitempty: bool = False) -> str:
        parts: List[str] = []
        if omitempty:
            parts.append("omitempty")
        elif field_info.is_required():
            parts.append("required")

        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            enum_values = " ".join(str(e.value) for e in list(annotation))
            parts.append(f'oneof={enum_values}')

        for meta in field_info.metadata:
            if getattr(meta, 'gt', None) is not None:
                parts.append(f"gt={meta.gt}")
            if getattr(meta, 'ge', None) is not None:
                parts.append(f"gte={meta.ge}")
            if getattr(meta, 'lt', None) is not None:
                parts.append(f"lt={meta.lt}")
            if getattr(meta, 'le', None) is not None:
                parts.append(f"lte={meta.le}")
            if getattr(meta, 'min_length', None) is not None:
                parts.append(f"min={meta.min_length}")
            if getattr(meta, 'max_length', None) is not None:
                parts.append(f"max={meta.max_length}")
            if getattr(meta, 'regex', None) is not None:
                parts.append(f"regexp={meta.regex.pattern}")

        return ",".join(filter(None, parts))

    @classmethod
    def build(cls, name: str, field: Union[Field, Model], field_info: FieldInfo) -> str:
        extra = getattr(field, '__extra__', {}) or {}
        alias = extra.get('alias')
        omitempty = extra.get('omitempty', False)
        field_name = alias or name
        normal_val = field_name if not omitempty else f'{name},omitempty'

        tags: List[Tuple[str, str]] = [(tag, normal_val) for tag in cls.DEFAULT_TAG_FIELDS]

        binding = cls.binding(field_info, omitempty)
        if binding:
            tags.append(('binding', binding))

        return ' '.join(f'{tag}:"{value}"' for tag, value in tags)


@dataclass(frozen=True)
class GolangProtoField:
    name: str
    field: str
    type: GolangType
    tags: str

    def render(self, formatters: Dict[str, str]) -> 'GolangProtoFieldView':
        return GolangProtoFieldView(
            name=self.name,
            field=self.field,
            type=self.type.render(formatters),
            tags=self.tags,
        )
    
    def import_specs(self, formatters: Dict[str, str]) -> List[str]:
        parents = getattr(self.type, 'parents', [])
        imps = []
        for parent in parents:
            package = formatters.get(f'{parent}_package', '')
            imports = formatters.get(f'{parent}_imports', '')
            if not package or not imports:
                continue
            imps.append(f'{package} "{imports}"')
        return imps


@dataclass(frozen=True)
class GolangProtoFieldView:
    name: str
    field: str
    type: str
    tags: str


@dataclass(frozen=True)
class GolangEnumMember:
    name: str
    value: Any

    @property
    def go_value_literal(self) -> str:
        return _go_literal(self.value)


@dataclass(frozen=True)
class GolangEnum:
    name: str
    base_type: str
    members: List[GolangEnumMember]

    @classmethod
    def from_enum(cls, enum_cls: Type[enum.Enum]) -> Optional['GolangEnum']:
        members = [GolangEnumMember(name=member.name, value=member.value) for member in enum_cls]
        if not members:
            return None
        base_type = _detect_go_base_type(type(members[0].value))
        return cls(name=enum_cls.__name__, base_type=base_type, members=members)


def _detect_go_base_type(value_type: Type[Any]) -> str:
    candidates: Tuple[Tuple[Type[Any], str], ...] = (
        (bool, 'bool'),
        (int, 'int'),
        (float, 'float64'),
        (str, 'string'),
    )
    for py_type, go_type in candidates:
        try:
            if issubclass(value_type, py_type):
                return go_type
        except TypeError:
            continue
    return 'string'


def _go_literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, default=str)



@dataclass(frozen=True)
class GolangPackageLayout:
    module_import: str
    views_package: str
    provider_package: str
    errors_package: str

    @property
    def views_imports(self) -> str:
        return join_path_imports(self.module_import, self.views_package)

    @property
    def provider_imports(self) -> str:
        return join_path_imports(self.views_imports, self.provider_package)

    @property
    def errors_imports(self) -> str:
        return join_path_imports(self.module_import, self.errors_package)

    def formatters(self, update: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        fmts = {
            'views_package': self.views_package,
            'views_imports': self.views_imports,
            'provider_package': self.provider_package,
            'provider_imports': self.provider_imports,
            'errors_package': self.errors_package,
            'errors_imports': self.errors_imports,
        }
        fmts.update({k + '$': v + '.' for k, v in fmts.items() if k.endswith('_package')})
        if update:
            fmts.update(update)
        return fmts


@dataclass
class GolangProtoStruct:
    _resolver = GolangTypeResolver()

    @staticmethod
    def get_field_type(field: Union[Field, Model, Type[Any], Any], is_sub: bool = False) -> str:
        pointer_allowed = not is_sub
        return GolangProtoStruct._resolver.resolve(field, pointer_allowed=pointer_allowed)

    @staticmethod
    def get_binding_tag(field: FieldInfo, omitempty: bool = False) -> str:
        return GolangTagBuilder.binding(field, omitempty)

    @staticmethod
    def get_field_tags(name: str, field: Union[Field, Model], field_info: FieldInfo) -> str:
        return GolangTagBuilder.build(name, field, field_info)


@dataclass
class GolangProtoGeneric:
    name: GolangType
    types: List[Union['GolangProto', GolangType]]

    def type_reference(self, formatters: Dict[str, str]) -> str:
        return self.name.render(formatters)

    def import_specs(self, formatters: Dict[str, str]) -> List[str]:
        parents = self.name.parents
        for t in self.types:
            if isinstance(t, GolangProto):
                parents += t.import_specs(formatters)
        imps = []
        for parent in parents:
            package = formatters.get(f'{parent}_package', '')
            imports = formatters.get(f'{parent}_imports', '')
            if not package or not imports:
                continue
            imps.append(f'{package} "{imports}"')
        return imps

@dataclass
class GolangProtoAlias:
    name: GolangType
    proto: Optional['GolangProto'] = None
    new_type: bool = False

    def type_reference(self, formatters: Dict[str, str]) -> str:
        return self.name.render(formatters)

    def import_specs(self, formatters: Dict[str, str]) -> List[str]:
        parents = self.name.parents
        if self.proto is not None:
            parents += self.proto.import_specs(formatters)
        imps = []
        for parent in parents:
            package = formatters.get(f'{parent}_package', '')
            imports = formatters.get(f'{parent}_imports', '')
            if not package or not imports:
                continue
            imps.append(f'{package} "{imports}"')
        return imps


class GolangFieldWrappedModel(FieldWrappedModel):
    @property
    def __name__(self) -> str:
        return GolangProtoStruct.get_field_type(self.__field_type__)

    @__name__.setter
    def __name__(self, *args) -> str:
        pass


class GolangResponseWrapper:
    prefix: str
    response_wrapper: Type[ResponseWrapper]
    _proto: Optional['GolangProto'] = None

    def __init__(self, prefix: str, response_wrapper: Type[ResponseWrapper]):
        self.prefix = prefix
        self.response_wrapper = response_wrapper
        self._proto = None

    @property
    def proto_def_name(self) -> str:
        name = self.proto_name
        name += self.generic_types(True)
        return name

    @property
    def proto(self) -> 'GolangProto':
        if self._proto is not None:
            return self._proto

        fields = [v for k, v in iter_model_vars(self.response_wrapper) if isinstance(v, (Model, Field))]
        
        alias: Optional[GolangProtoAlias] = None
        struct: Optional[GolangProtoStruct] = None
        if len(fields) > 0:
            struct_type = 'struct'
            struct = GolangProtoStruct()
        else:
            struct_type = 'alias'
            alias = GolangProtoAlias(
                name=GolangType('any'),
            )

        self._proto = GolangProto(
            name=self.prefix,
            model=self.response_wrapper,
            struct_type=struct_type,
            struct=struct,
            alias=alias,
        )
        return self._proto
 
    @property
    def proto_name(self) -> str:
        return f'{self.prefix}_{self.response_wrapper.__name__}'

    @property
    def proto_type(self) -> PROTO_STRUCT_TYPE:
        return self.proto.struct_type

    def proto_fields(self) -> List[GolangProtoField]:
        return self.proto.fields()

    def proto_fields_for(self, formatters: Dict[str, str]) -> List[GolangProtoFieldView]:
        return self.proto.fields_for(formatters)

    @property
    def class_name(self) -> str:
        return self.response_wrapper.__name__

    def generic_types(self, with_any: bool = False) -> str:
        generic_types = self.proto.generic_types()
        if generic_types:
            return f'[{", ".join(generic_types.values())}{" any" if with_any else ""}]'
        return ''

    def json_factory(self, **kwargs) -> str:
        return self.response_factory('json', **kwargs)

    def xml_factory(self, **kwargs) -> str:
        return self.response_factory('xml', **kwargs)

    def response_factory(self, type: str,  **kwargs) -> str:
        return self.response_wrapper.golang_factory(type).format(**kwargs)




class GolangProto(Proto):
    struct_type: PROTO_STRUCT_TYPE
    struct: Optional[GolangProtoStruct]
    generic: Optional[GolangProtoGeneric]
    alias: Optional[GolangProtoAlias]

    def __init__(
        self, 
        name: str, 
        model: AnyModel, 
        struct_type: PROTO_STRUCT_TYPE = 'struct',
        *,
        struct: Optional[GolangProtoStruct] = None,
        generic: Optional[GolangProtoGeneric] = None,
        alias: Optional[GolangProtoAlias] = None,
    ):
        super().__init__(name, model)
        self.struct_type = struct_type
        self.struct = struct
        self.generic = generic
        self.alias = alias

    @property
    def def_name(self) -> str:
        generic_types = self.generic_types()
        if generic_types:
            return f'{self.name}[{", ".join(generic_types.values())} any]'
        return self._name

    @classmethod
    def from_model(cls, model: AnyModel, **kwargs) -> 'GolangProto':
        return cls(model.__name__, model, **kwargs)

    @classmethod
    def from_model_ref(cls, ref_model: AnyModel, name: str, **kwargs) -> 'GolangProto':
        is_autocreate = ref_model.__auto__
        is_field_ref = isinstance(ref_model, GolangFieldWrappedModel) 
        if is_autocreate and not is_field_ref:
            proto = GolangProto(
                name,
                ref_model,
                'struct',
                struct=GolangProtoStruct(),
                **kwargs,
            )
        else:
            # field基础类型不会在com包中定义，需要排除            
            alias_is_com = not is_field_ref
            alias_proto = GolangProto.from_model(ref_model, **kwargs)
            alias_name = alias_proto.name
            if alias_is_com:
                alias_name = f'{{protos_package}}.{alias_proto.name}'
            proto = GolangProto(
                name,
                ref_model,
                'alias',
                alias=GolangProtoAlias(
                    name=GolangType(alias_name),
                    proto=alias_proto,
                ),
                **kwargs,
            )
        return proto

    def generic_types(self) -> Dict[TypeVar, str]:
        if self.model_type is None:
            return {}
        generic_types: Dict[TypeVar, str] = {}
        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue
            if field is None:
                field = Null()
            
            if type(field) is Field:
                anno = self.model_type.__annotations__.get(name, None)
                if isinstance(anno, TypeVar):
                    c = inc_to_letters(len(generic_types), 'TUVWXYZABCDEFGHIJKLMNOPQRS')
                    generic_types[anno] = c
        return generic_types

    def fields(self) -> List[GolangProtoField]:
        proto_fields: List[GolangProtoField] = []
        pydmodel = model_to_pydantic(self.model_type)
        generic_types = self.generic_types()
        annotations = getattr(self.model_type, '__annotations__', {})

        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue

            model_field = pydmodel.model_fields[name]
            if field is None:
                field = Null()

            go_type = self._resolve_field_type(name, field, generic_types, annotations)
            extra = getattr(field, '__extra__', {}) or {}
            field_name = extra.get('alias') or name

            proto_fields.append(GolangProtoField(
                name=snake_to_pascal_case(name),
                field=field_name,
                type=GolangType(go_type),
                tags=GolangProtoStruct.get_field_tags(name, field, model_field),
            ))
        return proto_fields

    def fields_for(self, formatters: Dict[str, str]) -> List[GolangProtoFieldView]:
        return [field.render(formatters) for field in self.fields()]

    def _resolve_field_type(
        self,
        name: str,
        field: Union[Field, Model],
        generic_types: Dict[TypeVar, str],
        annotations: Dict[str, Any],
    ) -> str:
        if type(field) is Field:
            anno = annotations.get(name)
            if isinstance(anno, TypeVar): # 类型注释
                generic_name = generic_types.get(anno)
                if generic_name:
                    return f'*{generic_name}'
        return GolangProtoStruct.get_field_type(field)

    def generics(self, formatters: Dict[str, str]) -> Generator[str, None, None]:
        for proto in self.generic.types:
            if isinstance(proto, GolangType):
                yield proto.render(formatters)
            else:
                yield GolangType(proto.name).render(formatters)

    def com_protos(self) -> Generator['GolangProto', None, None]:
        for model_type in iter_field_model_type(self.model_type):
            if model_type is self.model_type:
                # 去掉自身
                continue
            yield GolangProto.from_model(model_type)
        
        # 对于非自动生成的Model需要放到com包中(关于参数化的泛型类型不作为独立类型处理)
        if (getattr(self.model_type, '__auto__', None) is False and 
            not is_parametrized(self.model_type) and
            self.model_type not in BASIC_FIELD_TYPES):
            yield GolangProto.from_model(self.model_type)

    def import_specs(self, formatters: Dict[str, str]) -> List[str]:
        specs: List[str] = []
        if self.generic:
            specs += self.generic.import_specs(formatters)
        if self.alias:
            specs += self.alias.import_specs(formatters)
        return list(set(specs))


    def __iter__(self) -> Generator['GolangProto', None, None]:
        for model_type in iter_field_model_type(self.model_type):
            yield GolangProto.from_model(model_type)


class GolangError:
    _err: Error

    def __init__(self, error: Error):
        self._err = error

    @property
    def code(self) -> int:
        return self._err.code
    
    @property
    def message(self) -> str:
        return self._err.message
    
    @property
    def key(self) -> str:
        _, key = self._err.__key__
        return key.upper()


class GolangErrorGroup:
    package: str 
    imports: str
    gen_dir: str

    errors: List[GolangError]

    def __init__(self, package: str, imports: str, gen_dir: str, errs: List[Error]):
        self.package = package
        self.imports = imports
        self.gen_dir = gen_dir
        self.errors = [GolangError(err) for err in errs]
    

    def error_vars(self) -> Generator[GolangError, None, None]:
        for err in self.errors:
            yield err


class GolangRouter:
    router: Router

    def __init__(self, router: Router):
        self.router = router

    @property
    def url(self):
        return self.router.url

    @property
    def methods(self) -> List[str]:
        return [met.upper() for met in self.router.methods]

    @property
    def func_name(self):
        if not self.router.leaf.strip('/'):
            return 'ROOT_'
        return snake_to_pascal_case(self.router.leaf, '', 'Z')

    @property
    def ctx_type(self):
        return f'CTX_{self.func_name}'

    @property
    def req_type(self):
        return f'REQ_{self.func_name}'

    @property
    def rsp_type(self):
        return f'RSP_{self.func_name}'

    @property
    def req_provider(self):
        r = self.router
        return ''.join([
            v for v, ok in [
                ('Q', r.req_query),
                ('F', r.req_form),
                ('J', r.req_json),
            ] if ok
        ])

    @property
    def rsp_provider(self):
        r = self.router
        media_type_mapping = {
            'application/json': 'json',
            'application/xml': 'xml',
            'text/html': 'html',
        }
        options = [
            media_type_mapping[r.rsp_media_type],
            self.router.response_wrapper.__name__,
        ]
        return '@'.join(options)

    @property
    def providers(self):
        providers = self.router.providers
        seqs: List[str] = []
        for prov in providers:
            data = prov.data
            if prov.name == ProviderName.REQ.value:
                data = self.req_provider
            elif prov.name == ProviderName.RSP.value:
                data = self.rsp_provider
            elif prov.name == ProviderName.WS_HANDLE.value:
                data = ','.join(data)

            kv: str = prov.name
            if data:
                kv += f'={data}'
            seqs.append(kv)
        return '|'.join(seqs)

    def protos(self) -> Generator[GolangProto, None, None]:
        req_query_proto: Optional[GolangProto] = None
        req_form_proto: Optional[GolangProto] = None
        req_json_proto: Optional[GolangProto] = None
        
        if self.router.req_query is not None:
            req_query_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_query), f'{self.req_type}_QUERY')
            yield req_query_proto

        if self.router.req_form is not None:
            req_form_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_form), f'{self.req_type}_FORM')
            yield req_form_proto

        if self.router.req_json is not None:
            req_json_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_json), f'{self.req_type}_JSON')
            yield req_json_proto
        
        # REQ
        req_proto = GolangProto(
            self.req_type,
            create_model(self.req_type, {
                'Q': self.router.req_query or Null(),
                'B': self.router.req_json or self.router.req_form or Null(),
            }),
            'generic',
            generic=GolangProtoGeneric(
                name=GolangType('{provider_package$}REQ'), 
                types=[
                    req_query_proto or GolangType('any'),
                    req_json_proto or req_form_proto or GolangType('any'),
                ]
            ),
        )
        yield req_proto
        
        # RSP
        rsp_json_proto = None
        if self.router.rsp_model is not None:
            rsp_json_proto = GolangProto.from_model_ref(
                ensure_model(self.router.rsp_model), f'{self.rsp_type}_BODY')
            yield rsp_json_proto

        rsp_proto = GolangProto(
            self.rsp_type,
            self.router.rsp_model,
            'alias',
            alias=GolangProtoAlias(
                name=GolangType(rsp_json_proto.name if rsp_json_proto else 'any'),
                proto=rsp_json_proto,
            ),
        )
        yield rsp_proto

        # CTX
        ctx_proto = GolangProto(
            self.ctx_type,
            create_model(self.req_type, {
                'Q': self.router.req_query or Null(),
                'B': self.router.req_json or self.router.req_form or Null(),
                'P': self.router.rsp_model or Null(),
            }),
            'generic',
            generic=GolangProtoGeneric(
                name=GolangType('{provider_package$}Context'), 
                types=[
                    req_query_proto or GolangType('any'),
                    req_json_proto or req_form_proto or GolangType('any'),
                    rsp_json_proto or GolangType('any'),
                ],
            )
        )
        yield ctx_proto


    def com_protos(self) -> Generator[GolangProto, None, None]:
        if self.router.req_query is not None:
            yield from GolangProto.from_model(
                self.router.req_query).com_protos()

        if self.router.req_form is not None:
            yield from GolangProto.from_model(
                self.router.req_form).com_protos()

        if self.router.req_json is not None:
            yield from GolangProto.from_model(
                self.router.req_json).com_protos()

        if self.router.rsp_model is not None:
            yield from GolangProto.from_model(
                self.router.rsp_model).com_protos()

        for recv in self.router.recvs:
            yield from GolangProto.from_model(
                recv).com_protos()
                
        for send in self.router.sends:
            yield from GolangProto.from_model(
                send).com_protos()


class GolangRouterGroup:
    bp: 'GolangBlueprint'
    group: RouterGroup
    _routers: Optional[List[Router]] = None

    def __init__(self, bp: 'GolangBlueprint', group: RouterGroup):
        self.bp = bp
        self.group = group

    @property
    def routers(self):
        routers = self._routers
        if routers is None:
            routers = list(self.group)
            self._routers = routers
        
        return routers

    @property
    def package(self) -> str:
        branch: str = self.branch
        if not branch:
            return self.root
        return branch

    @property
    def root(self) -> str:
        return self.group.bp.root.strip("/")
    
    @property
    def branch(self) -> str:
        return self.group.branch.strip('/')

    @property
    def imports(self) -> str:
        branch: str = self.branch
        if not branch:
            return self.bp.imports
        return join_path_imports(self.bp.imports, self.package)

    def __len__(self) -> int:
        return len(self.group)

    def interfaces(self) -> Generator[Dict[str, Any], None, None]:
        for r in self.group:
            router = GolangRouter(r)
            yield {
                'func': router.func_name,
                'ctx_type': router.ctx_type,
                'req_type': router.req_type,
                'rsp_type': router.rsp_type,
            }
    
    def registers(self) -> Generator[Dict[str, Any], None, None]:
        for r in self.group:
            router = GolangRouter(r)
            for method in router.methods:
                yield {
                    'func': router.func_name,
                    'method': method,
                    'api': router.url,
                    'provider': router.providers,
                }
    
    def protos(self) -> Generator[GolangProto, None, None]:
        for r in self.group:
            router = GolangRouter(r)
            yield from router.protos()
    
    def com_protos(self) -> Generator[GolangProto, None, None]:
        for r in self.group:
            router = GolangRouter(r)
            yield from router.com_protos()
    
    def implements(self) -> Generator[Dict[str, Any], None, None]:
        for r in self.group:
            router = GolangRouter(r)
            yield {
                'func': router.func_name,
                'ctx_type': router.ctx_type,
                'req_type': router.req_type,
                'rsp_type': router.rsp_type,
            }

def ensure_model(model_or_map: Union[AnyModel, FieldWrappedModel]) -> Union[GolangFieldWrappedModel, AnyModel]:
    if isinstance(model_or_map, FieldWrappedModel) or (
        isinstance(model_or_map, type) and FieldWrappedModel is model_or_map):
        return GolangFieldWrappedModel(model_or_map.__field_type__)
    return model_or_map


class GolangBlueprint(BaseBlueprint['GolangWriter']):
    router_groups: Optional[List[GolangRouterGroup]] = None

    def get_router_groups(self) -> List[GolangRouterGroup]:
        groups = self.router_groups
        if groups is None:
            group_set: Set[RouterGroup] = set()
            groups = []
            for group, router in self.iter_router():
                if group in group_set:
                    continue
                group_set.add(group)
                groups.append(GolangRouterGroup(self, group))
            self.router_groups = groups
        
        return groups

    @property
    def package(self) -> str:
        return self.bp.root.strip('/')

    @property
    def imports(self) -> str:
        return join_path_imports(self.writer.views_imports, self.package)

    @property
    def com_proto_package(self) -> str:
        return PackageName.COM_PROTOS.value

    @property
    def com_proto_gen_path(self) -> str:
        return f'gen-{self.com_proto_package}'
    
    @property
    def com_proto_imports(self) -> str:
        return join_path_imports(self.imports, self.com_proto_gen_path)


    @property
    def com_enum_package(self) -> str:
        return PackageName.COM_ENUMS.value

    @property
    def com_enum_gen_path(self) -> str:
        return f'gen-{self.com_enum_package}'

    @property
    def com_enum_imports(self) -> str:
        return join_path_imports(self.imports, self.com_enum_gen_path)


    def formatters(self, update: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        fmts = self.writer.formatters()
        fmts.update({
            'enums_package': self.com_enum_package,
            'enums_imports': self.com_enum_imports,
            'protos_package': self.com_proto_package,
            'protos_imports': self.com_proto_imports,
        })
        pkg_with_dot_key = { k + '$': v + '.' for k, v in fmts.items() if k.endswith('_package') }
        fmts.update(pkg_with_dot_key)
        if update:
            fmts.update(update)
        return fmts
 
    def protos(self) -> Generator[GolangProto, None, None]:
        protos_set = set()
        for group in self.get_router_groups():
            for proto in group.protos():
                if proto.name in protos_set:
                    continue
                protos_set.add(proto.name)
                yield proto

    def com_protos(self) -> Generator[GolangProto, None, None]:
        protos_set = set()
        for group in self.get_router_groups():
            for proto in group.com_protos():
                if proto.name in protos_set:
                    continue
                protos_set.add(proto.name)
                yield proto

    def com_enums(self) -> Generator[GolangEnum, None, None]:
        enums_seen: Set[Type[enum.Enum]] = set()
        for proto in chain(self.protos(), self.com_protos()):
            for enum_cls in iter_enum_classes(proto.model_type):
                if enum_cls in enums_seen:
                    continue
                golang_enum = GolangEnum.from_enum(enum_cls)
                if golang_enum is None:
                    continue
                enums_seen.add(enum_cls)
                yield golang_enum
    

    def gen_views(self):
        view_dir: Path = self.writer.working_dir / self.writer.views_package / self.package
        ctx = {
            'writer': self.writer,
            'bp': self,
        }
        # engine
        with self.writer.write_file(self.writer.working_dir / self.writer.views_package / 'engine.go') as f:
            if f: 
                f.write(templates.render(LANG, 'engine.go', ctx, ''))

        # com_protos
        with self.writer.write_file(view_dir / self.com_proto_gen_path / 'protos.go', overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, 'protos.go', ctx, 'views/gen-protos'))

        # com_enums
        enums_path = view_dir / self.com_enum_gen_path / 'enums.go'
        with self.writer.write_file(enums_path, overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, 'enums.go', ctx, 'views/gen-enums'))
        self.writer.run_go_enum(enums_path)


        # view blueprint
        with self.writer.write_file(view_dir / 'gen_blueprint.go', overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, 'gen_blueprint.go', ctx, 'views'))
                

        # view routers
        for group in self.get_router_groups():
            self.gen_routers(group)


    def gen_routers(self, group: GolangRouterGroup):
        view_dir: Path = self.writer.working_dir / self.writer.views_package / self.package / group.package
        ctx = {
            'writer': self.writer,
            'bp': self,
            'router_group': group
        }
        for name, text in templates.iter_render(LANG, ctx, 'views/route'):
            overwrite = name.startswith('gen_')
            path = view_dir / name if group.branch else view_dir.parent / name
            with self.writer.write_file(path, overwrite=overwrite) as f:
                if f: f.write(text)


class GolangWriter(BaseWriter[GolangBlueprint]):
    gomodule: str
    gomodpath: str = None

    views_package: str
    provider_package: str
    GO_ENUM_ARGS: Tuple[str, ...] = (
        '--names',
        '--values',
        '--marshal',
        '--mustparse',
        '--nocase',
        '--output-suffix', '_gen',
    )

    _written_files: Set[str]
    _response_wrappers: Optional[List[ResponseWrapper]]
    
    _list_providers_cache: Optional[Set[str]] = None

    def __init__(
        self,         
        working_dir: str = '.', 
        *,
        module: Optional[str] = None,
        views_package: str = PackageName.VIEWS.value,
        provider_package: str = PackageName.PROVIDER.value,
        errors_package: str = PackageName.ERROR.value,
        **kwargs: Dict[str, Any],
    ):
        super().__init__(working_dir)

        gmods = self.read_gomodule(working_dir)
        if len(gmods) > 1 and not module:
            raise ModuleNotFoundError(f'[go]路径下存在多个module，需要使用module指定其一:{[k for k, _ in gmods]}')
        for gmod in gmods:
            mod, mod_dir = gmod
            if mod == 'command-line-arguments':
                logger.error(f'[x] gomodule: {module}')
                raise ModuleNotFoundError('[go]生成目录找不到gomodule，无法继续生成go代码')
            if not module or module == mod:
                module = mod
                self.gomodule = mod
                self.gomodpath = (module / Path(working_dir).absolute().relative_to(mod_dir)).as_posix()
                logger.info(f'[*] gomodule: {module}')
                break

        if self.gomodpath is None:
            raise ModuleNotFoundError(f'[go]生成目录找不到gomodule[{module}]，无法继续生成go代码')

        self.packages = GolangPackageLayout(
            module_import=self.gomodpath,
            views_package=views_package,
            provider_package=provider_package,
            errors_package=errors_package,
        )

        self.views_package = self.packages.views_package
        self.provider_package = self.packages.provider_package
        self.errors_package = self.packages.errors_package

        self._written_files = set()
        self._response_wrappers = None
    
    @property
    def views_imports(self) -> str:
        return self.packages.views_imports

    @property
    def provider_imports(self) -> str:
        return self.packages.provider_imports

    @property
    def errors_imports(self) -> str:
        return self.packages.errors_imports

    def list_providers(self) -> Set[str]:
        provs = self._list_providers_cache
        if provs is None:
            provs = {
                prov.name
                for bp in self.bps
                for group in bp.get_router_groups()
                for router in group.routers
                for prov in router.providers
            }
            self._list_providers_cache = provs
        return provs

    @staticmethod
    def read_gomodule(path: str) -> List[Tuple[str, str]]:
        p = subprocess.run(
            ['go', 'list', '-m', '-f', "{{.Path}} {{.Dir}}"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        return [line.split(' ', 2) for line in p.stdout.strip().splitlines()]

    @staticmethod
    def run_format(filepath: str):
        file_or_dir = str(Path(filepath).absolute())
        try:
            p = subprocess.run(
                ['gofmt', '-s', '-w', file_or_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            import sys
            print(f'[x] gofmt: \n{e.stderr.strip()}', file=sys.stderr)
            return e.stderr
        else:
            return p.stdout.strip()

    def run_go_enum(self, filepath: Union[str, Path], extra_args: Optional[List[str]] = None):
        exe = shutil.which('go-enum')
        if exe is None:
            logger.warning('[!] go-enum command not found, skip enum generation for %s', filepath)
            return

        file_path = Path(filepath).absolute()
        if not file_path.exists():
            logger.error('[x] go-enum target missing: %s', file_path)
            return

        args = list(extra_args or self.GO_ENUM_ARGS)
        cmd = [exe, *args, f'--file={file_path.name}']

        try:
            subprocess.run(
                cmd,
                cwd=file_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            output = exc.stderr.strip() or exc.stdout.strip()
            logger.error('[x] go-enum failed for %s: %s', file_path, output)
    
    def formatters(self, update: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        return self.packages.formatters(update)

    def error_vars(self) -> Generator[GolangErrorGroup, None, None]:
        for cls_name, cls in iter_error_models():

            err_pkg = pascal_to_snake_case(cls_name)
            err_imports = join_path_imports(self.errors_imports, err_pkg)
            err_dir = Path(self.working_dir / self.errors_package / err_pkg)
            errors = [field for _, field in iter_model_vars(cls) if isinstance(field, Error)]
            error_group = GolangErrorGroup(err_pkg, err_imports, err_dir, errors)
            yield error_group

    def response_wrappers(self, *prefixs: str) -> Generator[GolangResponseWrapper, None, None]:
        if self._response_wrappers is None:
            wrappers = set()
            for bp in self.bps:
                for group in bp.get_router_groups():
                    for router in group.routers:
                        wrapper: Optional[Type[ResponseWrapper]] = router.response_wrapper
                        wrappers.add(wrapper)
            self._response_wrappers = list(wrappers)

        for prefix in prefixs:
            for wrapper in self._response_wrappers:
                yield GolangResponseWrapper(
                    prefix=prefix,
                    response_wrapper=wrapper,
                )
    
    def gen(self):
        for bp in self.bps:
            bp.build()
            bp.gen_views()

        self.gen_errors()
        self.gen_providers()

        if len(self._written_files) > 0:
            for file in self._written_files:
                self.run_format(file)

    def gen_errors(self):
        for error_group in self.error_vars():
            for name, text in templates.iter_render(LANG, {
                'writer': self,
                'error_group': error_group
            }, 'errors/group'):
                overwrite = name.startswith('gen_')

                with self.write_file(error_group.gen_dir / name, overwrite=overwrite) as f:
                    if f: f.write(text)

        errors_dir: Path = self.working_dir / self.errors_package

        for name, text in templates.iter_render(LANG, {
            'writer': self,
        }, 'errors'):
            overwrite = name.startswith('gen_')

            with self.write_file(errors_dir / name, overwrite=overwrite) as f:
                if f: f.write(text)

    def gen_providers(self):
        prov_dir: Path = self.working_dir / self.views_package / self.provider_package

        for name, text in templates.iter_render(LANG, {
            'writer': self,
        }, 'provider'):
            overwrite = name.startswith('gen_')

            with self.write_file(prov_dir / name, overwrite=overwrite) as f:
                if f: f.write(text)

    @contextmanager
    def write_file(self, filepath: str | Path, overwrite: bool = False) -> Generator[Optional[IO], None, None]:
        filepath: str = str(filepath)
        wrote: bool = False
        with utils.ensure_filepath_open(filepath, 'w', overwrite=overwrite) as f:
            if f:
                wrote = True
            yield f
        
        if wrote:
            state: str = '[+] Written'
            d = Path(filepath)
            if d.is_file():
                d = d.parent
                self._written_files.add(str(d))
        else:
            state: str = '[.] Skipped'
        logger.info(f'{state}: {filepath}')
