from api_blueprint.includes import *


bp = Blueprint(
    root="/api",
    tags=["wails-hello"],
    providers=[
        provider.Req(),
        provider.Handle(),
        provider.Rsp(),
    ],
)


class GreetResponse(Model):
    message = String(description="Greeting message")


with bp.group("/hello") as views:
    views.GET(
        "/greet",
        summary="Greet a user",
        description="Return a greeting for the provided name.",
    ).ARGS(
        name=String(description="Name to greet", default="World"),
    ).RSP(GreetResponse)
