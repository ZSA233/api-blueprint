
from fnmatch import fnmatch
from typing import Optional, Dict, Any, Generator, Tuple, List
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os


def load_templates(dir: Optional[str]) -> Jinja2Templates:
    return Jinja2Templates(directory=dir)

_template_cache_: Dict[str, Jinja2Templates] = {}

def render(lang: str, name: str, context: Dict[str, Any], relative_path: str = '') -> str:
    templates = _template_cache_.get(lang, None)
    if templates is None:
        path = Path(__path__[0]) / lang
        templates = load_templates(str(path))
        _template_cache_[lang] = templates
    return templates.get_template(
        str(Path(relative_path) / f'{name}.j2'),
    ).render(context)


def iter_render(lang: str, context: Dict[str, Any], relative_path: str = '', exclusives: Tuple[str] = ()) -> Generator[Tuple[str, str], None, None]:
    templates = _template_cache_.get(lang, None)
    path = Path(__path__[0]) / lang
    if templates is None:
        templates = load_templates(str(path))
        _template_cache_[lang] = templates
    

    for file in os.listdir(path / relative_path.lstrip('/')):
        filepath = Path(file)
        filename = filepath.name
        orig_name, ext = os.path.splitext(filename)
        if ext not in ['.j2', '.jinja']:
            continue
        if orig_name in exclusives or orig_name.startswith('__'):
            continue
        yield orig_name, templates.get_template(
            str(Path(relative_path) / filename),
        ).render(context)