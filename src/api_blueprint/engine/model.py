from typing import (
    Any, Dict, Tuple, Type, TypeVar, ItemsView, Optional,
    Generic, get_origin, get_args, List, DefaultDict, ForwardRef, 
    overload, Type, Union, Generator, Literal, Callable, ClassVar, TYPE_CHECKING,
    get_type_hints, Set, TypeAlias
)
from types import GenericAlias
from collections import defaultdict
import pydantic as pyd
from pydantic.fields import FieldInfo
from fastapi import params as fa_params
from fastapi.security import api_key as fa_apikey
from api_blueprint.engine.utils import inspect_getmembers, is_parametrized
import fastapi
import inspect
import enum
import zlib

if TYPE_CHECKING:
    from api_blueprint.engine.wrapper import ResponseWrapper
    from api_blueprint.engine.router import Router


AnyField = Union['Field', 'Model', Type['Model']]
AnyModel = Union['Model', Type['Model']]


__error_models__: Dict[str, Type['Model']] = {}
__name_models__: Dict[str, Type['Model']] = {}

class ModelMeta(type):
    def __new__(mcls, name, bases, namespace: Dict[str, Any]):
        model_is_ready = 'Model' in globals()

        fields: Dict[str, Any] = {}

        for k, v in namespace.items():
            if model_is_ready and isinstance(v, Field):
                setattr(v, "__key__", (name, k))
                fields[k] = v
            elif model_is_ready and isinstance(v, type) and isinstance(v, ModelMeta):
                fields[k] = v

        cls: Type['Model'] = super().__new__(mcls, name, bases, namespace)
        cls.__fields__ = fields

        if model_is_ready and any(isinstance(v, Error) for v in namespace.values()):
            __error_models__[name] = cls
        __name_models__[name] = cls
        return cls

    def __iter__(cls: Type['Model']):
        return iter(cls.__fields__)
    
    def __len__(cls: Type['Model']):
        return len(cls.__fields__)

    def __getitem__(cls: Type['Model'], key: str):
        if not isinstance(key, str) and getattr(cls, "__parameters__", ()):
            # item 可能是单个类型或元组，这里统一转成 tuple
            return GenericAlias(cls, key if isinstance(key, tuple) else (key,))
        return cls.__fields__[key]

    def keys(cls: Type['Model']):
        return cls.__fields__.keys()

    def items(cls: Type['Model']):
        return cls.__fields__.items()

    def values(cls: Type['Model']):
        return cls.__fields__.values()


class Model(metaclass=ModelMeta):
    __name__: str
    __type__: str = 'object'
    __auto__: bool = False # 子类继承
    __extra__: Dict[str, Any] = {}
    __fields__: Dict[str, Any] = {}

    @overload
    def __init__(
        self,
        *,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs: Dict[str, Any]):
        self.__extra__ = kwargs
        self.__name__ = self.__class__.__name__

    def __iter__(self):
        return iter(self.__fields__)
    
    def __len__(self):
        return len(self.__fields__)

    def __getitem__(self, key: str):
        return self.__fields__[key]

    def __bool__(self):
        return True


def create_model(name: str, data: Dict[str, Any], **kwargs) -> 'Model':
    namespace = data.copy()
    namespace['__name__'] = name
    namespace['__extra__'] = kwargs
    namespace['__type__'] = 'object'
    namespace['__auto__'] = True
    return type(name, (Model,), namespace)(**kwargs)


def iter_model_vars(model: AnyModel) -> ItemsView[str, Union['Field ', Model]]:
    cls = model
    if not isinstance(model, type):
        cls = model.__class__
    return {k: v for k, v in inspect_getmembers(cls) if not k.startswith('__')}.items()


def unwrap_errors(errors: List[Union[Type[Model], Model, 'Error']]) -> DefaultDict[int, List['Error']]:
    code_errs: DefaultDict[int, List['Error']] = defaultdict(list)
    for err in errors:
        if isinstance(err, Error):
            code_errs[err.code].append(err)
        elif isinstance(err, Model) or (isinstance(err, type) and issubclass(err, Model)):
            for name, field_err in iter_model_vars(err):
                if isinstance(field_err, Error):
                    code_errs[field_err.code].append(field_err)
    return code_errs


def iter_error_models() -> Generator[Tuple[str, Type[Model]], None, None]:
    global __error_models__
    for cls_name, cls in __error_models__.items():
        yield cls_name, cls


def unwrap_model_type(model: Union[Type[Model], Model, GenericAlias]) -> Type[Model]:
    if isinstance(model, type) or is_parametrized(model):
        model_type = model    
    elif getattr(model, '__orig_class__', None):
        model_type = model.__orig_class__
    elif isinstance(model, FieldWrappedModel):
        # FieldWrappedModel本身不重要，其内部的model才有用
        model_type = unwrap_model_type(model.__field_type__)
    else:
        model_type = model.__class__
    return model_type


class Proto:
    _name: str
    model_type: Model

    def __init__(
        self, 
        name: str, 
        model: Union[Type[Model], Model], 
    ):
        self._name = name
        self.model_type = unwrap_model_type(model)

    @property
    def name(self) -> str: 
        return self._name        


P = TypeVar("P", bound=Proto)


def iter_field_model_type(
    field: AnyField,
) -> Generator[Type[Model], None, None]:
    if isinstance(field, AnonKV):
        field = field.get_obj()

    if orig := get_origin(field):
        yield from iter_field_model_type(field())
        for arg in get_args(field):
            yield from iter_field_model_type(arg)
    elif isinstance(field, Array):
        elem = field.elem_type()
        yield from iter_field_model_type(elem)
    elif isinstance(field, Map):
        val = field.value_type()
        yield from iter_field_model_type(val)
    else:
        if isinstance(field, Model):
            model_type = field.__class__
        elif isinstance(field, type) and issubclass(field, Model):
            if field is FieldWrappedModel:
                model_type = field.__field_type__
            model_type = field
        else:
            return
        
        for name, sub_field in iter_model_vars(model_type):
            yield from iter_field_model_type(sub_field)
        yield model_type


class Field:
    __name__: str
    __extra__: Dict[str, Any] = {}
    __type__: str = ''
    __auto__: bool = False
    __key__: Tuple[str, str] = None

    @overload
    def __init__(
        self,
        *,
        default: Any = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        self.__extra__ = kwargs

    def __bool__(self):
        return True



T = TypeVar('T')


class Object(Field):                
    __type__ = 'object'

    @overload
    def __init__(
        self,
        *,
        default: Any = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Null(Field):                
    __type__ = 'null'

    @overload
    def __init__(
        self,
        *,
        default: Any = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class String(Field):                
    __type__ = 'string'

    @overload
    def __init__(
        self,
        *,
        default: str = ...,
        min_length: int | None = ...,
        max_length: int | None = ...,
        regex: str | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: str = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Int(Field):
    __type__ = 'int'

    @overload
    def __init__(
        self,
        *,
        default: int = ...,
        gt: float | None = ...,
        ge: float | None = ...,
        lt: float | None = ...,
        le: float | None = ...,
        multiple_of: float | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: int = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Int64(Int):   __type__ = 'int64'
class Int32(Int):   __type__ = 'int32'
class Int16(Int):   __type__ = 'int16'
class Int8(Int):    __type__ = 'int8'


class Uint(Int):    __type__ = 'uint'
class Uint64(Int):  __type__ = 'uint64'
class Uint32(Int):  __type__ = 'uint32'
class Uint16(Int):  __type__ = 'uint16'
class Uint8(Int):   __type__ = 'uint8'


class Float(Field):
    __type__ = 'float'

    @overload
    def __init__(
        self,
        *,
        default: float = ...,
        gt: float | None = ...,
        ge: float | None = ...,
        lt: float | None = ...,
        le: float | None = ...,
        multiple_of: float | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: float = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Float64(Field):   __type__ = 'float64'
class Float32(Field):   __type__ = 'float32'


class Bool(Field):
    __type__ = "boolean"

    @overload
    def __init__(
        self,
        *,
        default: bool = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: bool = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Byte(Field):
    __type__ = "byte"

    @overload
    def __init__(
        self,
        *,
        default: bool = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: bool = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Enum(Field, Generic[T]):
    __type__ = "enum"

    @overload
    def __init__(
        self,
        *,
        default: list[T] = ...,
        min_items: int | None = ...,
        max_items: int | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: list[T] = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def enum_type(self) -> Type[enum.Enum]:
        args = get_args(self.__orig_class__)
        t = args[0] if args else Any
        if isinstance(t, ForwardRef):
            t = get_forward_ref_type(t)
        return t

    def enum_base_type(self) -> Optional[Type]:
        enum_type = self.enum_type()
        members = list(enum_type)
        if not members:
            raise Exception('没有提供任何枚举值，无法推断其基础类型')
        
        types = [type(m.value) for m in members]
        for cond in types[0].mro():
            if all(issubclass(t, cond) for t in types):
                return cond
        raise object



def iter_enum_classes(value: Any) -> Generator[Type[enum.Enum], None, None]:
    yield from _iter_enum_classes(value, set())


def _iter_enum_classes(value: Any, visited_models: Set[Type[Model]]):
    if value is None:
        return

    if isinstance(value, ForwardRef):
        resolved = get_forward_ref_type(value)
        if resolved:
            yield from _iter_enum_classes(resolved, visited_models)
        return

    if isinstance(value, enum.EnumMeta):
        yield value
        return

    if isinstance(value, enum.Enum):
        yield value.__class__
        return

    if isinstance(value, Enum):
        enum_cls = value.enum_type()
        if isinstance(enum_cls, type) and issubclass(enum_cls, enum.Enum):
            yield enum_cls
        return

    if isinstance(value, Array):
        yield from _iter_enum_classes(value.elem_type(), visited_models)
        return

    if isinstance(value, Map):
        yield from _iter_enum_classes(value.key_type(), visited_models)
        yield from _iter_enum_classes(value.value_type(), visited_models)
        return

    if isinstance(value, AnonKV):
        obj = value.get_obj()
        if obj:
            yield from _iter_enum_classes(obj, visited_models)
        return

    if isinstance(value, FieldWrappedModel):
        yield from _iter_enum_classes(value.__field_type__, visited_models)
        return

    if isinstance(value, Model):
        model_cls = value if isinstance(value, type) else value.__class__
        if model_cls in visited_models:
            return
        visited_models.add(model_cls)
        for _, sub in iter_model_vars(model_cls):
            yield from _iter_enum_classes(sub, visited_models)
        return

    if isinstance(value, type):
        try:
            if issubclass(value, Model):
                if value in visited_models:
                    return
                visited_models.add(value)
                for _, sub in iter_model_vars(value):
                    yield from _iter_enum_classes(sub, visited_models)
                return
        except TypeError:
            pass

        try:
            if issubclass(value, enum.Enum):
                yield value
                return
        except TypeError:
            pass

        try:
            if issubclass(value, Field):
                instance = value()
                yield from _iter_enum_classes(instance, visited_models)
                return
        except TypeError:
            pass

    origin = get_origin(value)
    if origin and isinstance(origin, type):
        try:
            if issubclass(origin, Field):
                instance = value()
                yield from _iter_enum_classes(instance, visited_models)
                return
        except TypeError:
            pass

        try:
            if issubclass(origin, Model):
                if origin in visited_models:
                    return
                visited_models.add(origin)
                for _, sub in iter_model_vars(origin):
                    yield from _iter_enum_classes(sub, visited_models)
                return
        except TypeError:
            pass



class AnonKV(Field):
    __type__ = 'anonkv'
    origin: Optional[GenericAlias]
    kvs: Dict[str, Any]
    _obj: Optional[Model] = None

    def __init__(self, origin: Optional[GenericAlias] = None, **kvs):
        self.origin = origin
        self.kvs = kvs

    def __call__(self, **kwds):
        self.__extra__ = kwds
        return self

    def get_obj(self):
        return self._obj

    def build(self, router: Optional['Router'], field_name: Optional[str]) -> AnyField:
        if all([field_name, router]):
            name = f'ANON_{router.name}_{field_name}'
        else:
            short_id = zlib.crc32(f'{" ".join(sorted(self.kvs.keys()))}'.encode('utf8')) & 0xFFFFFFFF
            name = f'ANON_{short_id:08x}'
        model = create_model(
            name,
            self.kvs,
        ).__class__
        obj = model
        if self.origin:
            obj = self.origin[obj]()
        if isinstance(obj, ForwardRef):
            obj = get_forward_ref_type(obj)
        self._obj = obj
        return obj


def ArrayKV(**kwargs):
    return AnonKV(Array, **kwargs)

def KV(**kwargs):
    return AnonKV(None, **kwargs)


class Array(Field, Generic[T]):     
    __type__ = 'array'

    @overload
    def __init__(
        self,
        *,
        default: list[T] = ...,
        min_items: int | None = ...,
        max_items: int | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: list[T] = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def elem_type(self) -> Any:
        args = get_args(self.__orig_class__)
        t = args[0] if args else Any
        if isinstance(t, ForwardRef):
            t = get_forward_ref_type(t)
        return t



K = TypeVar('K')
V = TypeVar('V')

class Map(Field, Generic[K, V]):
    __name__: str = 'Map'
    __type__ = 'map'

    @overload
    def __init__(
        self,
        *,
        default: Dict[K, V] = ...,
        min_properties: int | None = ...,
        max_properties: int | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Dict[K, V] = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def key_type(self) -> Any:
        args = get_args(self.__orig_class__)
        t = args[0] if args else Any
        if isinstance(t, ForwardRef):
            t = get_forward_ref_type(t)
        return t

    def value_type(self) -> Any:
        args = get_args(self.__orig_class__)
        t = args[1] if len(args) > 1 else Any
        if isinstance(t, ForwardRef):
            t = get_forward_ref_type(t)
        return t



class Error(Field):
    code: int
    message: str

    __type__ = 'error'

    @overload
    def __init__(
        self,
        code: int,
        message: str,
        *,
        default: Any = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, code: int, message: str, **kwargs):
        super().__init__(**kwargs)
        self.code = code
        self.message = message


class Header(Field):
    __type__ = 'header'

    @overload
    def __init__(
        self,
        *,
        default: Any = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: Any = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class APIKeyHeader(Field):
    __type__ = 'api_key_header'

    @overload
    def __init__(
        self,
        *,
        name: Any = ...,
        scheme_name: str = None,
        description: str | None = ...,
        auto_error: bool = False,
    ) -> None: ...
    def __init__(self, **kwargs):
        auto_error = kwargs.pop('auto_error', False)
        kwargs['auto_error'] = auto_error
        super().__init__(**kwargs)

    def __call__(self, *args, **kwds):
        scheme_name = kwds.pop('scheme_name', None)
        if scheme_name is None:
            cls_name, scheme_name = self.__key__
            kwds['scheme_name'] = f'{cls_name}: {scheme_name}'
        return fa_apikey.APIKeyHeader(*args, **kwds)



class FieldWrappedModel(Model):
    __name_val__: str = 'Field'
    __field_type__: Type[Field]
    __auto__: bool = True # 只用于内部，属于自动生成model

    def __init__(self, field_type: Field, **kwargs: Dict[str, Any]):
        super().__init__(**kwargs)
        self.__field_type__ = field_type

    @property
    def __name__(self) -> str:
        return self.__name_val__

    @__name__.setter
    def __name__(self, name: str) -> str:
        self.__name_val__ = name

    def __call__(self, *args, **kwds):
        self.__extra__ = kwds
        return self.__field_type__


def create_field_wrapped_model(name: str, field: Field) -> FieldWrappedModel:
    model = FieldWrappedModel(field)
    model.__name__ = name
    model.__auto__ = True
    return model


class HeaderModel(Model):
    __type__ = 'header_model'


class NoneHeader(HeaderModel):  pass


__pydantic_model_cache__: Dict[Union[Type[Model], Map], Any] = {}


def model_to_pydantic(
    cls: Union[Type[Model], Map], 
    field_factory: Union[Callable[..., FieldInfo], Callable[..., fa_params.Header]] = pyd.Field,
    *,
    name: Optional[str] = None,
    router: 'Router' = None,
) -> Type[pyd.BaseModel]:
    global __pydantic_model_cache__

    annotations: Dict[str, Any] = {}
    namespace: Dict[str, Any] = {}
    cls_name = cls.__name__
    pyd_cls = __pydantic_model_cache__.get(cls, None)
    if pyd_cls:
        return pyd_cls

    for name, attr in iter_model_vars(cls):
        if isinstance(attr, Field):
            py_type, info = resolve_field(attr, field_factory, name=name, router=router)
        elif isinstance(attr, Model):
            nested = model_to_pydantic(attr.__class__, name=name, router=router)
            py_type = nested
            description = attr.__extra__.get('description', '')
            copy_extra = {k: v for k, v in attr.__extra__.items() if k != 'description'}
            copy_extra['description'] = f'[{attr.__class__.__name__}] {description}'
            info = field_factory(**copy_extra)
        else:
            continue

        annotations[name] = py_type
        namespace[name] = info

    wrapper: Optional[ResponseWrapper] = getattr(cls, '__wrapper__', None)
    if wrapper:
        annotations["Config"] = ClassVar[type]
        Config = type("Config", (), {
            "json_schema_extra": wrapper.json_schema_extra()
        })
        namespace['Config'] = Config

    namespace['__annotations__'] = annotations
    namespace['__name__'] = cls.__name__
    namespace['__module__'] = "api_model"
    pyd_cls = type(cls_name, (pyd.BaseModel,), namespace)
    __pydantic_model_cache__[cls] = pyd_cls
    return pyd_cls



def resolve_field(
    field: Union[Field, Type[Field]],
    field_factory: Union[Callable[..., FieldInfo], Callable[..., fa_params.Header]] = pyd.Field,
    *,
    name: Optional[str] = None,
    router: 'Router' = None,
) -> Tuple[Any, FieldInfo]:
    if is_parametrized(field):
        # 参数化的泛型类型，需要实例化后再解析
        field = field()

    is_type = isinstance(field, type)
    ismatch: Callable[[Union[Field, Type[Field]], Type], bool] = isinstance if not is_type else issubclass
    description: Optional[str] = getattr(field, "__extra__", {}).get('description', '')

    if ismatch(field, String):
        py_type = str
    elif ismatch(
        field, (Int, Int64, Int32, Int16, Int8, 
                Uint, Uint8, Uint16, Uint32, Uint64)):
        py_type = int
    elif ismatch(field, (Float, Float32, Float64)):
        py_type = float
    elif ismatch(field, Bool):
        py_type = bool
    elif ismatch(field, enum.Enum):
        py_type = field
    elif ismatch(field, Enum):
        py_type = field.enum_base_type()
    elif ismatch(field, Array):
        arr: Array = field
        elem = arr.elem_type()
        if isinstance(elem, type) and issubclass(elem, Model):
            elem = model_to_pydantic(elem, name=name, router=router)
            description = f'[{elem.__name__}] {description}'
        if isinstance(elem, type) and issubclass(elem, Field):
            elem, _ = resolve_field(elem, name=name, router=router)
        elif orig_elem := get_origin(elem):
            if isinstance(orig_elem, type) and issubclass(orig_elem, Field):
                elem, _ = resolve_field(elem(), name=name, router=router)
        py_type = List[elem]
    elif ismatch(field, Map):
        key = field.key_type()
        val = field.value_type()
        if isinstance(key, type) and issubclass(key, Model):
            key = model_to_pydantic(key, name=name, router=router)

        if (isinstance(key, type) and issubclass(key, Field)) or is_parametrized(key):
            key, _ = resolve_field(key, name=name, router=router)
        
        if isinstance(val, type) and issubclass(val, Model):
            val = model_to_pydantic(val, name=name, router=router)
            description = f'[{key.__name__}: {val.__name__}] {description}'
        if isinstance(val, type) and issubclass(val, Field) or is_parametrized(key):
            val, _ = resolve_field(val, name=name, router=router)
        
        if orig_val := get_origin(val):
            if isinstance(orig_val, type) and issubclass(orig_val, Field):
                val, _ = resolve_field(val(), name=name, router=router)

        py_type = Dict[key, val]
    elif ismatch(field, AnonKV):
        obj = field.build(router, name)
        if isinstance(obj, type):
            py_type = model_to_pydantic(obj, name=name, router=router)
        else:
            py_type, _ = resolve_field(obj, name=name, router=router)
    elif ismatch(field, Error):
        py_type = Any
    elif ismatch(field, Null):
        py_type = Any
    elif ismatch(field, Header):
        py_type = str
        field_factory = fastapi.Header
    elif ismatch(field, APIKeyHeader):
        py_type = str
        field_factory = lambda *args, **kwargs:fastapi.Security(field(*args, **kwargs))
    else:
        py_type = Any

    if is_type:
        info = None
    else:
        # 追加model名称: [{model_name}] {description} 
        copy_extra = {k: v for k, v in getattr(field, "__extra__", {}).items() if k != 'description'}
        copy_extra['description'] = description
        info = field_factory(
            **copy_extra
        )
        if (default := copy_extra.get('default', ...)) is not ...:
            if py_type is not Any:
                py_type = Optional[py_type]

    return py_type, info


def get_forward_ref_type(ref: ForwardRef) -> Type[Model]:
    return __name_models__.get(ref.__forward_arg__)


BASIC_FIELD_TYPES = frozenset([
    v
    for v in locals().values() if isinstance(v, type) and issubclass(v, Field)
])

# BASIC_FIELD_TYPE = frozenset([
#     String, Int, Int64, Int32, Int16, Int8, Uint, Uint8, Uint16, Uint32, Uint64,
#     Float, Float32, Float64, Bool, Array, Map, AnonKV, Error, Null, Header, APIKeyHeader
# ])