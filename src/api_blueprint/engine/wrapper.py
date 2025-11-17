from typing import Type, Generic, TypeVar, Dict, Any, Tuple
from api_blueprint.engine.model import Field, Model, Int, String, Error, ModelMeta
from abc import ABC, abstractmethod

TM = TypeVar('TypeModel', bound=Model)


class ResponseWrapper(Model):
    __xml_options__: Dict[str, Any] = {
        'root_label': None
    }

    @classmethod
    def get_xml_root_name(cls) -> str:
        return cls.__xml_options__.get('root_label', None) or cls.__name__

    @classmethod
    @abstractmethod
    def create(cls, data_cls: Type[Model]) -> Type['GeneralWrapper']: ...
    
    @classmethod
    @abstractmethod
    def on_error(cls, err: Error) -> Tuple[str, Dict[str, Any]]: ...

    @classmethod
    @abstractmethod
    def golang_factory(cls, typ: str) -> str: ...

    @classmethod
    def json_schema_extra(cls) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        if xml_root := cls.__xml_options__['root_label']:
            extra['xml'] = {
                'name': xml_root
            }
        return extra



class NoneWrapper(ResponseWrapper):

    @classmethod
    def create(cls, data_cls: Type[Model]) -> Type['GeneralWrapper']:
        global __rsp_cls_cache__
        cls_name = f'{data_cls.__name__}_Wrapper'
        rsp_cls = __rsp_cls_cache__.get(f'{cls.__name__}:{cls_name}', None)
        if rsp_cls:
            return rsp_cls
        namespaces: Dict[str, Any] = {}
        namespaces['__name__'] = cls_name
        namespaces['__module__'] = cls.__name__
        namespaces['__wrapper__'] = cls
        rsp_cls = type(
            cls_name,
            (data_cls,),
            namespaces,
        )
        __rsp_cls_cache__[cls_name] = rsp_cls
        return rsp_cls
    
    @classmethod
    def on_error(cls, err: Error) -> Tuple[str, Dict[str, Any]]:
        cls_key, name = err.__key__
        key = f'{cls_key}.{name}'
        return key, {
            'error': key,
            'detail': err.message
        }

    @classmethod
    def golang_factory(cls, typ: str) -> str:
        return {
            'json': """
                return int({code}), ({wrapper_name})({data})""",
            
            'xml': """
                inner := ({wrapper_name}_INNER)({data})
                return int({code}), &{wrapper_name}{{
                    XMLName: xml.Name{{Local: "%s"}},
                    Inner:   &inner,
                }}""" % (cls.get_xml_root_name(), ),

        }[typ]


__rsp_cls_cache__: Dict[str, 'ResponseWrapper'] = {}


class GeneralWrapper(ResponseWrapper, Generic[TM]):
    code    = Int(description='code')
    message = String(description='message', omitempty=True)
    data: TM= Field(description='data', omitempty=True)
    
    __xml_options__: Dict[str, Any] = {
        'root_label': 'response'
    }

    @classmethod
    def create(cls, data_cls: Type[Model]) -> Type['GeneralWrapper']:
        global __rsp_cls_cache__
        cls_name = f'{data_cls.__name__}_Wrapper'
        rsp_cls = __rsp_cls_cache__.get(f'{cls.__name__}:{cls_name}', None)
        if rsp_cls:
            return rsp_cls
        namespaces: Dict[str, Any] = {}
        for k, v in vars(cls).items():
            namespaces[k] = v
        namespaces['__name__'] = cls_name
        namespaces['__module__'] = cls.__name__
        namespaces['__wrapper__'] = cls
        namespaces['data'] = data_cls(description='data')
        rsp_cls = type(
            cls_name,
            (GeneralWrapper,),
            namespaces,
        )
        __rsp_cls_cache__[cls_name] = rsp_cls
        return rsp_cls
    
    @classmethod
    def on_error(cls, err: Error) -> Tuple[str, Dict[str, Any]]:
        cls_key, name = err.__key__
        key = f'{cls_key}.{name}'
        return key, {
            'code': err.code,
            'message': err.message
        }
    
    @classmethod
    def golang_factory(cls, typ: str) -> str:
        return {
            'json': """
                return 0, &{wrapper_name}{generic_types}{{
                    Code:    {code},
                    Message: {message},
                    Data:    {data},
                }}""",

            'xml': """
                return int({code}), &{wrapper_name}{generic_types}{{
                    XMLName: xml.Name{{Local: "%s"}},
                    Inner: &{wrapper_name}_INNER{generic_types}{{
                        Code:    {code},
                        Message: {message},
                        Data:    {data},
                    }},
                }}""" % (cls.get_xml_root_name(), ),
        }[typ]
    
        