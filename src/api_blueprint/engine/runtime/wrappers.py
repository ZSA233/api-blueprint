from __future__ import annotations

from abc import abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

from api_blueprint.engine.schema import Bool, Error, Field, Int, Model, String

TM = TypeVar("TM", bound=Model)


class ResponseEnvelope(Model):
    __envelope_kind__: ClassVar[str] = "custom"
    __error_identity__: ClassVar[str] = "nested"
    __success_code__: ClassVar[int] = 0
    __success_message__: ClassVar[str] = "ok"
    __envelope_fields__: ClassVar[dict[str, str]] = {}
    __xml_options__: dict[str, Any] = {
        "root_label": None,
    }

    @classmethod
    def get_xml_root_name(cls) -> str:
        return cls.__xml_options__.get("root_label") or cls.__name__

    @classmethod
    @abstractmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseEnvelope"]: ...

    @classmethod
    @abstractmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]: ...

    @classmethod
    def json_schema_extra(cls) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if xml_root := cls.__xml_options__["root_label"]:
            extra["xml"] = {"name": xml_root}
        return extra

    @classmethod
    def envelope_spec(cls) -> dict[str, Any]:
        return {
            "name": cls.__name__,
            "kind": cls.__envelope_kind__,
            "error_identity": cls.__error_identity__,
            "success_code": cls.__success_code__,
            "success_message": cls.__success_message__,
            "fields": dict(cls.__envelope_fields__),
        }


_RSP_CLASS_CACHE: dict[tuple[type[ResponseEnvelope], type[Model]], type[ResponseEnvelope]] = {}


def reset_response_envelope_cache() -> None:
    _RSP_CLASS_CACHE.clear()


class NoEnvelope(ResponseEnvelope):
    __envelope_kind__ = "none"
    __error_identity__ = "none"
    __envelope_fields__ = {}

    @classmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseEnvelope"]:
        cls_name = f"{data_cls.__name__}_Envelope"
        cache_key = (cls, data_cls)
        rsp_cls = _RSP_CLASS_CACHE.get(cache_key)
        if rsp_cls is not None:
            return rsp_cls

        namespaces: dict[str, Any] = {
            "__name__": cls_name,
            "__module__": cls.__name__,
            "__envelope__": cls,
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

class EnvelopeToastPayload(Model):
    key = String(description="toast key")
    level = String(description="toast level")
    default = String(description="default toast text")
    text = String(description="dynamic toast text", omitempty=True)


class EnvelopeErrorIdentityPayload(Model):
    id = String(description="stable error id")
    group = String(description="error group")
    key = String(description="error key")
    toast = EnvelopeToastPayload(description="toast payload")


class EnvelopeApiErrorPayload(Model):
    id = String(description="stable error id")
    group = String(description="error group")
    key = String(description="error key")
    code = Int(description="business error code")
    message = String(description="default error message")
    toast = EnvelopeToastPayload(description="toast payload")


class CodeMessageDataEnvelope(ResponseEnvelope, Generic[TM]):
    code = Int(description="business status code")
    message = String(description="status message")
    error = EnvelopeErrorIdentityPayload(description="business error identity", omitempty=True)
    data: TM = Field(description="data", omitempty=True)

    __envelope_kind__ = "code_message_data"
    __error_identity__ = "nested"
    __envelope_fields__ = {
        "code": "code",
        "message": "message",
        "data": "data",
        "error": "error",
    }
    __xml_options__ = {
        "root_label": "response",
    }

    @classmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseEnvelope"]:
        cls_name = f"{data_cls.__name__}_Envelope"
        cache_key = (cls, data_cls)
        rsp_cls = _RSP_CLASS_CACHE.get(cache_key)
        if rsp_cls is not None:
            return rsp_cls

        namespaces = {key: value for key, value in vars(cls).items()}
        namespaces["__name__"] = cls_name
        namespaces["__module__"] = cls.__name__
        namespaces["__envelope__"] = cls
        namespaces["data"] = data_cls(description="data", omitempty=True)
        rsp_cls = type(cls_name, (cls,), namespaces)
        _RSP_CLASS_CACHE[cache_key] = rsp_cls
        return rsp_cls

    @classmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]:
        group, key = err.__key__
        error_id = f"{group}.{key}"
        return error_id, {
            "code": err.code,
            "message": err.message,
            "data": None,
            "error": {
                "id": error_id,
                "group": group,
                "key": key,
                "toast": _error_toast_payload(err),
            },
        }

class LegacyCodeMessageDataEnvelope(CodeMessageDataEnvelope[TM]):
    error = None

    __envelope_kind__ = "code_message_data"
    __error_identity__ = "none"
    __envelope_fields__ = {
        "code": "code",
        "message": "message",
        "data": "data",
    }

    @classmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]:
        group, key = err.__key__
        return f"{group}.{key}", {
            "code": err.code,
            "message": err.message,
            "data": None,
        }

class OkDataErrorEnvelope(ResponseEnvelope, Generic[TM]):
    ok = Bool(description="success flag")
    error = EnvelopeApiErrorPayload(description="business error payload", omitempty=True)
    data: TM = Field(description="data", omitempty=True)

    __envelope_kind__ = "ok_data_error"
    __error_identity__ = "nested"
    __envelope_fields__ = {
        "ok": "ok",
        "data": "data",
        "error": "error",
    }
    __xml_options__ = {
        "root_label": "response",
    }

    @classmethod
    def create(cls, data_cls: type[Model]) -> type["ResponseEnvelope"]:
        cls_name = f"{data_cls.__name__}_Envelope"
        cache_key = (cls, data_cls)
        rsp_cls = _RSP_CLASS_CACHE.get(cache_key)
        if rsp_cls is not None:
            return rsp_cls

        namespaces = {key: value for key, value in vars(cls).items()}
        namespaces["__name__"] = cls_name
        namespaces["__module__"] = cls.__name__
        namespaces["__envelope__"] = cls
        namespaces["data"] = data_cls(description="data")
        rsp_cls = type(cls_name, (cls,), namespaces)
        _RSP_CLASS_CACHE[cache_key] = rsp_cls
        return rsp_cls

    @classmethod
    def on_error(cls, err: Error) -> tuple[str, dict[str, Any]]:
        group, key = err.__key__
        error_id = f"{group}.{key}"
        return error_id, {
            "ok": False,
            "error": {
                "id": error_id,
                "group": group,
                "key": key,
                "code": err.code,
                "message": err.message,
                "toast": _error_toast_payload(err),
            },
        }

def _error_toast_payload(err: Error) -> dict[str, str]:
    group, key = err.__key__
    fallback_key = f"{group}.{key}"
    toast = err.toast
    if toast is None:
        return {
            "key": fallback_key,
            "level": "error",
            "default": err.message,
        }
    return {
        "key": toast.key or fallback_key,
        "level": toast.level or "error",
        "default": toast.default or err.message,
    }
