from __future__ import annotations

from collections import defaultdict
from types import GenericAlias
from typing import (
    TYPE_CHECKING,
    Any,
    DefaultDict,
    Dict,
    ForwardRef,
    Generator,
    ItemsView,
    TypeAlias,
    TypeVar,
    Union,
    get_args,
    get_origin,
    overload,
)

from api_blueprint.engine.utils import inspect_getmembers, is_parametrized

from .registry import get_named_model, iter_error_models as _iter_error_models, register_model

if TYPE_CHECKING:
    from .fields import Error


AnyField: TypeAlias = Union["Field", "Model", type["Model"]]
AnyModel: TypeAlias = Union["Model", type["Model"]]


class Field:
    __name__: str
    __extra__: dict[str, Any] = {}
    __type__: str = ""
    __auto__: bool = False
    __key__: tuple[str, str] | None = None

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
        self.__extra__ = kwargs

    def __bool__(self) -> bool:
        return True


class ModelMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        model_is_ready = "Model" in globals()
        fields: dict[str, Any] = {}

        for key, value in namespace.items():
            if model_is_ready and isinstance(value, Field):
                setattr(value, "__key__", (name, key))
                fields[key] = value
            elif model_is_ready and isinstance(value, type) and isinstance(value, ModelMeta):
                fields[key] = value

        cls: type["Model"] = super().__new__(mcls, name, bases, namespace)
        cls.__fields__ = fields

        if model_is_ready:
            register_model(
                name,
                cls,
                has_error=any(getattr(value, "__type__", None) == "error" for value in namespace.values()),
            )
        return cls

    def __iter__(cls: type["Model"]):
        return iter(cls.__fields__)

    def __len__(cls: type["Model"]) -> int:
        return len(cls.__fields__)

    def __getitem__(cls: type["Model"], key: Any):
        if not isinstance(key, str) and getattr(cls, "__parameters__", ()):
            return GenericAlias(cls, key if isinstance(key, tuple) else (key,))
        return cls.__fields__[key]

    def keys(cls: type["Model"]):
        return cls.__fields__.keys()

    def items(cls: type["Model"]):
        return cls.__fields__.items()

    def values(cls: type["Model"]):
        return cls.__fields__.values()


class Model(metaclass=ModelMeta):
    __name__: str
    __type__: str = "object"
    __auto__: bool = False
    __extra__: dict[str, Any] = {}
    __fields__: dict[str, Any] = {}

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

    def __init__(self, **kwargs: Any):
        self.__extra__ = kwargs
        self.__name__ = self.__class__.__name__

    def __iter__(self):
        return iter(self.__fields__)

    def __len__(self) -> int:
        return len(self.__fields__)

    def __getitem__(self, key: str):
        return self.__fields__[key]

    def __bool__(self) -> bool:
        return True


def create_model(name: str, data: dict[str, Any], **kwargs: Any) -> "Model":
    namespace = data.copy()
    namespace["__name__"] = name
    namespace["__extra__"] = kwargs
    namespace["__type__"] = "object"
    namespace["__auto__"] = True
    return type(name, (Model,), namespace)(**kwargs)


def iter_model_vars(model: AnyModel) -> ItemsView[str, Union[Field, Model]]:
    cls = model if isinstance(model, type) else model.__class__
    members = {
        key: value
        for key, value in inspect_getmembers(cls)
        if not key.startswith("__")
    }
    return members.items()


def unwrap_errors(errors: list[Union[type[Model], Model, "Error"]]) -> DefaultDict[int, list["Error"]]:
    code_errs: DefaultDict[int, list["Error"]] = defaultdict(list)
    for err in errors:
        if getattr(err, "__type__", None) == "error":
            code_errs[err.code].append(err)
            continue
        if isinstance(err, Model) or (isinstance(err, type) and issubclass(err, Model)):
            for _name, field_err in iter_model_vars(err):
                if getattr(field_err, "__type__", None) == "error":
                    code_errs[field_err.code].append(field_err)
    return code_errs


def iter_error_models() -> Generator[tuple[str, type[Model]], None, None]:
    yield from _iter_error_models()


def unwrap_model_type(model: Union[type[Model], Model, GenericAlias]) -> type[Model]:
    if isinstance(model, type) or is_parametrized(model):
        model_type = model
    elif getattr(model, "__orig_class__", None):
        model_type = model.__orig_class__
    elif hasattr(model, "__field_type__"):
        model_type = unwrap_model_type(model.__field_type__)
    else:
        model_type = model.__class__
    return model_type


class Proto:
    _name: str
    model_type: type[Model]

    def __init__(self, name: str, model: Union[type[Model], Model]):
        self._name = name
        self.model_type = unwrap_model_type(model)

    @property
    def name(self) -> str:
        return self._name


P = TypeVar("P", bound=Proto)


def iter_field_model_type(field: AnyField) -> Generator[type[Model], None, None]:
    from .fields import AnonKV, Array, FieldWrappedModel, Map

    if isinstance(field, AnonKV):
        field = field.get_obj()

    if get_origin(field):
        yield from iter_field_model_type(field())
        for arg in get_args(field):
            yield from iter_field_model_type(arg)
        return

    if isinstance(field, Array):
        yield from iter_field_model_type(field.elem_type())
        return

    if isinstance(field, Map):
        yield from iter_field_model_type(field.value_type())
        return

    if isinstance(field, Model):
        model_type = field.__class__
    elif isinstance(field, type) and issubclass(field, Model):
        if field is FieldWrappedModel:
            model_type = field.__field_type__
        else:
            model_type = field
    else:
        return

    for _name, sub_field in iter_model_vars(model_type):
        yield from iter_field_model_type(sub_field)
    yield model_type


def get_forward_ref_type(ref: ForwardRef) -> type[Model] | None:
    return get_named_model(ref.__forward_arg__)
