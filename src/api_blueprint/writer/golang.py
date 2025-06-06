from api_blueprint.writer import BaseBlueprint, BaseWriter, utils
from typing import (
    List, Optional, Dict, Any, Set, Generator, Union, Literal, TypeVar,
    Generic, Tuple, Type, IO
)
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import (
    Field, Model, Array, Null, Map, MapModel, Error,
    create_model, model_to_pydantic, iter_model_vars,
    Proto, iter_field_model_type, AnyModel, iter_error_models,
)
from api_blueprint.engine.wrapper import ResponseWrapper
from api_blueprint.engine.router import Router
from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.utils import (
    snake_to_pascal_case, pascal_to_snake_case, inc_to_letters, join_path_imports,
)
from api_blueprint.writer import templates
from api_blueprint.writer.utils import SafeFmtter
from fastapi.responses import Response
import logging
from pydantic.fields import FieldInfo
import subprocess
from enum import Enum


logging.basicConfig(
    level=logging.INFO,            
    format="%(message)s",
)


logger = logging.getLogger('GolangWriter')
logger.setLevel(logging.INFO)


class PackageName(str, Enum):
    COM_PROTOS = 'protos'
    PROVIDER   = 'provider'
    ERROR      = 'errors'
    VIEWS      = 'views'


PROTO_STRUCT_TYPE = Literal['struct', 'generic', 'alias']



class GolangProtoHelper:
    parent: str

    @property
    def package(self) -> str:
        if not self.parent:
            return ''
        return f'{{{self.parent}_package}}'

    def format_package(self, **kwargs) -> str:
        return self.package.format(**kwargs)

    def format_package_with_dot(self, **kwargs) -> str:
        if not self.parent:
            return ''
        return f'{{{self.parent}_package$}}'.format(**kwargs)

    @property
    def imports(self) -> str:
        if not self.parent:
            return ''
        return f'{{{self.parent}_imports}}'

    def format_imports(self, **kwargs) -> str:
        return self.imports.format(**kwargs)


@dataclass
class GolangProtoGeneric(GolangProtoHelper):
    parent: str
    name: str
    types: List[Union['GolangProto', str]]


@dataclass
class GolangProtoAlias(GolangProtoHelper):
    name: str
    parent: Optional[str] = None
    proto: Optional['GolangProto'] = None
    new_type: bool = False
    

class GolangMapModel(MapModel):
    @property
    def __name__(self) -> str:
        return GolangProto.get_field_type(self.__map_type__)

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
        if len(fields) > 0:
            struct_type = 'struct'
        else:
            struct_type = 'alias'
            alias = GolangProtoAlias(
                name='any',
            )

        self._proto = GolangProto(
            name=self.prefix,
            model=self.response_wrapper,
            struct_type=struct_type,
            alias=alias,
        )
        return self._proto
 
    @property
    def proto_name(self) -> str:
        return f'{self.prefix}_{self.response_wrapper.__name__}'

    @property
    def proto_type(self) -> PROTO_STRUCT_TYPE:
        return self.proto.struct_type

    def proto_fields(self) -> List[Dict[str, Any]]:
        return self.proto.fields()

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
    generic: Optional[GolangProtoGeneric]
    alias: Optional[GolangProtoAlias]

    def __init__(
        self, 
        name: str, 
        model: AnyModel, 
        struct_type: PROTO_STRUCT_TYPE = 'struct',
        *,
        generic: Optional[GolangProtoGeneric] = None,
        alias: Optional[GolangProtoAlias] = None,
    ):
        super().__init__(name, model)
        self.struct_type = struct_type
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
        if ref_model.__auto__:
            proto = GolangProto(
                name,
                ref_model,
                **kwargs,
            )
        else:
            # GolangMapModel => map[?]?
            alias_is_com = not isinstance(ref_model, GolangMapModel)
            alias_proto = GolangProto.from_model(ref_model, **kwargs)
            alias_parent = None
            if alias_is_com:
                alias_parent = PackageName.COM_PROTOS.value
            proto = GolangProto(
                name,
                ref_model,
                'alias',
                alias=GolangProtoAlias(
                    parent=alias_parent,
                    name=alias_proto.name,
                    proto=alias_proto,
                ),
                **kwargs,
            )
        return proto

    @staticmethod
    def get_field_type(field: Union[Field, Model], is_sub: bool = False) -> str:
        def array():
            arr: Array = field
            elem = arr.elem_type()
            if issubclass(elem, Field):
                return f'[]{do_sub(elem)}'
            elif issubclass(elem, Model):
                return f'[]*{do_sub(elem)}'
            return '[]any'
        
        def string():   return 'string'

        def int():      return 'int'
        def int64():    return 'int64'
        def int32():    return 'int32'
        def int16():    return 'int16'
        def int8():     return 'int8'
        def uint():     return 'uint'
        def uint64():   return 'uint64'
        def uint32():   return 'uint32'
        def uint16():   return 'uint16'
        def uint8():    return 'uint8'

        def float():    return 'float64'
        def float64():  return 'float64'
        def float32():  return 'float32'

        def boolean():  return 'bool'
        def error():    return 'error'    
        def null():     return 'nil'

        def object():
            cls = field if isinstance(field, type) else field.__class__
            return f'{"*" if not is_sub else ""}{{protos_package$}}{cls.__name__}'

        def map():
            map: Map = field
            key = map.key_type()
            value = map.value_type()
            if issubclass(value, Field):
                return f'map[{do_sub(key)}]{do_sub(value)}'
            elif issubclass(value, Model):
                return f'map[{do_sub(key)}]*{do_sub(value)}'
            return f'map[string]any'

        def do_sub(sub_field: Union[Field, Model]):
            return GolangProto.get_field_type(sub_field, True)

        getter = {
            'array': array,
            'int': int,
            'int64': int64,
            'int32': int32,
            'int16': int16,
            'int8': int8,
            'uint': uint,
            'uint64': uint64,
            'uint32': uint32,
            'uint16': uint16,
            'uint8': uint8,
            'float': float,
            'float64': float64,
            'float32': float32,
            'boolean': boolean,
            'error': error,
            'string': string,
            'null': null,
            'map': map,
            'object': object,
        }.get(field.__type__, lambda: 'any')
        return getter()

    @staticmethod
    def get_binding_tag(field: FieldInfo) -> str:
        parts = []
        if field.is_required():
            parts.append("required")

        metadata = field.metadata
        for meta in metadata:
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

        return ",".join(parts)

    @staticmethod
    def get_field_tags(name: str, field: Union[Field, Model], field_info: FieldInfo) -> str:
        alias = field.__extra__.get('alias', None)
        field_name = alias or name
        normal_val = field_name if not field.__extra__.get('omitempty', False) else f'{name},omitempty'
        tags: List[Tuple[str, str]] = [
            ('json', normal_val),
            ('xml', normal_val),
            ('form', normal_val),
        ]
        binding = GolangProto.get_binding_tag(field_info)
        if binding:
            tags.append(
                ('binding', binding)
            )
        
        return ' '.join([
            f'{tag}:"{value}"'
            for tag, value in tags
        ])

    def generic_types(self) -> Dict[TypeVar, str]:
        generic_types: Dict[TypeVar, str] = {}
        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue
            if field is None:
                field = Null()
            
            if type(field) is Field:
                anno = self.model_type.__annotations__.get(name, None)
                if isinstance(anno, TypeVar):
                    c = inc_to_letters(len(generic_types), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                    generic_types[anno] = c
        return generic_types

    def fields(self) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        pydmodel = model_to_pydantic(self.model_type)
        
        generic_types = self.generic_types()

        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue
            pydfield = pydmodel.model_fields[name]
            if field is None:
                field = Null()
            
            typ: Optional[str] = None
            if type(field) is Field:
                anno = self.model_type.__annotations__.get(name, None)
                if isinstance(anno, TypeVar):
                    typ = f'*{generic_types[anno]}'
            
            alias = field.__extra__.get('alias', None)

            if typ is None:
                typ = self.get_field_type(field)
            
            field_name = alias or name
            fields.append({
                'name': snake_to_pascal_case(name),
                'field': field_name, 
                'type': SafeFmtter(typ),
                'tags': self.get_field_tags(name, field, pydfield)
            })
        return fields

    def generics(self) -> Generator[str, None, None]:
        for proto in self.generic.types:
            if isinstance(proto, str):
                yield proto
            else:
                yield proto.name

    def com_protos(self) -> Generator['GolangProto', None, None]:
        for model_type in iter_field_model_type(self.model_type):
            if model_type is self.model_type:
                continue
            yield GolangProto.from_model(model_type)
            
        if not model_type.__auto__:
            yield GolangProto.from_model(model_type)


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
            media_type_mapping[r.media_type],
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

        def ensure_model(model_or_map: Union[AnyModel, MapModel]) -> Union[GolangMapModel, AnyModel]:
            if isinstance(model_or_map, MapModel) or (
                isinstance(model_or_map, type) and MapModel is model_or_map):
                return GolangMapModel(model_or_map.__map_type__)
            return model_or_map
        
        if self.router.req_query:
            req_query_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_query), f'{self.req_type}_QUERY')
            yield req_query_proto

        if self.router.req_form:
            req_form_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_form), f'{self.req_type}_FORM')
            yield req_form_proto

        if self.router.req_json:
            req_json_proto = GolangProto.from_model_ref(
                ensure_model(self.router.req_json), f'{self.req_type}_JSON')
            yield req_json_proto
        
        # REQ
        req_proto = GolangProto(
            self.req_type,
            create_model(self.req_type, {
                'Q': self.router.req_query or Null(),
                'F': self.router.req_form or Null(),
                'J': self.router.req_json or Null(),
            }),
            'generic',
            generic=GolangProtoGeneric('provider', 'REQ', [
                req_query_proto or 'any',
                req_form_proto or 'any',
                req_json_proto or 'any',
            ]),
        )
        yield req_proto
        
        # RSP
        rsp_json_proto = None
        if self.router.rsp_model:
            rsp_json_proto = GolangProto.from_model_ref(
                ensure_model(self.router.rsp_model), f'{self.rsp_type}_JSON')
            yield rsp_json_proto

        rsp_proto = GolangProto(
            self.rsp_type,
            self.router.rsp_model,
            'alias',
            alias=GolangProtoAlias(
                name=rsp_json_proto.name if rsp_json_proto else 'any',
                proto=rsp_json_proto,
            ),
        )
        yield rsp_proto

        # CTX
        ctx_proto = GolangProto(
            self.ctx_type,
            create_model(self.req_type, {
                'Q': self.router.req_query or Null(),
                'F': self.router.req_form or Null(),
                'J': self.router.req_json or Null(),
                'P': self.router.rsp_model or Null(),
            }),
            'generic',
            generic=GolangProtoGeneric('provider', 'Context', [
                req_query_proto or 'any',
                req_form_proto or 'any',
                req_json_proto or 'any',
                rsp_json_proto or 'any',
            ])
        )
        yield ctx_proto


    def com_protos(self) -> Generator[GolangProto, None, None]:
        if self.router.req_query:
            yield from GolangProto.from_model(
                self.router.req_query).com_protos()

        if self.router.req_form:
            yield from GolangProto.from_model(
                self.router.req_form).com_protos()

        if self.router.req_json:
            yield from GolangProto.from_model(
                self.router.req_json).com_protos()

        if self.router.rsp_model:
            yield from GolangProto.from_model(
                self.router.rsp_model).com_protos()


LANG: str = 'golang'

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
    def com_proto_imports(self) -> str:
        return join_path_imports(self.imports, self.com_proto_package)

    def formatters(self, update: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        fmts = self.writer.formatters()
        fmts.update({
            'protos_package': self.com_proto_package,
            'protos_imports': self.com_proto_imports,
        })
        pkg_with_dot_key = { k + '$': v + '.' for k, v in fmts.items() if k.endswith('_package') }
        fmts.update(pkg_with_dot_key)
        if update:
            fmts.update(update)
        return fmts
 

    def com_protos(self) -> Generator[GolangProto, None, None]:
        protos_set = set()
        for group in self.get_router_groups():
            for proto in group.com_protos():
                if proto.name in protos_set:
                    continue
                protos_set.add(proto.name)
                yield proto
    

    def gen_views(self):
        view_dir: Path = self.writer.working_dir / self.writer.views_package / self.package

        # engine
        with self.writer.write_file(self.writer.working_dir / self.writer.views_package / 'engine.go') as f:
            if f: 
                f.write(templates.render(LANG, 'engine.go', {
                    'writer': self.writer,
                    'bp': self,
                }, ''))

        # com_protos
        with self.writer.write_file(view_dir / self.com_proto_package / 'gen_protos.go', overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, 'gen_protos.go', {
                    'writer': self.writer,
                    'bp': self,
                }, 'views/protos'))

        # view blueprint
        with self.writer.write_file(view_dir / 'gen_blueprint.go', overwrite=True) as f:
            if f:
                f.write(templates.render(LANG, 'gen_blueprint.go', {
                    'writer': self.writer,
                    'bp': self,
                }, 'views'))
                

        # view routers
        for group in self.get_router_groups():
            self.gen_routers(group)

    
    def gen_routers(self, group: GolangRouterGroup):
        view_dir: Path = self.writer.working_dir / self.writer.views_package / self.package / group.package
        
        for name, text in templates.iter_render(LANG, {
            'writer': self.writer,
            'bp': self,
            'router_group': group
        }, 'views/route'):
            overwrite = name.startswith('gen_')
            path = view_dir / name if group.branch else view_dir.parent / name
            with self.writer.write_file(path, overwrite=overwrite) as f:
                if f: f.write(text)


class GolangWriter(BaseWriter[GolangBlueprint]):
    gomodule: str
    views_package: str
    provider_package: str

    _written_files: Set[str]
    _response_wrappers: Optional[List[ResponseWrapper]]
    
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

        if module is None:
            module = self.read_gomodule(working_dir)
            if module == 'command-line-arguments':
                logger.error(f'[x] gomodule: {module}')
                raise ModuleNotFoundError('[go]生成目录找不到gomodule，无法继续生成go代码')
            logger.info(f'[*] gomodule: {module}')

        self.gomodule = module

        self.views_package = views_package
        self.provider_package = provider_package
        self.errors_package = errors_package

        self._written_files = set()
        self._response_wrappers = None
    
    @property
    def views_imports(self) -> str:
        return join_path_imports(self.gomodule, self.views_package)

    @property
    def provider_imports(self) -> str:
        return join_path_imports(self.views_imports, self.provider_package)

    @property
    def errors_imports(self) -> str:
        return join_path_imports(self.gomodule, self.errors_package)

    @staticmethod
    def read_gomodule(path: str) -> str:
        p = subprocess.run(
            ['go', 'list', '-m'],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        return p.stdout.strip()

    @staticmethod
    def run_format(filepath: str):
        file_or_dir = Path(filepath).absolute()
        p = subprocess.run(
            ['gofmt', '-s', '-w', file_or_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        return p.stdout.strip()
    
    def formatters(self, update: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        fmts = {
            'views_package': self.views_package,
            'views_imports': self.views_imports,
            'provider_package': self.provider_package,
            'provider_imports': self.provider_imports,
            'errors_package': self.errors_package,
            'errors_imports': self.errors_imports,
        }
        pkg_with_dot_key = { k + '$': v + '.' for k, v in fmts.items() if k.endswith('_package') }
        fmts.update(pkg_with_dot_key)
        if update:
            fmts.update(update)
        return fmts

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
        written: bool = False
        with utils.ensure_filepath_open(filepath, 'w', overwrite=overwrite) as f:
            if f:
                written = True
            yield f
        
        if written:
            state: str = '[+]'
            d = Path(filepath)
            if d.is_file():
                d = d.parent
                self._written_files.add(str(d))
        else:
            state: str = '[.]'
        logger.info(f'{state} Written: {filepath}')
