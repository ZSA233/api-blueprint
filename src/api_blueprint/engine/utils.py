from typing import Union, Any, get_args, get_origin
from pathlib import Path
from inspect import getmro, isclass
import types
import re


def snake_to_pascal_case(s: str, prefix: str = '', invalid_prefix: str = 'Func') -> str:
    segments = s.split('/')
    camel_segments = []
    
    for seg in segments:
        if not seg:
            continue
        parts = re.split(r'[^0-9a-zA-Z]+', seg)
        camel = ''.join(p.capitalize() for p in parts if p)
        if not camel:
            camel = invalid_prefix
        if not camel[0].isalpha():
            camel = invalid_prefix + camel
        camel = re.sub(r'[^0-9a-zA-Z_]', '', camel)
        camel_segments.append(camel)
    
    name = '_'.join(camel_segments)
    if not name:
        name = invalid_prefix
    if not name[0].isalpha():
        name = invalid_prefix + name
    return prefix + name


def pascal_to_snake_case(s: str) -> str:
    s = re.sub(r'[^0-9A-Za-z]', '_', s)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


def inc_to_letters(inc: int, chars: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    inc += 1
    if inc < 1:
        raise ValueError("inc must >= 1 ")
    base = len(chars)
    result = []
    while inc > 0:
        inc -= 1  # 先减 1，使得余数 0 对应 chars[0]
        idx = inc % base
        result.append(chars[idx])
        inc //= base
    return ''.join(reversed(result))


def join_path_imports(p1: Union[str, Path], *pp: Union[str, Path]) -> str:
    p1 = Path(p1)
    for p in pp:
        p1 /= p
    return str(p1).strip('/')



def names_by_definition_order(obj):
    cls = obj if isclass(obj) else obj.__class__
    seen, out = set(), []
    for base in cls.mro():  # 基类→子类
        d = getattr(base, "__dict__", None)
        if d is None: 
            continue
        for k in d.keys():  # 按定义顺序
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


def inspect_getmembers(object, predicate=None, getter=getattr):
    results = []
    processed = set()
    names = names_by_definition_order(object)
    if isclass(object):
        mro = (object,) + getmro(object)
        # add any DynamicClassAttributes to the list of names if object is a class;
        # this may result in duplicate entries if, for example, a virtual
        # attribute with the same name as a DynamicClassAttribute exists
        try:
            for base in object.__bases__:
                for k, v in base.__dict__.items():
                    if isinstance(v, types.DynamicClassAttribute):
                        names.append(k)
        except AttributeError:
            pass
    else:
        mro = ()
    for key in names:
        # First try to get the value via getattr.  Some descriptors don't
        # like calling their __get__ (see bug #1785), so fall back to
        # looking in the __dict__.
        try:
            value = getter(object, key)
            # handle the duplicate key
            if key in processed:
                raise AttributeError
        except AttributeError:
            for base in mro:
                if key in base.__dict__:
                    value = base.__dict__[key]
                    break
            else:
                # could be a (currently) missing slot member, or a buggy
                # __dir__; discard and move on
                continue
        if not predicate or predicate(value):
            results.append((key, value))
        processed.add(key)
    return results


def is_parametrized(val: Any) -> bool:
    return get_origin(val) is not None and bool(get_args(val))
