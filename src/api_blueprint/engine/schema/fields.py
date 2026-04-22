from __future__ import annotations

import enum
import zlib
from typing import Any, ForwardRef, Generic, Optional, TypeVar, get_args, get_origin, overload

from fastapi.security import api_key as fa_apikey

from .modeling import Field, Model, create_model, get_forward_ref_type, iter_model_vars

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Object(Field):
    __type__ = "object"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class Null(Field):
    __type__ = "null"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class String(Field):
    __type__ = "string"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class Int(Field):
    __type__ = "int"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class Int64(Int):
    __type__ = "int64"


class Int32(Int):
    __type__ = "int32"


class Int16(Int):
    __type__ = "int16"


class Int8(Int):
    __type__ = "int8"


class Uint(Int):
    __type__ = "uint"


class Uint64(Int):
    __type__ = "uint64"


class Uint32(Int):
    __type__ = "uint32"


class Uint16(Int):
    __type__ = "uint16"


class Uint8(Int):
    __type__ = "uint8"


class Float(Field):
    __type__ = "float"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class Float64(Field):
    __type__ = "float64"


class Float32(Field):
    __type__ = "float32"


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

    def __init__(self, **kwargs: Any):
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

    def __init__(self, **kwargs: Any):
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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def enum_type(self) -> type[enum.Enum]:
        args = get_args(self.__orig_class__)
        enum_type = args[0] if args else Any
        if isinstance(enum_type, ForwardRef):
            enum_type = get_forward_ref_type(enum_type)
        return enum_type

    def enum_base_type(self) -> Optional[type]:
        enum_type = self.enum_type()
        members = list(enum_type)
        if not members:
            raise Exception("没有提供任何枚举值，无法推断其基础类型")

        types = [type(member.value) for member in members]
        for cond in types[0].mro():
            if all(issubclass(member_type, cond) for member_type in types):
                return cond
        raise object


def iter_enum_classes(value: Any):
    yield from _iter_enum_classes(value, set())


def _iter_enum_classes(value: Any, visited_models: set[type[Model]]):
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
        for _name, sub in iter_model_vars(model_cls):
            yield from _iter_enum_classes(sub, visited_models)
        return

    if isinstance(value, type):
        try:
            if issubclass(value, Model):
                if value in visited_models:
                    return
                visited_models.add(value)
                for _name, sub in iter_model_vars(value):
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
                yield from _iter_enum_classes(value(), visited_models)
                return
        except TypeError:
            pass

    origin = get_origin(value)
    if origin and isinstance(origin, type):
        try:
            if issubclass(origin, Field):
                yield from _iter_enum_classes(value(), visited_models)
                return
        except TypeError:
            pass

        try:
            if issubclass(origin, Model):
                if origin in visited_models:
                    return
                visited_models.add(origin)
                for _name, sub in iter_model_vars(origin):
                    yield from _iter_enum_classes(sub, visited_models)
                return
        except TypeError:
            pass


class AnonKV(Field):
    __type__ = "anonkv"
    origin: Optional[type]
    kvs: dict[str, Any]
    _obj: Any = None

    def __init__(self, origin: Optional[type] = None, **kvs: Any):
        self.origin = origin
        self.kvs = kvs

    def __call__(self, **kwargs: Any):
        self.__extra__ = kwargs
        return self

    def get_obj(self):
        return self._obj

    def build(self, router: Any, field_name: str | None):
        if field_name and router:
            name = f"ANON_{router.name}_{field_name}"
        else:
            short_id = zlib.crc32(f'{" ".join(sorted(self.kvs.keys()))}'.encode("utf8")) & 0xFFFFFFFF
            name = f"ANON_{short_id:08x}"
        model = create_model(name, self.kvs).__class__
        obj = self.origin[model]() if self.origin else model
        if isinstance(obj, ForwardRef):
            obj = get_forward_ref_type(obj)
        self._obj = obj
        return obj


def ArrayKV(**kwargs: Any):
    return AnonKV(Array, **kwargs)


def KV(**kwargs: Any):
    return AnonKV(None, **kwargs)


class Array(Field, Generic[T]):
    __type__ = "array"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def elem_type(self) -> Any:
        args = get_args(self.__orig_class__)
        elem_type = args[0] if args else Any
        if isinstance(elem_type, ForwardRef):
            elem_type = get_forward_ref_type(elem_type)
        return elem_type


class Map(Field, Generic[K, V]):
    __name__: str = "Map"
    __type__ = "map"

    @overload
    def __init__(
        self,
        *,
        default: dict[K, V] = ...,
        min_properties: int | None = ...,
        max_properties: int | None = ...,
        description: str | None = ...,
        alias: str | None = ...,
        example: dict[K, V] = ...,
        omitempty: bool = False,
        **kwargs: Any,
    ) -> None: ...

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def key_type(self) -> Any:
        args = get_args(self.__orig_class__)
        key_type = args[0] if args else Any
        if isinstance(key_type, ForwardRef):
            key_type = get_forward_ref_type(key_type)
        return key_type

    def value_type(self) -> Any:
        args = get_args(self.__orig_class__)
        value_type = args[1] if len(args) > 1 else Any
        if isinstance(value_type, ForwardRef):
            value_type = get_forward_ref_type(value_type)
        return value_type


class Error(Field):
    code: int
    message: str

    __type__ = "error"

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

    def __init__(self, code: int, message: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.code = code
        self.message = message


class Header(Field):
    __type__ = "header"

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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class APIKeyHeader(Field):
    __type__ = "api_key_header"

    @overload
    def __init__(
        self,
        *,
        name: Any = ...,
        scheme_name: str | None = None,
        description: str | None = ...,
        auto_error: bool = False,
    ) -> None: ...

    def __init__(self, **kwargs: Any):
        auto_error = kwargs.pop("auto_error", False)
        kwargs["auto_error"] = auto_error
        super().__init__(**kwargs)

    def __call__(self, *args: Any, **kwargs: Any):
        scheme_name = kwargs.pop("scheme_name", None)
        if scheme_name is None and self.__key__ is not None:
            cls_name, scheme_name = self.__key__
            kwargs["scheme_name"] = f"{cls_name}: {scheme_name}"
        return fa_apikey.APIKeyHeader(*args, **kwargs)


class FieldWrappedModel(Model):
    __name_val__: str = "Field"
    __field_type__: type[Field]
    __auto__: bool = True

    def __init__(self, field_type: Field, **kwargs: Any):
        super().__init__(**kwargs)
        self.__field_type__ = field_type

    @property
    def __name__(self) -> str:
        return self.__name_val__

    @__name__.setter
    def __name__(self, name: str) -> None:
        self.__name_val__ = name

    def __call__(self, *args: Any, **kwargs: Any):
        self.__extra__ = kwargs
        return self.__field_type__


def create_field_wrapped_model(name: str, field: Field) -> FieldWrappedModel:
    model = FieldWrappedModel(field)
    model.__name__ = name
    model.__auto__ = True
    return model


class HeaderModel(Model):
    __type__ = "header_model"


class NoneHeader(HeaderModel):
    pass


BASIC_FIELD_TYPES = frozenset(
    value
    for value in locals().values()
    if isinstance(value, type) and issubclass(value, Field)
)
