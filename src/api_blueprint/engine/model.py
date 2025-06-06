from typing import (
    Any, Dict, Tuple, Type, TypeVar, ItemsView, Optional,
    Generic, get_origin, get_args, List, DefaultDict, 
    overload, Type, Union, Generator, Literal, Callable, ClassVar, TYPE_CHECKING
)
from collections import defaultdict
import pydantic as pyd
from pydantic.fields import FieldInfo
from fastapi import params as fa_params
import fastapi
from fastapi.security import api_key as fa_apikey
import inspect

if TYPE_CHECKING:
    from api_blueprint.engine.wrapper import ResponseWrapper


AnyField = Union['Field', 'Model', Type['Model']]
AnyModel = Union['Model', Type['Model']]


__error_models__: Dict[str, Type['Model']] = {}

class Model:
    __name__: str
    __type__: str = 'object'
    __auto__: bool = False # 子类继承
    __extra__: Dict[str, Any] = {}

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

    def __init_subclass__(cls):
        exist_err: bool = False
        for k, v in iter_model_vars(cls):
            if isinstance(v, Field):
                v.__key__ = (cls.__name__, k)
            if isinstance(v, Error):
                exist_err = True

        super().__init_subclass__()

        if exist_err:
            __error_models__[cls.__name__] = cls


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
    return {k: v for k, v in inspect.getmembers(cls) if not k.startswith('__')}.items()


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


class Proto:
    _name: str
    model_type: Model

    def __init__(
        self, 
        name: str, 
        model: Union[Type[Model], Model], 
    ):
        self._name = name
        self.model_type = model if isinstance(model, type) else model.__class__

    @property
    def name(self) -> str: 
        return self._name        


P = TypeVar("P", bound=Proto)


def iter_field_model_type(
    field: AnyField,
) -> Generator[Type[Model], None, None]:
    if isinstance(field, Array):
        elem = field.elem_type()
        yield from iter_field_model_type(elem)
    else:
        if isinstance(field, Model):
            model_type = field.__class__
        elif isinstance(field, type) and issubclass(field, Model):
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
        return args[0] if args else Any


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
        return args[0] if args else Any

    def value_type(self) -> Any:
        args = get_args(self.__orig_class__)
        return args[1] if len(args) > 1 else Any



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



class MapModel(Model):
    __name_val__: str = 'Map'
    __map_type__: Map

    def __init__(self, map_type: Map, **kwargs: Dict[str, Any]):
        super().__init__(**kwargs)
        self.__map_type__ = map_type

    @property
    def __name__(self) -> str:
        return self.__name_val__

    @__name__.setter
    def __name__(self, name: str) -> str:
        self.__name_val__ = name

    def __call__(self, *args, **kwds):
        self.__extra__ = kwds
        return self.__map_type__


def create_map_model(name: str, map: Map) -> MapModel:
    model = MapModel(map)
    model.__name__ = name
    return model


class HeaderModel(Model):
    __type__ = 'header_model'


class NoneHeader(HeaderModel):  pass


__pydantic_model_cache__: Dict[str, Any] = {}


def model_to_pydantic(
    cls: Union[Type[Model], Map], 
    field_factory: Union[Callable[..., FieldInfo], Callable[..., fa_params.Header]] = pyd.Field,
) -> Type[pyd.BaseModel]:
    global __pydantic_model_cache__

    annotations: Dict[str, Any] = {}
    namespace: Dict[str, Any] = {}
    cls_name = cls.__name__
    pyd_cls = __pydantic_model_cache__.get(cls_name, None)
    if pyd_cls:
        return pyd_cls

    for name, attr in iter_model_vars(cls):
        if isinstance(attr, Field):
            py_type, info = resolve_field(attr, field_factory)
        elif isinstance(attr, Model):
            nested = model_to_pydantic(attr.__class__)
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
    __pydantic_model_cache__[cls_name] = pyd_cls
    return pyd_cls



def resolve_field(
    field: Union[Field, Type[Field]],
    field_factory: Union[Callable[..., FieldInfo], Callable[..., fa_params.Header]] = pyd.Field,
) -> Tuple[Any, FieldInfo]:
    is_type = isinstance(field, type)
    ismatch: Callable[[Union[Field, Type[Field]], Type], bool] = isinstance if not is_type else issubclass

    description: Optional[str] = (field.__extra__ or {}).get('description', '')

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
    elif ismatch(field, Array):
        arr: Array = field
        elem = arr.elem_type()
        if isinstance(elem, type) and issubclass(elem, Model):
            elem = model_to_pydantic(elem)
            description = f'[{elem.__name__}] {description}'
        if isinstance(elem, type) and issubclass(elem, Field):
            elem, _ = resolve_field(elem)
        py_type = List[elem]
    elif ismatch(field, Map):
        key = field.key_type()
        val = field.value_type()
        if isinstance(key, type) and issubclass(key, Model):
            key = model_to_pydantic(key)

        if isinstance(key, type) and issubclass(key, Field):
            key, _ = resolve_field(key)
        
        if isinstance(val, type) and issubclass(val, Model):
            val = model_to_pydantic(val)
            description = f'[{key.__name__}: {val.__name__}] {description}'
        if isinstance(val, type) and issubclass(val, Field):
            val, _ = resolve_field(val)
        py_type = Dict[key, val]
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
        copy_extra = {k: v for k, v in (field.__extra__ or {}).items() if k != 'description'}
        copy_extra['description'] = description
        info = field_factory(
            **copy_extra
        )
        if (default := copy_extra.get('default', ...)) is not ...:
            if py_type is not Any:
                py_type = Optional[py_type]

    return py_type, info


def dict_to_pyd_model(
    name: str,
    fields: Dict[str, Any],
    config: Type[Any] = None
) -> Type[pyd.BaseModel]:
    kwargs: Dict[str, Tuple[Any, Any]] = {}
    for key, field in fields.items():
        if isinstance(field, Field):
            py_type, info = resolve_field(field)
        elif isinstance(field, type) and issubclass(field, Model):
            nested = model_to_pydantic(field)
            py_type, info = nested, pyd.Field(None)
        else:
            py_type, info = type(field), pyd.Field(field)
        kwargs[key] = (py_type, info)
    if config:
        kwargs['__config__'] = config
    return pyd.create_model(name, **kwargs)

