from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from urllib.parse import urljoin
from pathlib import Path

app = FastAPI()


HERE = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

NAV_ITEMS = []


def add_nav_items(app: FastAPI, host: str):
    title = app.title
    link = urljoin(host, app.docs_url)
    NAV_ITEMS.append({
        'name': title,
        'url': link,
    })


@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "nav_items": NAV_ITEMS,
        },
    )
