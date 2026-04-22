from __future__ import annotations

from abc import abstractmethod
from typing import Any, Generic, TypeVar

from api_blueprint.engine.schema import Error, Field, Int, Model, String

TM = TypeVar("TM", bound=Model)


class ResponseWrapper(Model):
    __xml_options__: dict[str, Any] = {
        "root_label": None,
    }

    @classmethod
    def get_xml_root_name(cls) -> str:
        return cls.__xml_options__.get("root_label") or cls.__name__

    @classmethod
    @abstractmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseWrapper"]: ...

    @classmethod
    @abstractmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]: ...

    @classmethod
    @abstractmethod
    def golang_factory(cls, typ: str) -> str: ...

    @classmethod
    def json_schema_extra(cls) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if xml_root := cls.__xml_options__["root_label"]:
            extra["xml"] = {"name": xml_root}
        return extra


_RSP_CLASS_CACHE: dict[tuple[type[ResponseWrapper], type[Model]], type[ResponseWrapper]] = {}


def reset_response_wrapper_cache() -> None:
    _RSP_CLASS_CACHE.clear()


class NoneWrapper(ResponseWrapper):
    @classmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseWrapper"]:
        cls_name = f"{data_cls.__name__}_Wrapper"
        cache_key = (cls, data_cls)
        rsp_cls = _RSP_CLASS_CACHE.get(cache_key)
        if rsp_cls is not None:
            return rsp_cls

        namespaces: dict[str, Any] = {
            "__name__": cls_name,
            "__module__": cls.__name__,
            "__wrapper__": cls,
        }
        rsp_cls = type(cls_name, (data_cls,), namespaces)
        _RSP_CLASS_CACHE[cache_key] = rsp_cls
        return rsp_cls

    @classmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]:
        cls_key, name = err.__key__
        key = f"{cls_key}.{name}"
        return key, {
            "error": key,
            "detail": err.message,
        }

    @classmethod
    def golang_factory(cls, typ: str) -> str:
        return {
            "json": """
                return int({code}), ({wrapper_name})({data})""",
            "xml": """
                inner := ({wrapper_name}_INNER)({data})
                return int({code}), &{wrapper_name}{{
                    XMLName: xml.Name{{Local: "%s"}},
                    Inner:   &inner,
                }}""" % (cls.get_xml_root_name(),),
        }[typ]


class GeneralWrapper(ResponseWrapper, Generic[TM]):
    code = Int(description="code")
    message = String(description="message", omitempty=True)
    data: TM = Field(description="data", omitempty=True)

    __xml_options__ = {
        "root_label": "response",
    }

    @classmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseWrapper"]:
        cls_name = f"{data_cls.__name__}_Wrapper"
        cache_key = (cls, data_cls)
        rsp_cls = _RSP_CLASS_CACHE.get(cache_key)
        if rsp_cls is not None:
            return rsp_cls

        namespaces = {key: value for key, value in vars(cls).items()}
        namespaces["__name__"] = cls_name
        namespaces["__module__"] = cls.__name__
        namespaces["__wrapper__"] = cls
        namespaces["data"] = data_cls(description="data")
        rsp_cls = type(cls_name, (GeneralWrapper,), namespaces)
        _RSP_CLASS_CACHE[cache_key] = rsp_cls
        return rsp_cls

    @classmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]:
        cls_key, name = err.__key__
        key = f"{cls_key}.{name}"
        return key, {
            "code": err.code,
            "message": err.message,
        }

    @classmethod
    def golang_factory(cls, typ: str) -> str:
        return {
            "json": """
                return 0, &{wrapper_name}{generic_types}{{
                    Code:    {code},
                    Message: {message},
                    Data:    {data},
                }}""",
            "xml": """
                return int({code}), &{wrapper_name}{generic_types}{{
                    XMLName: xml.Name{{Local: "%s"}},
                    Inner: &{wrapper_name}_INNER{generic_types}{{
                        Code:    {code},
                        Message: {message},
                        Data:    {data},
                    }},
                }}""" % (cls.get_xml_root_name(),),
        }[typ]
