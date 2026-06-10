from api_blueprint.includes import *


class RequestSignature(provider.Provider):
    name = "request-signature"


public_api = Blueprint(
    root="/api",
    tags=["public"],
    providers=[
        provider.Req(),
        RequestSignature(),
        provider.Handle(),
        provider.Rsp(),
    ],
)


with public_api.group("/orders") as orders:
    orders.POST(
        "/create",
        operation_id="create_order",
        summary="Create order",
        description="Spring MVC controller/delegate example route.",
    ).REQ(
        sku=String(description="Stock keeping unit"),
        quantity=Int(description="Quantity"),
        note=String(description="Optional buyer note", omitempty=True),
    ).RSP(
        order_id=String(description="Created order id"),
        status=String(description="Order status"),
    )
