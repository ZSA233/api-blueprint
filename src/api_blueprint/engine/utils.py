from typing import Union
from pathlib import Path
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
            camel = 'F' + camel
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


