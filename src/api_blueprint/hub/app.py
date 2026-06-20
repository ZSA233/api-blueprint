from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api_blueprint.engine.runtime.docs import docs_home_path

app = FastAPI()


HERE = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE.parent / "static")), name="static")

app.state.nav_items = []


def set_nav_items(items: list[dict[str, Any]]) -> None:
    app.state.nav_items = list(items)


def add_nav_items(target_app: FastAPI, host: str):
    title = target_app.title
    link = urljoin(host, docs_home_path(target_app))
    nav_items = list(getattr(app.state, "nav_items", []))
    nav_items.append(
        {
            "name": title,
            "url": link,
            "route_count": 0,
        }
    )
    set_nav_items(nav_items)


@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "nav_items": getattr(app.state, "nav_items", []),
        },
    )
