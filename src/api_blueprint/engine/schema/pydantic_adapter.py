from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, get_origin

import fastapi
import pydantic as pyd
from fastapi import params as fa_params
from pydantic import ConfigDict
from pydantic.fields import FieldInfo

from api_blueprint.engine.utils import is_parametrized

from .fields import (
    APIKeyHeader,
    AnonKV,
    Array,
    Bool,
    Byte,
    Enum,
    Error,
    FieldWrappedModel,
    Float,
    Float32,
    Float64,
    Header,
    Int,
    Int8,
    Int16,
    Int32,
    Int64,
    Map,
    Null,
    String,
    Uint,
    Uint8,
    Uint16,
    Uint32,
    Uint64,
)
from .modeling import AnyModel, Field, Model, iter_model_vars

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.router import Router
    from api_blueprint.engine.runtime.wrappers import ResponseWrapper


_PYDANTIC_MODEL_CACHE: dict[type[Model] | Map, Any] = {}


def reset_pydantic_model_cache() -> None:
    _PYDANTIC_MODEL_CACHE.clear()


def model_to_pydantic(
    cls: type[Model] | Map,
    field_factory: Callable[..., FieldInfo] | Callable[..., fa_params.Header] = pyd.Field,
    *,
    name: str | None = None,
    router: "Router" | None = None,
) -> type[pyd.BaseModel]:
    cls_name = cls.__name__
    cached = _PYDANTIC_MODEL_CACHE.get(cls)
    if cached is not None:
        return cached

    annotations: dict[str, Any] = {}
    namespace: dict[str, Any] = {}

    for field_name, attr in iter_model_vars(cls):
        if isinstance(attr, Field):
            py_type, info = resolve_field(attr, field_factory, name=field_name, router=router)
        elif isinstance(attr, Model):
            nested = model_to_pydantic(attr.__class__, name=field_name, router=router)
            py_type = nested
            description = attr.__extra__.get("description", "")
            copy_extra = {key: value for key, value in attr.__extra__.items() if key != "description"}
            copy_extra["description"] = f"[{attr.__class__.__name__}] {description}"
            info = field_factory(**copy_extra)
        else:
            continue

        annotations[field_name] = py_type
        namespace[field_name] = info

    wrapper: type["ResponseWrapper"] | None = getattr(cls, "__wrapper__", None)
    if wrapper is not None:
        namespace["model_config"] = ConfigDict(json_schema_extra=wrapper.json_schema_extra())
        annotations["model_config"] = ClassVar[ConfigDict]

    namespace["__annotations__"] = annotations
    namespace["__name__"] = cls_name
    namespace["__module__"] = "api_model"
    pyd_cls = type(cls_name, (pyd.BaseModel,), namespace)
    _PYDANTIC_MODEL_CACHE[cls] = pyd_cls
    return pyd_cls


def resolve_field(
    field: Field | type[Field],
    field_factory: Callable[..., FieldInfo] | Callable[..., fa_params.Header] = pyd.Field,
    *,
    name: str | None = None,
    router: "Router" | None = None,
) -> tuple[Any, FieldInfo | Any]:
    if is_parametrized(field):
        field = field()

    is_type = isinstance(field, type)
    ismatch: Callable[[Field | type[Field], type], bool] = isinstance if not is_type else issubclass
    description: str = getattr(field, "__extra__", {}).get("description", "")

    if ismatch(field, String):
        py_type = str
    elif ismatch(field, (Int, Int64, Int32, Int16, Int8, Uint, Uint8, Uint16, Uint32, Uint64)):
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
            description = f"[{elem.__name__}] {description}"
        if isinstance(elem, type) and issubclass(elem, Field):
            elem, _ = resolve_field(elem, name=name, router=router)
        elif get_origin(elem):
            origin = get_origin(elem)
            if isinstance(origin, type) and issubclass(origin, Field):
                elem, _ = resolve_field(elem(), name=name, router=router)
        py_type = list[elem]
    elif ismatch(field, Map):
        key = field.key_type()
        value = field.value_type()
        if isinstance(key, type) and issubclass(key, Model):
            key = model_to_pydantic(key, name=name, router=router)
        if (isinstance(key, type) and issubclass(key, Field)) or is_parametrized(key):
            key, _ = resolve_field(key, name=name, router=router)

        if isinstance(value, type) and issubclass(value, Model):
            value = model_to_pydantic(value, name=name, router=router)
            description = f"[{key.__name__}: {value.__name__}] {description}"
        if (isinstance(value, type) and issubclass(value, Field)) or is_parametrized(value):
            value, _ = resolve_field(value, name=name, router=router)
        elif get_origin(value):
            origin = get_origin(value)
            if isinstance(origin, type) and issubclass(origin, Field):
                value, _ = resolve_field(value(), name=name, router=router)

        py_type = dict[key, value]
    elif ismatch(field, AnonKV):
        obj = field.get_obj()
        if obj is None or router is not None:
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
        field_factory = lambda *args, **kwargs: fastapi.Security(field(*args, **kwargs))
    elif ismatch(field, Byte):
        py_type = int
    else:
        py_type = Any

    if is_type:
        info = None
    else:
        copy_extra = _normalize_field_factory_kwargs(field.__extra__, description=description)
        info = field_factory(**copy_extra)
        if copy_extra.get("default", ...) is not ... and py_type is not Any:
            py_type = Optional[py_type]

    return py_type, info


def _normalize_field_factory_kwargs(extra: dict[str, Any], *, description: str) -> dict[str, Any]:
    copy_extra = {key: value for key, value in extra.items() if key != "description"}
    omitempty = bool(copy_extra.pop("omitempty", False))
    regex = copy_extra.pop("regex", None)

    if regex is not None:
        copy_extra["pattern"] = regex

    json_schema_extra = copy_extra.get("json_schema_extra")
    merged_schema_extra = dict(json_schema_extra or {})
    if omitempty:
        merged_schema_extra["omitempty"] = True
    if merged_schema_extra:
        copy_extra["json_schema_extra"] = merged_schema_extra

    copy_extra["description"] = description
    return copy_extra
